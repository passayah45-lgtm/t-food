from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, UnidentifiedImageError

from fooddelivery.media_storage import safe_media_name


ALLOWED_IMAGE_FORMATS = {'JPEG', 'PNG', 'WEBP'}
IMAGE_EXTENSIONS = {
    'JPEG': {'.jpg', '.jpeg'},
    'PNG': {'.png'},
    'WEBP': {'.webp'},
}
DOCUMENT_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.webp'}
DEFAULT_IMAGE_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_DOCUMENT_MAX_BYTES = 10 * 1024 * 1024


def _max_bytes(setting_name, default):
    return int(getattr(settings, setting_name, default))


def _position(file_obj):
    try:
        return file_obj.tell()
    except (AttributeError, OSError):
        return None


def _restore(file_obj, position):
    if position is None:
        return
    try:
        file_obj.seek(position)
    except (AttributeError, OSError):
        return


def _size(file_obj):
    size = getattr(file_obj, 'size', None)
    if size is not None:
        return size
    position = _position(file_obj)
    try:
        file_obj.seek(0, 2)
        return file_obj.tell()
    except (AttributeError, OSError):
        raise ValidationError('Unable to determine upload size.')
    finally:
        _restore(file_obj, position)


def _extension(filename):
    return Path(filename or '').suffix.lower()


def _require_safe_extension(file_obj, allowed_extensions):
    extension = _extension(getattr(file_obj, 'name', ''))
    if extension not in allowed_extensions:
        raise ValidationError('Unsupported file extension.')
    return extension


def _image_metadata(image_file, *, max_bytes, require_extension=True):
    if not image_file:
        raise ValidationError('Image is required.')
    size = _size(image_file)
    if size > max_bytes:
        mb = max_bytes // (1024 * 1024)
        raise ValidationError(f'Image must be {mb} MB or smaller.')

    extension = _extension(getattr(image_file, 'name', ''))
    if require_extension and extension not in {'.jpg', '.jpeg', '.png', '.webp'}:
        raise ValidationError('Unsupported image type. Use JPEG, PNG, or WebP.')

    position = _position(image_file)
    try:
        image_file.seek(0)
        with Image.open(image_file) as image:
            image.verify()
            image_format = (image.format or '').upper()
            width, height = image.size
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise ValidationError('Upload a valid JPEG, PNG, or WebP image.')
    finally:
        _restore(image_file, position)

    if image_format not in ALLOWED_IMAGE_FORMATS:
        raise ValidationError('Unsupported image type. Use JPEG, PNG, or WebP.')
    if require_extension and extension not in IMAGE_EXTENSIONS[image_format]:
        raise ValidationError('File extension does not match image content.')

    return {
        'width': width,
        'height': height,
        'format': image_format,
        'size_bytes': size,
    }


def validate_public_image_upload(image_file):
    return _image_metadata(
        image_file,
        max_bytes=_max_bytes('PUBLIC_IMAGE_UPLOAD_MAX_BYTES', DEFAULT_IMAGE_MAX_BYTES),
    )


def validate_private_image_upload(image_file):
    return _image_metadata(
        image_file,
        max_bytes=_max_bytes('PRIVATE_IMAGE_UPLOAD_MAX_BYTES', DEFAULT_IMAGE_MAX_BYTES),
    )


def validate_private_document_upload(file_obj):
    if not file_obj:
        raise ValidationError('Document is required.')
    max_bytes = _max_bytes('PRIVATE_DOCUMENT_UPLOAD_MAX_BYTES', DEFAULT_DOCUMENT_MAX_BYTES)
    size = _size(file_obj)
    if size > max_bytes:
        mb = max_bytes // (1024 * 1024)
        raise ValidationError(f'Document must be {mb} MB or smaller.')

    extension = _require_safe_extension(file_obj, DOCUMENT_EXTENSIONS)
    if extension == '.pdf':
        position = _position(file_obj)
        try:
            file_obj.seek(0)
            header = file_obj.read(8)
            if header.startswith(b'MZ'):
                raise ValidationError('Executable files are not allowed.')
            if not header.startswith(b'%PDF-'):
                raise ValidationError('Upload a valid PDF document.')
        finally:
            _restore(file_obj, position)
        return {'format': 'PDF', 'size_bytes': size}

    metadata = validate_private_image_upload(file_obj)
    return {'format': metadata['format'], 'size_bytes': size}


def strip_image_exif(image_file):
    position = _position(image_file)
    try:
        image_file.seek(0)
        with Image.open(image_file) as image:
            image_format = (image.format or 'JPEG').upper()
            data = list(image.getdata())
            clean = Image.new(image.mode, image.size)
            clean.putdata(data)
            if image_format == 'JPEG' and clean.mode not in ('RGB', 'L'):
                clean = clean.convert('RGB')
            buffer = BytesIO()
            clean.save(buffer, format=image_format)
            return ContentFile(
                buffer.getvalue(),
                name=_safe_basename(getattr(image_file, 'name', ''), image_format),
            )
    except Exception:
        return image_file
    finally:
        _restore(image_file, position)


def generate_safe_upload_filename(prefix, filename):
    return safe_media_name(prefix, filename)


def prepare_public_image_upload(image_file):
    metadata = validate_public_image_upload(image_file)
    stripped = strip_image_exif(image_file)
    stripped.name = _safe_basename(getattr(image_file, 'name', ''), metadata['format'])
    return stripped


def prepare_private_image_upload(image_file):
    metadata = validate_private_image_upload(image_file)
    stripped = strip_image_exif(image_file)
    stripped.name = _safe_basename(getattr(image_file, 'name', ''), metadata['format'])
    return stripped


def prepare_private_document_upload(file_obj):
    metadata = validate_private_document_upload(file_obj)
    if metadata['format'] in ALLOWED_IMAGE_FORMATS:
        return prepare_private_image_upload(file_obj)
    file_obj.name = _safe_basename(getattr(file_obj, 'name', ''), 'PDF')
    return file_obj


def _safe_basename(filename, detected_format):
    extension = {
        'JPEG': '.jpg',
        'PNG': '.png',
        'WEBP': '.webp',
        'PDF': '.pdf',
    }.get((detected_format or '').upper(), _extension(filename) or '.bin')
    safe_name = safe_media_name('uploads', filename or 'upload')
    return f'{Path(safe_name).stem}{extension}'

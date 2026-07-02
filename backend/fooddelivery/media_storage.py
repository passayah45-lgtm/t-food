import mimetypes
import os
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.files.storage import FileSystemStorage, default_storage
from django.http import HttpResponse
from django.utils.text import get_valid_filename


PRIVATE_MEDIA_PREFIX = 'private/'
PUBLIC_REVIEW_PHOTO_PREFIX = 'reviews/photos/approved/'


def private_storage():
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)


def _extension(filename):
    suffix = Path(filename or '').suffix.lower()
    if len(suffix) > 12:
        return ''
    return suffix


def safe_media_name(prefix, filename, max_length=100):
    prefix = prefix.rstrip('/')
    extension = _extension(filename)
    unique_part = uuid4().hex
    available = max_length - len(prefix) - len(unique_part) - len(extension) - 2
    basename = get_valid_filename(Path(filename or 'upload').stem)[:max(1, available)] or 'upload'
    return f'{prefix}/{unique_part}-{basename}{extension}'


def store_private_upload(file_obj, prefix, filename=None):
    storage = private_storage()
    name = safe_media_name(prefix, filename or getattr(file_obj, 'name', 'upload'))
    return storage.save(name, file_obj)


def private_file_exists(name):
    return bool(name) and private_storage().exists(name)


def public_file_exists(name):
    return bool(name) and default_storage.exists(name)


def open_private_file(name, mode='rb'):
    return private_storage().open(name, mode)


def open_public_file(name, mode='rb'):
    return default_storage.open(name, mode)


def file_response(file_handle, filename=None):
    content_type, _encoding = mimetypes.guess_type(filename or '')
    try:
        content = file_handle.read()
    finally:
        close = getattr(file_handle, 'close', None)
        if close:
            close()
    response = HttpResponse(
        content,
        content_type=content_type or 'application/octet-stream',
    )
    response['Content-Disposition'] = f'inline; filename="{filename or "t-food-media"}"'
    return response


def attach_private_upload(instance, field_name, prefix):
    field_file = getattr(instance, field_name)
    if not field_file or getattr(field_file, '_committed', True):
        return
    original_name = getattr(field_file.file, 'name', field_file.name)
    saved_name = store_private_upload(field_file.file, prefix, original_name)
    field_file.name = saved_name
    field_file._committed = True


def publish_private_file_to_public(private_name, public_prefix=PUBLIC_REVIEW_PHOTO_PREFIX):
    if not private_name:
        return ''
    if public_file_exists(private_name):
        return private_name
    storage = private_storage()
    if not storage.exists(private_name):
        return private_name
    public_name = safe_media_name(public_prefix, os.path.basename(private_name))
    with storage.open(private_name, 'rb') as source:
        return default_storage.save(public_name, source)

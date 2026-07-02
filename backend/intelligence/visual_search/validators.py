from fooddelivery.upload_validation import (
    prepare_private_image_upload,
    validate_private_image_upload,
)


def validate_visual_search_image(image_file):
    return validate_private_image_upload(image_file)


def strip_image_exif(image_file):
    return prepare_private_image_upload(image_file)

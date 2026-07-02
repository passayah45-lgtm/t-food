from fooddelivery.upload_validation import (
    prepare_private_image_upload,
    validate_private_image_upload,
)


def validate_review_photo_image(image_file):
    return validate_private_image_upload(image_file)


def strip_review_photo_exif(image_file):
    return prepare_private_image_upload(image_file)

import tempfile
from io import BytesIO

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APITestCase

from customers.models import Customer
from fooddelivery.media_storage import private_file_exists
from fooddelivery.upload_validation import (
    generate_safe_upload_filename,
    prepare_private_document_upload,
    strip_image_exif,
    validate_private_document_upload,
    validate_private_image_upload,
    validate_public_image_upload,
)
from restaurants.models import MerchantProfile, Restaurant
from verifications.constants import SUBJECT_MERCHANT
from verifications.models import VerificationDocument


TEST_MEDIA_ROOT = tempfile.mkdtemp()
TEST_PRIVATE_MEDIA_ROOT = tempfile.mkdtemp()


def image_upload(name='tfood.jpg', image_format='JPEG', size=(16, 12), color=(255, 122, 0)):
    buffer = BytesIO()
    Image.new('RGB', size, color=color).save(buffer, format=image_format)
    return SimpleUploadedFile(
        name,
        buffer.getvalue(),
        content_type={
            'JPEG': 'image/jpeg',
            'PNG': 'image/png',
            'WEBP': 'image/webp',
        }.get(image_format, 'application/octet-stream'),
    )


class UploadValidationUtilityTests(TestCase):
    def test_svg_rejected(self):
        svg = SimpleUploadedFile(
            'logo.svg',
            b'<svg><script>alert(1)</script></svg>',
            content_type='image/svg+xml',
        )

        with self.assertRaises(ValidationError):
            validate_public_image_upload(svg)

    def test_oversized_image_rejected(self):
        image = SimpleUploadedFile(
            'large.jpg',
            b'x' * (5 * 1024 * 1024 + 1),
            content_type='image/jpeg',
        )

        with self.assertRaises(ValidationError):
            validate_private_image_upload(image)

    def test_corrupt_image_rejected(self):
        image = SimpleUploadedFile(
            'broken.jpg',
            b'not-an-image',
            content_type='image/jpeg',
        )

        with self.assertRaises(ValidationError):
            validate_public_image_upload(image)

    def test_fake_extension_with_wrong_content_rejected(self):
        image = image_upload('fake.jpg', image_format='PNG')

        with self.assertRaises(ValidationError):
            validate_public_image_upload(image)

    def test_pdf_verification_document_accepted(self):
        pdf = SimpleUploadedFile(
            'identity.pdf',
            b'%PDF-1.4\n% T-Food identity document\n',
            content_type='application/pdf',
        )

        metadata = validate_private_document_upload(pdf)

        self.assertEqual(metadata['format'], 'PDF')

    def test_executable_disguised_as_pdf_rejected(self):
        fake = SimpleUploadedFile(
            'identity.pdf',
            b'MZ\x90\x00pretend executable',
            content_type='application/pdf',
        )

        with self.assertRaises(ValidationError):
            validate_private_document_upload(fake)

    def test_exif_stripping_does_not_crash(self):
        stripped = strip_image_exif(image_upload('tfood-photo.jpg'))

        self.assertTrue(stripped.name.endswith('.jpg'))
        self.assertGreater(stripped.size, 0)

    def test_safe_filename_removes_directory_traversal(self):
        name = generate_safe_upload_filename('avatars', '../../secret/t-food.jpg')

        self.assertTrue(name.startswith('avatars/'))
        self.assertNotIn('..', name)
        self.assertNotIn('\\', name)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT, PRIVATE_MEDIA_ROOT=TEST_PRIVATE_MEDIA_ROOT)
class UploadValidationApiTests(APITestCase):
    def setUp(self):
        self.customer_user = User.objects.create_user(
            username='upload-customer',
            password='test-password',
        )
        Customer.objects.create(user=self.customer_user)
        self.merchant_user = User.objects.create_user(
            username='upload-merchant',
            password='test-password',
        )
        MerchantProfile.objects.create(
            user=self.merchant_user,
            business_name='T-Food Upload Merchant',
        )
        self.restaurant = Restaurant.objects.create(
            owner=self.merchant_user,
            rest_name='T-Food Upload Branch',
            rest_email='upload-branch@example.com',
            rest_contact='9000001000',
            rest_address='Kaloum Road',
            rest_city='Conakry',
            is_active=True,
        )

    def test_customer_avatar_upload_uses_public_image_validation(self):
        self.client.force_authenticate(self.customer_user)

        response = self.client.patch(
            '/api/v1/users/profile/',
            {'avatar': image_upload('avatar.png', image_format='PNG')},
            format='multipart',
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('avatar', response.data)
        self.assertNotIn('..', response.data['avatar'])

    def test_customer_avatar_rejects_svg(self):
        self.client.force_authenticate(self.customer_user)

        response = self.client.patch(
            '/api/v1/users/profile/',
            {
                'avatar': SimpleUploadedFile(
                    'avatar.svg',
                    b'<svg></svg>',
                    content_type='image/svg+xml',
                ),
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, 400)

    def test_restaurant_cover_rejects_fake_extension(self):
        self.client.force_authenticate(self.merchant_user)

        response = self.client.patch(
            f'/api/v1/merchants/restaurants/{self.restaurant.id}/',
            {'cover_image': image_upload('cover.jpg', image_format='PNG')},
            format='multipart',
        )

        self.assertEqual(response.status_code, 400)

    def test_menu_image_rejects_corrupt_file(self):
        self.client.force_authenticate(self.merchant_user)

        response = self.client.post(
            f'/api/v1/merchants/restaurants/{self.restaurant.id}/items/',
            {
                'food_name': 'T-Food Bowl',
                'food_desc': 'Launch-safe upload test',
                'food_price': '100.00',
                'food_categ': 'Vegetarian',
                'image': SimpleUploadedFile(
                    'item.jpg',
                    b'not-an-image',
                    content_type='image/jpeg',
                ),
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, 400)

    def test_verification_document_upload_accepts_pdf_and_stays_private(self):
        self.client.force_authenticate(self.merchant_user)
        pdf = SimpleUploadedFile(
            'identity.pdf',
            b'%PDF-1.4\n% T-Food document\n',
            content_type='application/pdf',
        )

        response = self.client.post(
            '/api/v1/verifications/merchant/documents/',
            {'document_type': 'NATIONAL_ID', 'file': pdf},
            format='multipart',
        )

        self.assertEqual(response.status_code, 201)
        document = VerificationDocument.objects.get(id=response.data['id'])
        self.assertTrue(private_file_exists(document.file.name))
        self.assertFalse(response.data['file_url'].startswith('/media/'))

    def test_verification_document_rejects_executable_pdf(self):
        self.client.force_authenticate(self.merchant_user)
        fake = SimpleUploadedFile(
            'identity.pdf',
            b'MZnot-a-pdf',
            content_type='application/pdf',
        )

        response = self.client.post(
            '/api/v1/verifications/merchant/documents/',
            {'document_type': 'NATIONAL_ID', 'file': fake},
            format='multipart',
        )

        self.assertEqual(response.status_code, 400)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT, PRIVATE_MEDIA_ROOT=TEST_PRIVATE_MEDIA_ROOT)
class VerificationDocumentModelUploadTests(TestCase):
    def test_direct_model_upload_uses_private_document_validation(self):
        user = User.objects.create_user(username='model-upload-merchant')
        document = VerificationDocument.objects.create(
            user=user,
            subject_type=SUBJECT_MERCHANT,
            document_type='NATIONAL_ID',
            file=prepare_private_document_upload(
                SimpleUploadedFile(
                    '../../identity.pdf',
                    b'%PDF-1.4\n% T-Food model document\n',
                    content_type='application/pdf',
                )
            ),
        )

        self.assertTrue(private_file_exists(document.file.name))
        self.assertNotIn('..', document.file.name)

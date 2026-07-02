from decimal import Decimal
from io import BytesIO
import tempfile

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APITestCase

from markets.models import CommerceArea, CommerceCity, Market
from notifications.models import Notification
from operations_access.models import OperationsStaffMarketAccess, OperationsStaffProfile
from operations_access.permissions import MANAGE_SUPPORT, VIEW_SUPPORT
from orders.models import Order, OrderItem
from restaurants.image_validation import strip_review_photo_exif
from restaurants.notification_events import (
    schedule_review_photo_moderation_notification,
    schedule_review_photo_pending_notification,
)
from restaurants.models import FoodItem, Restaurant, RestaurantReview, ReviewPhoto


def review_test_image(name='review.jpg', image_format='JPEG', size=(24, 18)):
    buffer = BytesIO()
    image = Image.new('RGB', size, color='blue')
    image.save(buffer, format=image_format)
    content_type = {
        'JPEG': 'image/jpeg',
        'PNG': 'image/png',
        'WEBP': 'image/webp',
        'GIF': 'image/gif',
    }.get(image_format.upper(), 'application/octet-stream')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)


class RestaurantBranchFoundationTests(TestCase):
    def setUp(self):
        self.market = Market.objects.get(slug='india')
        self.owner = User.objects.create_user(username='branch-merchant')
        self.manager = User.objects.create_user(username='branch-manager')
        self.city = CommerceCity.objects.create(
            market=self.market,
            name='Bhubaneswar',
        )
        self.area = CommerceArea.objects.create(
            city=self.city,
            name='KIIT Area',
        )

    def create_branch(self, **overrides):
        defaults = {
            'market': self.market,
            'owner': self.owner,
            'rest_name': 'T-Food Test Kitchen',
            'rest_email': 'branch-kitchen@example.com',
            'rest_contact': '9000000000',
            'rest_address': 'Campus Road',
            'rest_city': 'Bhubaneswar',
            'pickup_latitude': Decimal('20.353000'),
            'pickup_longitude': Decimal('85.819000'),
            'is_active': True,
        }
        defaults.update(overrides)
        return Restaurant.objects.create(**defaults)

    def test_restaurant_defaults_to_food_branch_without_api_breaking_fields(self):
        branch = self.create_branch()

        self.assertEqual(branch.branch_name, branch.rest_name)
        self.assertEqual(branch.branch_type, Restaurant.BRANCH_TYPE_FOOD)
        self.assertEqual(branch.country_code, 'IN')
        self.assertEqual(branch.rest_city, 'Bhubaneswar')
        self.assertIsNotNone(branch.pickup_point)

    def test_branch_can_represent_non_food_commerce_unit(self):
        branch = self.create_branch(
            rest_email='grocery-branch@example.com',
            branch_name='KIIT Grocery Branch',
            branch_code='IN-BBI-KIIT-GROCERY',
            branch_type=Restaurant.BRANCH_TYPE_GROCERY,
            city_ref=self.city,
            area_ref=self.area,
            branch_manager=self.manager,
        )

        self.assertEqual(branch.branch_name, 'KIIT Grocery Branch')
        self.assertEqual(branch.branch_code, 'IN-BBI-KIIT-GROCERY')
        self.assertEqual(branch.branch_type, Restaurant.BRANCH_TYPE_GROCERY)
        self.assertEqual(branch.city_ref, self.city)
        self.assertEqual(branch.area_ref, self.area)
        self.assertEqual(branch.branch_manager, self.manager)

    def test_branch_country_code_is_normalized(self):
        branch = self.create_branch(
            rest_email='country-code-branch@example.com',
            country_code='in',
        )

        self.assertEqual(branch.country_code, 'IN')

    def test_branch_point_updates_when_old_coordinates_change(self):
        branch = self.create_branch(rest_email='point-sync-branch@example.com')
        original_point = str(branch.pickup_point)

        branch.pickup_latitude = Decimal('20.360000')
        branch.pickup_longitude = Decimal('85.830000')
        branch.save(update_fields=['pickup_latitude', 'pickup_longitude'])
        branch.refresh_from_db()

        self.assertIsNotNone(branch.pickup_point)
        self.assertNotEqual(str(branch.pickup_point), original_point)


class ReviewPhotoFoundationTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.TemporaryDirectory()
        self.media_override = override_settings(
            MEDIA_ROOT=self.media_root.name,
            PRIVATE_MEDIA_ROOT=self.media_root.name + '/private',
        )
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(self.media_root.cleanup)
        self.customer = User.objects.create_user(username='review-customer')
        self.other_customer = User.objects.create_user(username='other-review-customer')
        self.owner = User.objects.create_user(username='review-merchant')
        self.restaurant = Restaurant.objects.create(
            owner=self.owner,
            rest_name='Review Kitchen',
            rest_email='review-kitchen@example.com',
            rest_contact='9000000000',
            rest_address='Review Road',
            rest_city='',
            is_active=True,
        )
        self.food = FoodItem.objects.create(
            restaurant=self.restaurant,
            food_name='Review Pizza',
            food_desc='Photo friendly pizza',
            food_price=Decimal('199.00'),
            food_categ='Vegetarian',
        )
        self.order = self.create_order(self.customer, status='DELIVERED')
        self.review = RestaurantReview.objects.create(
            restaurant=self.restaurant,
            customer=self.customer,
            order=self.order,
            rating=5,
            comment='Great order',
        )

    def create_order(self, customer, status='DELIVERED'):
        order = Order.objects.create(
            customer=customer,
            status=status,
            total_amount=Decimal('199.00'),
        )
        OrderItem.objects.create(
            order=order,
            food=self.food,
            quantity=1,
            price=Decimal('199.00'),
            base_price=Decimal('199.00'),
        )
        return order

    def test_customer_can_create_review_photo_for_own_review(self):
        photo = ReviewPhoto.objects.create(
            review=self.review,
            uploaded_by=self.customer,
            image=review_test_image(),
            caption='Nice packaging',
        )

        self.assertEqual(photo.uploaded_by, self.customer)
        self.assertEqual(photo.status, ReviewPhoto.STATUS_PENDING)
        self.assertTrue(photo.image.name.startswith('reviews/photos/'))

    def test_default_status_is_pending(self):
        photo = ReviewPhoto.objects.create(
            review=self.review,
            uploaded_by=self.customer,
            image=review_test_image('pending.png', 'PNG'),
        )

        self.assertEqual(photo.status, ReviewPhoto.STATUS_PENDING)

    def test_customer_cannot_attach_photo_to_another_customer_review(self):
        with self.assertRaises(ValidationError):
            ReviewPhoto.objects.create(
                review=self.review,
                uploaded_by=self.other_customer,
                image=review_test_image('wrong-customer.jpg'),
            )

    def test_review_must_be_tied_to_delivered_order(self):
        pending_order = self.create_order(self.customer, status='PREPARING')
        pending_review = RestaurantReview.objects.create(
            restaurant=self.restaurant,
            customer=self.customer,
            order=pending_order,
            rating=4,
            comment='Not delivered yet',
        )

        with self.assertRaises(ValidationError):
            ReviewPhoto.objects.create(
                review=pending_review,
                uploaded_by=self.customer,
                image=review_test_image('pending-order.jpg'),
            )

    def test_multiple_photos_per_review_allowed(self):
        ReviewPhoto.objects.create(
            review=self.review,
            uploaded_by=self.customer,
            image=review_test_image('one.jpg'),
        )
        ReviewPhoto.objects.create(
            review=self.review,
            uploaded_by=self.customer,
            image=review_test_image('two.png', 'PNG'),
        )

        self.assertEqual(self.review.photos.count(), 2)

    def test_invalid_file_rejected(self):
        with self.assertRaises(ValidationError):
            ReviewPhoto.objects.create(
                review=self.review,
                uploaded_by=self.customer,
                image=SimpleUploadedFile(
                    'broken.jpg',
                    b'not-an-image',
                    content_type='image/jpeg',
                ),
            )

    def test_oversized_file_rejected(self):
        with self.assertRaises(ValidationError):
            ReviewPhoto.objects.create(
                review=self.review,
                uploaded_by=self.customer,
                image=SimpleUploadedFile(
                    'huge.jpg',
                    b'0' * ((5 * 1024 * 1024) + 1),
                    content_type='image/jpeg',
                ),
            )

    def test_exif_stripping_helper_does_not_crash(self):
        stripped = strip_review_photo_exif(review_test_image('plain.jpg'))

        self.assertTrue(stripped)

    def test_minimum_configuration_mode_works_without_market_or_location(self):
        Restaurant.objects.filter(id=self.restaurant.id).update(
            market=None,
            country_code='',
            city_ref=None,
            area_ref=None,
            pickup_latitude=None,
            pickup_longitude=None,
            pickup_point=None,
        )
        self.restaurant.refresh_from_db()
        photo = ReviewPhoto.objects.create(
            review=self.review,
            uploaded_by=self.customer,
            image=review_test_image('minimum.jpg'),
        )

        self.assertEqual(photo.review.restaurant.market_id, None)
        self.assertEqual(photo.status, ReviewPhoto.STATUS_PENDING)


class ReviewPhotoPublicReviewCompatibilityTests(APITestCase):
    def setUp(self):
        self.media_root = tempfile.TemporaryDirectory()
        self.media_override = override_settings(
            MEDIA_ROOT=self.media_root.name,
            PRIVATE_MEDIA_ROOT=self.media_root.name + '/private',
        )
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(self.media_root.cleanup)
        self.customer = User.objects.create_user(username='photo-api-customer')
        self.owner = User.objects.create_user(username='photo-api-owner')
        self.restaurant = Restaurant.objects.create(
            owner=self.owner,
            rest_name='Photo API Kitchen',
            rest_email='photo-api-kitchen@example.com',
            rest_contact='9000000000',
            rest_address='Photo API Road',
            rest_city='',
            is_active=True,
        )
        self.food = FoodItem.objects.create(
            restaurant=self.restaurant,
            food_name='Photo API Pizza',
            food_desc='Review photo item',
            food_price=Decimal('199.00'),
            food_categ='Vegetarian',
        )
        self.order = Order.objects.create(
            customer=self.customer,
            status='DELIVERED',
            total_amount=Decimal('199.00'),
        )
        OrderItem.objects.create(
            order=self.order,
            food=self.food,
            quantity=1,
            price=Decimal('199.00'),
            base_price=Decimal('199.00'),
        )
        self.review = RestaurantReview.objects.create(
            restaurant=self.restaurant,
            customer=self.customer,
            order=self.order,
            rating=5,
            comment='Public review',
        )
        ReviewPhoto.objects.create(
            review=self.review,
            uploaded_by=self.customer,
            image=review_test_image('pending-public.jpg'),
        )

    def test_pending_photos_are_not_returned_by_existing_public_review_api(self):
        response = self.client.get(f'/api/v1/restaurants/{self.restaurant.id}/reviews/')

        self.assertEqual(response.status_code, 200)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['photos'], [])


class ReviewPhotoApiTests(APITestCase):
    def setUp(self):
        self.media_root = tempfile.TemporaryDirectory()
        self.media_override = override_settings(
            MEDIA_ROOT=self.media_root.name,
            PRIVATE_MEDIA_ROOT=self.media_root.name + '/private',
        )
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(self.media_root.cleanup)
        self.customer = User.objects.create_user(username='review-photo-customer')
        self.other_customer = User.objects.create_user(username='review-photo-other')
        self.merchant = User.objects.create_user(username='review-photo-merchant')
        self.operator = User.objects.create_user(
            username='review-photo-operator',
            is_staff=True,
        )
        self.restaurant = Restaurant.objects.create(
            owner=self.merchant,
            rest_name='Photo Upload Kitchen',
            rest_email='photo-upload-kitchen@example.com',
            rest_contact='9000000000',
            rest_address='Photo Upload Road',
            rest_city='',
            is_active=True,
        )
        self.food = FoodItem.objects.create(
            restaurant=self.restaurant,
            food_name='Photo Upload Pizza',
            food_desc='Customer photo item',
            food_price=Decimal('199.00'),
            food_categ='Vegetarian',
        )
        self.order = self.create_order(self.customer, status='DELIVERED')
        self.review = RestaurantReview.objects.create(
            restaurant=self.restaurant,
            customer=self.customer,
            order=self.order,
            rating=5,
            comment='Photo upload review',
        )
        self.url = (
            f'/api/v1/restaurants/{self.restaurant.id}/reviews/'
            f'{self.review.id}/photos/'
        )

    def create_order(self, customer, status='DELIVERED'):
        order = Order.objects.create(
            customer=customer,
            status=status,
            total_amount=Decimal('199.00'),
        )
        OrderItem.objects.create(
            order=order,
            food=self.food,
            quantity=1,
            price=Decimal('199.00'),
            base_price=Decimal('199.00'),
        )
        return order

    def post_photo(self, user=None, image=None, url=None):
        self.client.force_authenticate(user or self.customer)
        return self.client.post(
            url or self.url,
            {
                'image': image or review_test_image('api-review.jpg'),
                'caption': 'Customer caption',
            },
            format='multipart',
        )

    def test_customer_uploads_photo_to_own_review(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.post_photo()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['status'], ReviewPhoto.STATUS_PENDING)
        self.assertIsNone(response.data['image_url'])
        self.assertEqual(ReviewPhoto.objects.count(), 1)
        notification = Notification.objects.get(
            user=self.operator,
            event_type='review_photo.pending',
        )
        self.assertEqual(notification.category, Notification.CATEGORY_SUPPORT)
        self.assertTrue(
            notification.idempotency_key.startswith(
                f'review-photo-pending:{response.data["id"]}'
            )
        )
        self.assertEqual(
            notification.action_url,
            '/operations?view=review-photo-moderation',
        )
        self.assertNotIn('image', notification.metadata)
        self.assertNotIn('image_url', notification.metadata)
        self.assertNotIn('file', notification.metadata)

    def test_uploaded_photo_defaults_to_pending(self):
        response = self.post_photo(image=review_test_image('pending-api.png', 'PNG'))

        self.assertEqual(response.status_code, 201)
        self.assertEqual(ReviewPhoto.objects.get().status, ReviewPhoto.STATUS_PENDING)

    def test_customer_cannot_upload_to_another_customer_review(self):
        response = self.post_photo(user=self.other_customer)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(ReviewPhoto.objects.count(), 0)

    def test_cannot_upload_photo_for_non_delivered_order_review(self):
        pending_order = self.create_order(self.customer, status='PREPARING')
        pending_review = RestaurantReview.objects.create(
            restaurant=self.restaurant,
            customer=self.customer,
            order=pending_order,
            rating=4,
            comment='Not delivered',
        )
        url = (
            f'/api/v1/restaurants/{self.restaurant.id}/reviews/'
            f'{pending_review.id}/photos/'
        )

        response = self.post_photo(url=url)

        self.assertEqual(response.status_code, 400)

    def test_invalid_image_rejected(self):
        response = self.post_photo(
            image=SimpleUploadedFile(
                'broken.jpg',
                b'not-an-image',
                content_type='image/jpeg',
            )
        )

        self.assertEqual(response.status_code, 400)

    def test_oversized_image_rejected(self):
        response = self.post_photo(
            image=SimpleUploadedFile(
                'huge.jpg',
                b'0' * ((5 * 1024 * 1024) + 1),
                content_type='image/jpeg',
            )
        )

        self.assertEqual(response.status_code, 400)

    def test_customer_can_list_own_pending_photos(self):
        photo = ReviewPhoto.objects.create(
            review=self.review,
            uploaded_by=self.customer,
            image=review_test_image('own-pending.jpg'),
        )
        self.client.force_authenticate(self.customer)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['id'], photo.id)
        self.assertEqual(response.data[0]['status'], ReviewPhoto.STATUS_PENDING)

    def test_review_photo_pending_notification_is_idempotent(self):
        photo = ReviewPhoto.objects.create(
            review=self.review,
            uploaded_by=self.customer,
            image=review_test_image('pending-notify-idempotent.jpg'),
        )

        with self.captureOnCommitCallbacks(execute=True):
            schedule_review_photo_pending_notification(photo, actor=self.customer)
        with self.captureOnCommitCallbacks(execute=True):
            schedule_review_photo_pending_notification(photo, actor=self.customer)

        self.assertEqual(
            Notification.objects.filter(
                user=self.operator,
                event_type='review_photo.pending',
            ).count(),
            1,
        )

    def test_review_photo_pending_notification_rollback_safe(self):
        try:
            with self.captureOnCommitCallbacks(execute=True):
                with transaction.atomic():
                    photo = ReviewPhoto.objects.create(
                        review=self.review,
                        uploaded_by=self.customer,
                        image=review_test_image('rolled-back-photo.jpg'),
                    )
                    schedule_review_photo_pending_notification(photo, actor=self.customer)
                    raise RuntimeError('rollback photo')
        except RuntimeError:
            pass

        self.assertFalse(
            Notification.objects.filter(event_type='review_photo.pending').exists()
        )

    def test_public_review_endpoint_returns_approved_photos_only(self):
        pending = ReviewPhoto.objects.create(
            review=self.review,
            uploaded_by=self.customer,
            image=review_test_image('pending-list.jpg'),
        )
        approved = ReviewPhoto.objects.create(
            review=self.review,
            uploaded_by=self.customer,
            image=review_test_image('approved-list.jpg'),
            status=ReviewPhoto.STATUS_APPROVED,
        )

        response = self.client.get(f'/api/v1/restaurants/{self.restaurant.id}/reviews/')

        self.assertEqual(response.status_code, 200)
        results = response.data.get('results', response.data)
        photo_ids = [item['id'] for item in results[0]['photos']]
        self.assertIn(approved.id, photo_ids)
        self.assertNotIn(pending.id, photo_ids)
        self.assertTrue(results[0]['photos'][0]['image_url'])

    def test_pending_photos_hidden_from_public_photo_endpoint(self):
        pending = ReviewPhoto.objects.create(
            review=self.review,
            uploaded_by=self.customer,
            image=review_test_image('pending-hidden.jpg'),
        )
        ReviewPhoto.objects.create(
            review=self.review,
            uploaded_by=self.customer,
            image=review_test_image('approved-visible.jpg'),
            status=ReviewPhoto.STATUS_APPROVED,
        )
        self.client.force_authenticate(user=None)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(pending.id, [item['id'] for item in response.data])

    def test_customer_can_delete_own_pending_photo(self):
        photo = ReviewPhoto.objects.create(
            review=self.review,
            uploaded_by=self.customer,
            image=review_test_image('delete-pending.jpg'),
        )
        self.client.force_authenticate(self.customer)

        response = self.client.delete(f'{self.url}{photo.id}/')

        self.assertEqual(response.status_code, 204)
        self.assertFalse(ReviewPhoto.objects.filter(id=photo.id).exists())

    def test_customer_cannot_delete_approved_photo(self):
        photo = ReviewPhoto.objects.create(
            review=self.review,
            uploaded_by=self.customer,
            image=review_test_image('delete-approved.jpg'),
            status=ReviewPhoto.STATUS_APPROVED,
        )
        self.client.force_authenticate(self.customer)

        response = self.client.delete(f'{self.url}{photo.id}/')

        self.assertEqual(response.status_code, 400)
        self.assertTrue(ReviewPhoto.objects.filter(id=photo.id).exists())

    def test_merchant_cannot_delete_customer_photo(self):
        photo = ReviewPhoto.objects.create(
            review=self.review,
            uploaded_by=self.customer,
            image=review_test_image('merchant-delete.jpg'),
        )
        self.client.force_authenticate(self.merchant)

        response = self.client.delete(f'{self.url}{photo.id}/')

        self.assertEqual(response.status_code, 403)
        self.assertTrue(ReviewPhoto.objects.filter(id=photo.id).exists())

    def test_existing_review_creation_api_still_works(self):
        other_order = self.create_order(self.customer, status='DELIVERED')
        self.client.force_authenticate(self.customer)

        response = self.client.post(
            f'/api/v1/restaurants/{self.restaurant.id}/reviews/',
            {
                'order_id': other_order.id,
                'rating': 4,
                'comment': 'Still works',
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertIn('photos', response.data)
        self.assertEqual(response.data['photos'], [])


class OperationsReviewPhotoModerationTests(APITestCase):
    def setUp(self):
        self.media_root = tempfile.TemporaryDirectory()
        self.media_override = override_settings(
            MEDIA_ROOT=self.media_root.name,
            PRIVATE_MEDIA_ROOT=self.media_root.name + '/private',
        )
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(self.media_root.cleanup)
        self.market = Market.objects.get(slug='india')
        self.city = CommerceCity.objects.create(
            market=self.market,
            name='Moderation City',
        )
        self.area = CommerceArea.objects.create(
            city=self.city,
            name='Moderation Area',
        )
        self.customer = User.objects.create_user(username='moderation-customer')
        self.merchant = User.objects.create_user(username='moderation-merchant')
        self.operator = User.objects.create_user(
            username='moderation-operator',
            is_staff=True,
        )
        self.country_operator = User.objects.create_user(
            username='moderation-country-operator',
            is_staff=True,
        )
        self.other_operator = User.objects.create_user(
            username='moderation-other-operator',
            is_staff=True,
        )
        self.restaurant = Restaurant.objects.create(
            owner=self.merchant,
            market=self.market,
            country_code='IN',
            city_ref=self.city,
            area_ref=self.area,
            rest_name='Moderation Kitchen',
            rest_email='moderation-kitchen@example.com',
            rest_contact='9000000000',
            rest_address='Moderation Road',
            rest_city='Moderation City',
            is_active=True,
        )
        self.food = FoodItem.objects.create(
            restaurant=self.restaurant,
            food_name='Moderation Pizza',
            food_desc='Photo moderation item',
            food_price=Decimal('199.00'),
            food_categ='Vegetarian',
        )
        self.order = Order.objects.create(
            customer=self.customer,
            status='DELIVERED',
            total_amount=Decimal('199.00'),
        )
        OrderItem.objects.create(
            order=self.order,
            food=self.food,
            quantity=1,
            price=Decimal('199.00'),
            base_price=Decimal('199.00'),
        )
        self.review = RestaurantReview.objects.create(
            restaurant=self.restaurant,
            customer=self.customer,
            order=self.order,
            rating=5,
            comment='Moderate this photo',
        )
        self.photo = ReviewPhoto.objects.create(
            review=self.review,
            uploaded_by=self.customer,
            image=review_test_image('moderation-pending.jpg'),
        )
        self.profile = OperationsStaffProfile.objects.create(
            user=self.country_operator,
            role=OperationsStaffProfile.ROLE_COUNTRY_ADMIN,
            status=OperationsStaffProfile.STATUS_ACTIVE,
            permissions=[VIEW_SUPPORT, MANAGE_SUPPORT],
        )
        OperationsStaffMarketAccess.objects.create(
            profile=self.profile,
            market=self.market,
            created_by=self.operator,
        )
        other_market = Market.objects.create(
            name='Other Moderation Market',
            slug='other-moderation-market',
            country_code='OM',
            default_currency=self.market.default_currency,
            is_active=True,
        )
        self.other_profile = OperationsStaffProfile.objects.create(
            user=self.other_operator,
            role=OperationsStaffProfile.ROLE_COUNTRY_ADMIN,
            status=OperationsStaffProfile.STATUS_ACTIVE,
            permissions=[VIEW_SUPPORT, MANAGE_SUPPORT],
        )
        OperationsStaffMarketAccess.objects.create(
            profile=self.other_profile,
            market=other_market,
            created_by=self.operator,
        )

    def test_operations_can_list_pending_photos(self):
        self.client.force_authenticate(self.operator)

        response = self.client.get('/api/v1/operations/review-photos/?status=PENDING')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.photo.id)
        self.assertEqual(response.data[0]['status'], ReviewPhoto.STATUS_PENDING)
        self.assertIn('/api/v1/restaurants/review-photos/', response.data[0]['image_preview_url'])

    def test_pending_photo_raw_media_path_is_not_public(self):
        response = self.client.get(f'/media/{self.photo.image.name}')

        self.assertEqual(response.status_code, 404)

    def test_authenticated_review_photo_preview_works_for_operations(self):
        self.client.force_authenticate(self.operator)

        response = self.client.get(
            f'/api/v1/restaurants/review-photos/{self.photo.id}/preview/'
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content)

    def test_unrelated_user_cannot_preview_pending_review_photo(self):
        unrelated = User.objects.create_user(username='unrelated-review-viewer')
        self.client.force_authenticate(unrelated)

        response = self.client.get(
            f'/api/v1/restaurants/review-photos/{self.photo.id}/preview/'
        )

        self.assertEqual(response.status_code, 403)

    def test_scoped_country_admin_sees_only_assigned_photos(self):
        self.client.force_authenticate(self.country_operator)

        response = self.client.get('/api/v1/operations/review-photos/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in response.data], [self.photo.id])

    def test_out_of_scope_photos_hidden(self):
        self.client.force_authenticate(self.other_operator)

        response = self.client.get('/api/v1/operations/review-photos/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_operations_can_approve_photo(self):
        self.client.force_authenticate(self.operator)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(
                f'/api/v1/operations/review-photos/{self.photo.id}/',
                {'action': 'APPROVE'},
                format='json',
            )

        self.assertEqual(response.status_code, 200)
        self.photo.refresh_from_db()
        self.assertEqual(self.photo.status, ReviewPhoto.STATUS_APPROVED)
        self.assertEqual(self.photo.moderation_reason, '')
        self.assertEqual(self.photo.reviewed_by, self.operator)
        self.assertIsNotNone(self.photo.reviewed_at)
        self.assertTrue(self.photo.image.name.startswith('reviews/photos/approved/'))
        notification = Notification.objects.get(
            user=self.customer,
            event_type='review_photo.approved',
        )
        self.assertEqual(
            notification.idempotency_key,
            f'review-photo-approved:{self.photo.id}',
        )
        self.assertEqual(notification.action_url, f'/restaurants/{self.restaurant.id}#reviews')
        self.assertNotIn('image', notification.metadata)
        self.assertNotIn('image_url', notification.metadata)

    def test_operations_can_reject_with_reason(self):
        self.client.force_authenticate(self.operator)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(
                f'/api/v1/operations/review-photos/{self.photo.id}/',
                {'action': 'REJECT', 'reason': 'Blurry image'},
                format='json',
            )

        self.assertEqual(response.status_code, 200)
        self.photo.refresh_from_db()
        self.assertEqual(self.photo.status, ReviewPhoto.STATUS_REJECTED)
        self.assertEqual(self.photo.moderation_reason, 'Blurry image')
        notification = Notification.objects.get(
            user=self.customer,
            event_type='review_photo.rejected',
        )
        self.assertEqual(notification.metadata['moderation_reason'], 'Blurry image')

    def test_operations_can_hide_with_reason(self):
        self.client.force_authenticate(self.operator)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(
                f'/api/v1/operations/review-photos/{self.photo.id}/',
                {'action': 'HIDE', 'reason': 'Customer privacy'},
                format='json',
            )

        self.assertEqual(response.status_code, 200)
        self.photo.refresh_from_db()
        self.assertEqual(self.photo.status, ReviewPhoto.STATUS_HIDDEN)
        self.assertEqual(self.photo.moderation_reason, 'Customer privacy')
        self.assertTrue(
            Notification.objects.filter(
                user=self.customer,
                event_type='review_photo.hidden',
            ).exists()
        )

    def test_review_photo_moderation_notification_is_idempotent(self):
        self.photo.status = ReviewPhoto.STATUS_APPROVED
        self.photo.reviewed_by = self.operator
        self.photo.reviewed_at = timezone.now()
        self.photo.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

        with self.captureOnCommitCallbacks(execute=True):
            schedule_review_photo_moderation_notification(
                self.photo,
                'APPROVE',
                actor=self.operator,
            )
        with self.captureOnCommitCallbacks(execute=True):
            schedule_review_photo_moderation_notification(
                self.photo,
                'APPROVE',
                actor=self.operator,
            )

        self.assertEqual(
            Notification.objects.filter(
                user=self.customer,
                event_type='review_photo.approved',
            ).count(),
            1,
        )

    def test_pending_notification_respects_operations_scope(self):
        with self.captureOnCommitCallbacks(execute=True):
            schedule_review_photo_pending_notification(
                self.photo,
                actor=self.customer,
            )

        self.assertTrue(
            Notification.objects.filter(
                user=self.country_operator,
                event_type='review_photo.pending',
            ).exists()
        )
        self.assertFalse(
            Notification.objects.filter(
                user=self.other_operator,
                event_type='review_photo.pending',
            ).exists()
        )

    def test_reject_and_hide_require_reason(self):
        self.client.force_authenticate(self.operator)

        reject = self.client.patch(
            f'/api/v1/operations/review-photos/{self.photo.id}/',
            {'action': 'REJECT'},
            format='json',
        )
        hide = self.client.patch(
            f'/api/v1/operations/review-photos/{self.photo.id}/',
            {'action': 'HIDE'},
            format='json',
        )

        self.assertEqual(reject.status_code, 400)
        self.assertEqual(hide.status_code, 400)

    def test_merchant_and_customer_cannot_moderate(self):
        for user in (self.merchant, self.customer):
            self.client.force_authenticate(user)
            list_response = self.client.get('/api/v1/operations/review-photos/')
            patch_response = self.client.patch(
                f'/api/v1/operations/review-photos/{self.photo.id}/',
                {'action': 'APPROVE'},
                format='json',
            )
            self.assertEqual(list_response.status_code, 403)
            self.assertEqual(patch_response.status_code, 403)

    def test_approved_photos_appear_in_public_review_response_only(self):
        rejected = ReviewPhoto.objects.create(
            review=self.review,
            uploaded_by=self.customer,
            image=review_test_image('moderation-rejected.jpg'),
            status=ReviewPhoto.STATUS_REJECTED,
        )
        hidden = ReviewPhoto.objects.create(
            review=self.review,
            uploaded_by=self.customer,
            image=review_test_image('moderation-hidden.jpg'),
            status=ReviewPhoto.STATUS_HIDDEN,
        )
        self.photo.status = ReviewPhoto.STATUS_APPROVED
        self.photo.reviewed_by = self.operator
        self.photo.reviewed_at = self.photo.created_at
        self.photo.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

        response = self.client.get(f'/api/v1/restaurants/{self.restaurant.id}/reviews/')

        self.assertEqual(response.status_code, 200)
        results = response.data.get('results', response.data)
        photo_ids = [photo['id'] for photo in results[0]['photos']]
        self.assertIn(self.photo.id, photo_ids)
        self.assertNotIn(rejected.id, photo_ids)
        self.assertNotIn(hidden.id, photo_ids)

    def test_minimum_configuration_mode_safe(self):
        bare_merchant = User.objects.create_user(username='bare-moderation-merchant')
        bare_customer = User.objects.create_user(username='bare-moderation-customer')
        bare_restaurant = Restaurant.objects.create(
            owner=bare_merchant,
            rest_name='Bare Moderation Branch',
            rest_email='bare-moderation@example.com',
            rest_contact='9000000001',
            rest_address='Bare Road',
            rest_city='',
            is_active=True,
        )
        bare_food = FoodItem.objects.create(
            restaurant=bare_restaurant,
            food_name='Bare Item',
            food_desc='No hierarchy item',
            food_price=Decimal('99.00'),
            food_categ='Vegetarian',
        )
        bare_order = Order.objects.create(
            customer=bare_customer,
            status='DELIVERED',
            total_amount=Decimal('99.00'),
        )
        OrderItem.objects.create(
            order=bare_order,
            food=bare_food,
            quantity=1,
            price=Decimal('99.00'),
            base_price=Decimal('99.00'),
        )
        bare_review = RestaurantReview.objects.create(
            restaurant=bare_restaurant,
            customer=bare_customer,
            order=bare_order,
            rating=4,
            comment='No hierarchy review',
        )
        bare_photo = ReviewPhoto.objects.create(
            review=bare_review,
            uploaded_by=bare_customer,
            image=review_test_image('bare-photo.jpg'),
        )
        self.client.force_authenticate(self.operator)

        response = self.client.get('/api/v1/operations/review-photos/')

        self.assertEqual(response.status_code, 200)
        self.assertIn(bare_photo.id, [item['id'] for item in response.data])

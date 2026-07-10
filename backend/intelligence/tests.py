from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image, features
from rest_framework.test import APITestCase

from customers.models import Customer, FavoriteRestaurant
from delivery.models import Delivery, DeliveryPartner
from intelligence.models import RecommendationEvent, SearchEvent, VisualSearchEvent
from intelligence.visual_search.providers.local_mock import LocalMockVisualLabelExtractor
from intelligence.visual_search.services import extract_visual_product_labels
from intelligence.visual_search.validators import (
    strip_image_exif,
    validate_visual_search_image,
)
from markets.models import CommerceArea, CommerceCity, Currency, Market
from operations_access.models import (
    OperationsStaffAreaAccess,
    OperationsStaffCityAccess,
    OperationsStaffMarketAccess,
    OperationsStaffProfile,
)
from orders.models import Order, OrderItem, OrderStatusEvent, SupportTicket
from payments.models import Payment
from restaurants.models import FoodItem, MerchantProfile, Restaurant, RestaurantReview


def visual_test_image(name='test.jpg', image_format='JPEG', size=(24, 18), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color=color)
    image.save(buffer, format=image_format)
    content_type = {
        'JPEG': 'image/jpeg',
        'PNG': 'image/png',
        'WEBP': 'image/webp',
        'GIF': 'image/gif',
    }.get(image_format.upper(), 'application/octet-stream')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)


class VisualSearchFoundationTests(TestCase):
    def test_valid_jpeg_accepted(self):
        image = visual_test_image('pizza_photo.jpg', 'JPEG')

        metadata = validate_visual_search_image(image)

        self.assertEqual(metadata['format'], 'JPEG')
        self.assertEqual(metadata['width'], 24)
        self.assertEqual(metadata['height'], 18)
        self.assertGreater(metadata['size_bytes'], 0)

    def test_valid_png_accepted(self):
        image = visual_test_image('medicine_tablet.png', 'PNG')

        metadata = validate_visual_search_image(image)

        self.assertEqual(metadata['format'], 'PNG')

    def test_valid_webp_accepted_if_supported(self):
        if not features.check('webp'):
            self.skipTest('Pillow WebP support is not available.')
        image = visual_test_image('rice_bag.webp', 'WEBP')

        metadata = validate_visual_search_image(image)

        self.assertEqual(metadata['format'], 'WEBP')

    def test_oversized_file_rejected_before_image_processing(self):
        image = SimpleUploadedFile(
            'huge.jpg',
            b'0' * ((5 * 1024 * 1024) + 1),
            content_type='image/jpeg',
        )

        with self.assertRaises(ValidationError):
            validate_visual_search_image(image)

    def test_corrupt_file_rejected(self):
        image = SimpleUploadedFile(
            'broken.jpg',
            b'not-an-image',
            content_type='image/jpeg',
        )

        with self.assertRaises(ValidationError):
            validate_visual_search_image(image)

    def test_malformed_png_rejected_without_server_error(self):
        broken_png = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
            b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde'
            b'\x00\x00\x00\rIDATx\x9cc\xfc\xcf\xc0P\x0f\x00'
            b'\x05\x83\x02\x7f\x97\xd9\xca\xca\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        image = SimpleUploadedFile(
            'broken.png',
            broken_png,
            content_type='image/png',
        )

        with self.assertRaises(ValidationError):
            validate_visual_search_image(image)

    def test_unsupported_file_rejected(self):
        image = visual_test_image('animated.gif', 'GIF')

        with self.assertRaises(ValidationError):
            validate_visual_search_image(image)

    def test_exif_stripping_does_not_crash(self):
        image = visual_test_image('plain.jpg', 'JPEG')

        stripped = strip_image_exif(image)

        self.assertTrue(stripped)

    def test_local_mock_extracts_pizza_labels(self):
        result = extract_visual_product_labels(visual_test_image('pizza_photo.jpg'))

        self.assertIn('pizza', result['labels'])
        self.assertIn('food', result['labels'])
        self.assertEqual(result['provider_code'], 'local_mock')
        self.assertIn('pizza', result['normalized_query'])

    def test_local_mock_extracts_medicine_pharmacy_labels(self):
        result = extract_visual_product_labels(
            visual_test_image('medicine_tablet.png', 'PNG')
        )

        self.assertIn('medicine', result['labels'])
        self.assertIn('tablet', result['labels'])
        self.assertIn('pharmacy', result['labels'])

    def test_local_mock_extracts_grocery_labels(self):
        image_format = 'WEBP' if features.check('webp') else 'PNG'
        name = 'rice_bag.webp' if image_format == 'WEBP' else 'rice_bag.png'

        result = extract_visual_product_labels(visual_test_image(name, image_format))

        self.assertIn('rice', result['labels'])
        self.assertIn('grocery', result['labels'])

    def test_fallback_product_label_works(self):
        result = extract_visual_product_labels(visual_test_image('unknown_object.jpg'))

        self.assertEqual(result['labels'], ['product'])
        self.assertEqual(result['normalized_query'], 'product')
        self.assertEqual(result['fallback_query'], 'product')
        self.assertGreaterEqual(result['confidence'], 0)
        self.assertLessEqual(result['confidence'], 1)

    def test_no_external_calls_happen(self):
        provider = LocalMockVisualLabelExtractor()

        self.assertFalse(provider.capabilities()['external_calls'])
        result = extract_visual_product_labels(visual_test_image('courier_package.jpg'))
        self.assertFalse(result['metadata']['external_calls'])

    def test_minimum_configuration_mode_without_market_or_branch(self):
        result = extract_visual_product_labels(
            visual_test_image('retail_shirt.jpg'),
            context={},
        )

        self.assertIn('retail', result['labels'])
        self.assertEqual(result['metadata']['image']['format'], 'JPEG')


class VisualProductSearchApiTests(APITestCase):
    endpoint = '/api/v1/intelligence/visual-product-search/'

    def create_branch(self, name, branch_type=Restaurant.BRANCH_TYPE_FOOD,
                      city='Bhubaneswar', market=None, latitude=None,
                      longitude=None):
        owner = User.objects.create_user(
            username=f'{name.lower().replace(" ", "-")}-owner',
            email=f'{name.lower().replace(" ", "-")}@example.com',
            password='pass12345',
        )
        return Restaurant.objects.create(
            owner=owner,
            market=market,
            rest_name=name,
            branch_name=name,
            branch_type=branch_type,
            rest_email=f'{name.lower().replace(" ", "-")}@branch.example.com',
            rest_contact='9999999999',
            rest_address=f'{name} address',
            rest_city=city,
            pickup_latitude=latitude,
            pickup_longitude=longitude,
            delivery_radius_km=Decimal('10.00'),
            is_active=True,
            is_open=True,
        )

    def create_market(self):
        currency, _created = Currency.objects.get_or_create(
            code='INR',
            defaults={'name': 'Indian Rupee'},
        )
        market, _created = Market.objects.get_or_create(
            slug='india',
            defaults={
                'name': 'India',
                'country_code': 'IN',
                'default_currency': currency,
            },
        )
        return market

    def post_image(self, image_name, image_format='JPEG', **data):
        payload = {
            'image': visual_test_image(image_name, image_format),
            **data,
        }
        return self.client.post(self.endpoint, payload, format='multipart')

    def test_valid_image_returns_labels_and_logs_event(self):
        response = self.post_image('pizza_photo.jpg')

        self.assertEqual(response.status_code, 200)
        self.assertIn('pizza', response.data['predicted_labels'])
        self.assertEqual(response.data['provider_code'], 'local_mock')
        self.assertEqual(response.data['image_metadata']['format'], 'JPEG')
        self.assertEqual(VisualSearchEvent.objects.count(), 1)

    def test_file_upload_alias_is_accepted(self):
        response = self.client.post(
            self.endpoint,
            {'file': visual_test_image('pizza_photo.jpg')},
            format='multipart',
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('pizza', response.data['predicted_labels'])

    def test_pizza_image_finds_pizza_item_and_branch(self):
        branch = self.create_branch('Pizza Palace')
        FoodItem.objects.create(
            restaurant=branch,
            food_name='Margherita Pizza',
            food_desc='Cheese pizza',
            food_price=Decimal('299.00'),
            food_categ='Vegetarian',
        )

        response = self.post_image('pizza_photo.jpg')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['matched_items'][0]['name'], 'Margherita Pizza')
        self.assertEqual(response.data['matched_merchants'][0]['branch_name'], 'Pizza Palace')

    def test_medicine_image_finds_pharmacy_branch_and_item(self):
        branch = self.create_branch(
            'Kaloum Pharmacy',
            branch_type=Restaurant.BRANCH_TYPE_PHARMACY,
        )
        FoodItem.objects.create(
            restaurant=branch,
            food_name='Medicine Tablet',
            food_desc='Basic pharmacy tablet',
            food_price=Decimal('49.00'),
            food_categ='Pharmacy',
        )

        response = self.post_image('medicine_tablet.png', 'PNG')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['matched_items'][0]['name'], 'Medicine Tablet')
        self.assertEqual(
            response.data['matched_merchants'][0]['branch_type'],
            Restaurant.BRANCH_TYPE_PHARMACY,
        )

    def test_grocery_image_finds_grocery_category_and_item(self):
        branch = self.create_branch(
            'Conakry Grocery',
            branch_type=Restaurant.BRANCH_TYPE_GROCERY,
        )
        FoodItem.objects.create(
            restaurant=branch,
            food_name='Premium Rice Bag',
            food_desc='Long grain rice grocery pack',
            food_price=Decimal('799.00'),
            food_categ='Grocery',
        )

        response = self.post_image('rice_bag.png', 'PNG')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['matched_items'][0]['name'], 'Premium Rice Bag')
        self.assertIn('grocery', [value.lower() for value in response.data['similar_categories']])

    def test_unknown_image_returns_fallback_and_empty_results_safely(self):
        response = self.post_image('unknown_object.jpg')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['fallback_query'], 'product')
        self.assertEqual(response.data['matched_items'], [])
        self.assertEqual(response.data['matched_merchants'], [])

    def test_invalid_image_rejected(self):
        response = self.client.post(
            self.endpoint,
            {
                'image': SimpleUploadedFile(
                    'broken.jpg',
                    b'not-an-image',
                    content_type='image/jpeg',
                )
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, 400)

    def test_oversized_image_rejected(self):
        response = self.client.post(
            self.endpoint,
            {
                'image': SimpleUploadedFile(
                    'huge.jpg',
                    b'0' * ((5 * 1024 * 1024) + 1),
                    content_type='image/jpeg',
                )
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, 400)

    def test_no_external_calls_or_public_image_returned(self):
        response = self.post_image('courier_package.jpg')

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('image_url', response.data)
        self.assertNotIn('raw_image', response.data)
        self.assertEqual(VisualSearchEvent.objects.first().provider_code, 'local_mock')

    def test_location_params_include_distance_and_serviceability(self):
        branch = self.create_branch(
            'Nearby Pizza',
            latitude=Decimal('20.296100'),
            longitude=Decimal('85.824500'),
        )
        FoodItem.objects.create(
            restaurant=branch,
            food_name='Pizza Slice',
            food_desc='Quick pizza',
            food_price=Decimal('99.00'),
            food_categ='Vegetarian',
        )

        response = self.post_image(
            'pizza_photo.jpg',
            latitude='20.296100',
            longitude='85.824500',
        )

        self.assertEqual(response.status_code, 200)
        merchant = response.data['matched_merchants'][0]
        self.assertIn('distance_km', merchant)
        self.assertIn('is_serviceable', merchant)
        self.assertEqual(merchant['distance_km'], '0.00')
        self.assertIs(merchant['is_serviceable'], True)
        event = VisualSearchEvent.objects.get()
        self.assertEqual(event.latitude, Decimal('20.296100'))
        self.assertEqual(event.longitude, Decimal('85.824500'))

    def test_no_market_country_city_area_does_not_crash(self):
        branch = self.create_branch('Minimum Pizza', city='')
        branch.country_code = ''
        branch.city_ref = None
        branch.area_ref = None
        branch.save(update_fields=['country_code', 'city_ref', 'area_ref'])
        FoodItem.objects.create(
            restaurant=branch,
            food_name='Minimum Pizza',
            food_desc='No geography configured',
            food_price=Decimal('199.00'),
            food_categ='Vegetarian',
        )

        response = self.post_image('pizza_photo.jpg')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['matched_items'][0]['name'], 'Minimum Pizza')

    def test_visual_search_event_logs_request(self):
        self.client.force_authenticate(
            User.objects.create_user(username='visual-customer', password='pass12345')
        )
        market = self.create_market()

        response = self.post_image(
            'unknown_object.jpg',
            market='india',
            category='retail',
        )

        self.assertEqual(response.status_code, 200)
        event = VisualSearchEvent.objects.get()
        self.assertEqual(event.user.username, 'visual-customer')
        self.assertEqual(event.market, market)
        self.assertEqual(event.country_code, 'IN')
        self.assertEqual(event.category, 'retail')
        self.assertEqual(event.result_count, 0)
        self.assertEqual(event.matched_item_count, 0)
        self.assertEqual(event.matched_merchant_count, 0)
        self.assertEqual(event.fallback_query, 'product')
        self.assertFalse(
            any(field.name == 'image' for field in VisualSearchEvent._meta.fields)
        )

    def test_existing_text_search_unchanged(self):
        branch = self.create_branch('Text Search Pizza')
        FoodItem.objects.create(
            restaurant=branch,
            food_name='Text Search Pizza',
            food_desc='Classic pizza',
            food_price=Decimal('199.00'),
            food_categ='Vegetarian',
        )

        response = self.client.get('/api/v1/restaurants/', {'search': 'pizza'})

        self.assertEqual(response.status_code, 200)
        results = response.data.get('results', response.data)
        self.assertIn('Text Search Pizza', [item['rest_name'] for item in results])


class IntelligenceEventTrackingTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='intelligence-user',
            email='intelligence@example.com',
            password='pass12345',
        )
        self.other_user = User.objects.create_user(
            username='spoofed-user',
            email='spoofed@example.com',
            password='pass12345',
        )

    def test_authenticated_user_can_create_search_event(self):
        self.client.force_authenticate(self.user)

        response = self.client.post('/api/v1/intelligence/search-events/', {
            'user': self.other_user.id,
            'query': ' biryani ',
            'category': ' dinner ',
            'latitude': '20.353100',
            'longitude': '85.826200',
            'result_count': 4,
        }, format='json')

        self.assertEqual(response.status_code, 201)
        event = SearchEvent.objects.get()
        self.assertEqual(event.user, self.user)
        self.assertEqual(event.query, 'biryani')
        self.assertEqual(event.category, 'dinner')
        self.assertEqual(event.result_count, 4)
        self.assertEqual(response.data['user'], self.user.id)

    def test_anonymous_search_event_is_allowed_without_private_user_data(self):
        response = self.client.post('/api/v1/intelligence/search-events/', {
            'query': 'pizza',
            'result_count': 0,
        }, format='json')

        self.assertEqual(response.status_code, 201)
        event = SearchEvent.objects.get()
        self.assertIsNone(event.user)
        self.assertIsNone(response.data['user'])
        self.assertNotIn('email', response.data)

    def test_create_recommendation_impression(self):
        self.client.force_authenticate(self.user)

        response = self.client.post('/api/v1/intelligence/events/', {
            'surface': 'home',
            'object_type': 'restaurant',
            'object_id': '42',
            'action': 'impression',
            'score': '0.7500',
            'reason_codes': ['nearby', 'popular'],
        }, format='json')

        self.assertEqual(response.status_code, 201)
        event = RecommendationEvent.objects.get()
        self.assertEqual(event.user, self.user)
        self.assertEqual(event.action, RecommendationEvent.ACTION_IMPRESSION)
        self.assertEqual(event.reason_codes, ['nearby', 'popular'])

    def test_create_recommendation_click(self):
        self.client.force_authenticate(self.user)

        response = self.client.post('/api/v1/intelligence/events/', {
            'surface': 'search_results',
            'object_type': 'food_item',
            'object_id': '99',
            'action': 'click',
            'reason_codes': [],
        }, format='json')

        self.assertEqual(response.status_code, 201)
        event = RecommendationEvent.objects.get()
        self.assertEqual(event.action, RecommendationEvent.ACTION_CLICK)

    def test_invalid_recommendation_action_is_rejected(self):
        self.client.force_authenticate(self.user)

        response = self.client.post('/api/v1/intelligence/events/', {
            'surface': 'home',
            'object_type': 'restaurant',
            'object_id': '42',
            'action': 'share',
        }, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(RecommendationEvent.objects.count(), 0)

    def test_spoofed_recommendation_user_is_ignored(self):
        self.client.force_authenticate(self.user)

        response = self.client.post('/api/v1/intelligence/events/', {
            'user': self.other_user.id,
            'surface': 'home',
            'object_type': 'restaurant',
            'object_id': '42',
            'action': 'click',
        }, format='json')

        self.assertEqual(response.status_code, 201)
        event = RecommendationEvent.objects.get()
        self.assertEqual(event.user, self.user)
        self.assertEqual(response.data['user'], self.user.id)

    def test_reason_codes_must_be_a_list(self):
        self.client.force_authenticate(self.user)

        response = self.client.post('/api/v1/intelligence/events/', {
            'surface': 'home',
            'object_type': 'restaurant',
            'object_id': '42',
            'action': 'click',
            'reason_codes': 'nearby',
        }, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(RecommendationEvent.objects.count(), 0)

    def test_event_endpoints_do_not_touch_order_payment_or_dispatch_models(self):
        before_counts = {
            'orders': Order.objects.count(),
            'payments': Payment.objects.count(),
            'deliveries': Delivery.objects.count(),
        }

        self.client.force_authenticate(self.user)
        recommendation = self.client.post('/api/v1/intelligence/events/', {
            'surface': 'home',
            'object_type': 'restaurant',
            'object_id': '42',
            'action': 'impression',
        }, format='json')
        search = self.client.post('/api/v1/intelligence/search-events/', {
            'query': 'burger',
            'result_count': 3,
        }, format='json')

        self.assertEqual(recommendation.status_code, 201)
        self.assertEqual(search.status_code, 201)
        self.assertEqual(Order.objects.count(), before_counts['orders'])
        self.assertEqual(Payment.objects.count(), before_counts['payments'])
        self.assertEqual(Delivery.objects.count(), before_counts['deliveries'])


class CustomerRecommendationTests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username='recommendation-customer',
            password='pass12345',
        )
        self.other_customer = User.objects.create_user(
            username='recommendation-other',
            password='pass12345',
        )
        self.favorite_restaurant = self.create_restaurant(
            'Favorite Bowl',
            'favorite@example.com',
            latitude='20.353100',
            longitude='85.826200',
        )
        self.ordered_restaurant = self.create_restaurant(
            'Order Again Kitchen',
            'ordered@example.com',
            latitude='20.354000',
            longitude='85.827000',
        )
        self.top_rated_restaurant = self.create_restaurant(
            'Five Star Bites',
            'rated@example.com',
            latitude='20.355000',
            longitude='85.828000',
        )
        self.popular_restaurant = self.create_restaurant(
            'Popular Plates',
            'popular@example.com',
            latitude='20.356000',
            longitude='85.829000',
        )
        self.inactive_restaurant = self.create_restaurant(
            'Hidden Closed Cafe',
            'inactive@example.com',
            is_active=False,
        )
        self.favorite_item = self.create_item(self.favorite_restaurant, 'Paneer Bowl')
        self.ordered_item = self.create_item(self.ordered_restaurant, 'Rice Meal')
        self.top_rated_item = self.create_item(self.top_rated_restaurant, 'Dosa')
        self.popular_item = self.create_item(self.popular_restaurant, 'Roll')
        self.inactive_item = self.create_item(self.inactive_restaurant, 'Hidden Snack')

    def create_restaurant(
        self,
        name,
        email,
        latitude=None,
        longitude=None,
        is_active=True,
        is_open=True,
    ):
        return Restaurant.objects.create(
            rest_name=name,
            rest_email=email,
            rest_contact='9999999999',
            rest_address='KIIT Road',
            rest_city='Bhubaneswar',
            pickup_latitude=latitude,
            pickup_longitude=longitude,
            delivery_radius_km=10,
            estimated_prep_minutes=20,
            is_active=is_active,
            is_open=is_open,
        )

    def create_item(self, restaurant, name, category='Vegetarian'):
        return FoodItem.objects.create(
            restaurant=restaurant,
            food_name=name,
            food_desc='Test item',
            food_price='120.00',
            food_categ=category,
            is_available=True,
        )

    def create_delivered_order(self, user, item, quantity=1):
        order = Order.objects.create(
            customer=user,
            status='DELIVERED',
            total_amount='150.00',
        )
        OrderItem.objects.create(
            order=order,
            food=item,
            quantity=quantity,
            price='120.00',
            base_price='120.00',
        )
        return order

    def restaurants_in_section(self, response, section):
        return [
            item['restaurant']['rest_name']
            for item in response.data[section]
        ]

    def recommendation_for(self, response, section, restaurant_name):
        for item in response.data[section]:
            if item['restaurant']['rest_name'] == restaurant_name:
                return item
        return None

    def test_favorite_restaurant_gets_boost(self):
        FavoriteRestaurant.objects.create(
            user=self.customer,
            restaurant=self.favorite_restaurant,
        )
        self.client.force_authenticate(self.customer)

        response = self.client.get('/api/v1/intelligence/customer/recommendations/')

        self.assertEqual(response.status_code, 200)
        first = response.data['recommended_for_you'][0]
        self.assertEqual(first['restaurant']['rest_name'], 'Favorite Bowl')
        self.assertIn('favorite', first['reason_codes'])
        self.assertEqual(first['reason_label'], 'Matches your favorites')

    def test_previously_ordered_restaurant_appears_in_order_again(self):
        self.create_delivered_order(self.customer, self.ordered_item, quantity=2)
        self.client.force_authenticate(self.customer)

        response = self.client.get('/api/v1/intelligence/customer/recommendations/')

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'Order Again Kitchen',
            self.restaurants_in_section(response, 'order_again'),
        )
        item = self.recommendation_for(
            response,
            'order_again',
            'Order Again Kitchen',
        )
        self.assertIn('ordered_before', item['reason_codes'])

    def test_top_rated_restaurant_appears_in_top_rated(self):
        order = self.create_delivered_order(self.other_customer, self.top_rated_item)
        RestaurantReview.objects.create(
            restaurant=self.top_rated_restaurant,
            customer=self.other_customer,
            order=order,
            rating=5,
            comment='Excellent.',
        )

        response = self.client.get('/api/v1/intelligence/customer/recommendations/')

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'Five Star Bites',
            self.restaurants_in_section(response, 'top_rated'),
        )
        item = self.recommendation_for(response, 'top_rated', 'Five Star Bites')
        self.assertIn('top_rated', item['reason_codes'])

    def test_popular_restaurant_appears_in_popular_near_you(self):
        self.create_delivered_order(self.other_customer, self.popular_item)
        self.create_delivered_order(self.customer, self.popular_item)

        response = self.client.get(
            '/api/v1/intelligence/customer/recommendations/'
            '?latitude=20.353500&longitude=85.826500'
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'Popular Plates',
            self.restaurants_in_section(response, 'popular_near_you'),
        )
        item = self.recommendation_for(
            response,
            'popular_near_you',
            'Popular Plates',
        )
        self.assertIn('popular', item['reason_codes'])

    def test_inactive_restaurant_is_not_recommended(self):
        FavoriteRestaurant.objects.create(
            user=self.customer,
            restaurant=self.inactive_restaurant,
        )
        self.client.force_authenticate(self.customer)

        response = self.client.get('/api/v1/intelligence/customer/recommendations/')

        self.assertEqual(response.status_code, 200)
        for section in response.data.values():
            names = [item['restaurant']['rest_name'] for item in section]
            self.assertNotIn('Hidden Closed Cafe', names)

    def test_location_aware_recommendations_include_distance_and_serviceability(self):
        response = self.client.get(
            '/api/v1/intelligence/customer/recommendations/'
            '?latitude=20.353500&longitude=85.826500'
        )

        self.assertEqual(response.status_code, 200)
        item = response.data['recommended_for_you'][0]
        self.assertIn('distance_km', item['restaurant'])
        self.assertIn('is_serviceable', item['restaurant'])
        self.assertIsNotNone(item['restaurant']['distance_km'])
        self.assertIs(item['restaurant']['is_serviceable'], True)
        self.assertTrue(
            item['reason_codes'],
            'recommendations should explain why they were returned',
        )

    def test_anonymous_user_receives_generic_recommendations(self):
        response = self.client.get('/api/v1/intelligence/customer/recommendations/')

        self.assertEqual(response.status_code, 200)
        self.assertIn('recommended_for_you', response.data)
        self.assertGreater(len(response.data['recommended_for_you']), 0)
        self.assertEqual(response.data['order_again'], [])

    def test_response_contains_reason_codes_and_labels(self):
        response = self.client.get('/api/v1/intelligence/customer/recommendations/')

        self.assertEqual(response.status_code, 200)
        item = response.data['recommended_for_you'][0]
        self.assertIn('score', item)
        self.assertIn('reason_codes', item)
        self.assertIn('reason_label', item)
        self.assertIsInstance(item['reason_codes'], list)
        self.assertTrue(item['reason_label'])


class MerchantIntelligenceTests(APITestCase):
    def setUp(self):
        self.merchant = User.objects.create_user(
            username='merchant-intel',
            password='pass12345',
        )
        self.other_merchant = User.objects.create_user(
            username='other-merchant-intel',
            password='pass12345',
        )
        self.customer = User.objects.create_user(
            username='merchant-insight-customer',
            password='pass12345',
        )
        self.non_merchant = User.objects.create_user(
            username='not-a-merchant',
            password='pass12345',
        )
        MerchantProfile.objects.create(
            user=self.merchant,
            business_name='Insight Foods',
            is_verified=True,
        )
        MerchantProfile.objects.create(
            user=self.other_merchant,
            business_name='Other Foods',
            is_verified=True,
        )
        self.restaurant = self.create_restaurant(
            self.merchant,
            'Insight Kitchen',
            'insight-kitchen@example.com',
        )
        self.other_restaurant = self.create_restaurant(
            self.other_merchant,
            'Other Kitchen',
            'other-kitchen@example.com',
        )
        self.best_item = self.create_item(self.restaurant, 'Chicken Biryani')
        self.zero_sale_item = self.create_item(self.restaurant, 'Quiet Salad')
        self.unavailable_item = self.create_item(
            self.restaurant,
            'Sold Out Shake',
            is_available=False,
        )
        self.other_item = self.create_item(self.other_restaurant, 'Other Roll')

    def create_restaurant(self, owner, name, email):
        return Restaurant.objects.create(
            owner=owner,
            rest_name=name,
            rest_email=email,
            rest_contact='9999999999',
            rest_address='KIIT Road',
            rest_city='Bhubaneswar',
            estimated_prep_minutes=20,
            is_active=True,
            is_open=True,
        )

    def create_item(self, restaurant, name, is_available=True):
        return FoodItem.objects.create(
            restaurant=restaurant,
            food_name=name,
            food_desc='Test item',
            food_price='160.00',
            food_categ='Non-Vegetarian',
            is_available=is_available,
        )

    def create_order(self, item, status='DELIVERED', quantity=1, customer=None):
        order = Order.objects.create(
            customer=customer or self.customer,
            status=status,
            total_amount='220.00',
            merchant_payout='180.00',
        )
        OrderItem.objects.create(
            order=order,
            food=item,
            quantity=quantity,
            price='160.00',
            base_price='160.00',
        )
        return order

    def add_status_timeline(self, order, ready_minutes=45):
        now = timezone.now()
        confirmed = OrderStatusEvent.objects.create(
            order=order,
            status='CONFIRMED',
            source='MERCHANT',
            description='Confirmed',
        )
        preparing = OrderStatusEvent.objects.create(
            order=order,
            status='PREPARING',
            source='MERCHANT',
            description='Preparing',
        )
        ready = OrderStatusEvent.objects.create(
            order=order,
            status='READY_FOR_PICKUP',
            source='MERCHANT',
            description='Ready',
        )
        OrderStatusEvent.objects.filter(id=confirmed.id).update(
            created_at=now
        )
        OrderStatusEvent.objects.filter(id=preparing.id).update(
            created_at=now + timedelta(minutes=5)
        )
        OrderStatusEvent.objects.filter(id=ready.id).update(
            created_at=now + timedelta(minutes=5 + ready_minutes)
        )

    def get_insights(self):
        self.client.force_authenticate(self.merchant)
        return self.client.get('/api/v1/intelligence/merchant/insights/')

    def test_merchant_can_only_see_own_insights(self):
        self.create_order(self.best_item, quantity=2)
        self.create_order(self.other_item, quantity=10)

        response = self.get_insights()

        self.assertEqual(response.status_code, 200)
        names = [
            item['name']
            for item in response.data['sales_insights']['best_selling_items']
        ]
        self.assertIn('Chicken Biryani', names)
        self.assertNotIn('Other Roll', names)

    def test_non_merchant_cannot_access_insights(self):
        self.client.force_authenticate(self.non_merchant)

        response = self.client.get('/api/v1/intelligence/merchant/insights/')

        self.assertEqual(response.status_code, 403)

    def test_best_selling_item_computed_correctly(self):
        self.create_order(self.best_item, quantity=3)

        response = self.get_insights()

        self.assertEqual(response.status_code, 200)
        best = response.data['sales_insights']['best_selling_items'][0]
        self.assertEqual(best['name'], 'Chicken Biryani')
        self.assertEqual(best['quantity'], 3)

    def test_zero_sale_and_unavailable_items_appear(self):
        self.create_order(self.best_item, quantity=1)

        response = self.get_insights()

        self.assertEqual(response.status_code, 200)
        zero_sale_names = [
            item['name']
            for item in response.data['menu_insights']['items_with_zero_sales']
        ]
        unavailable_names = [
            item['name']
            for item in response.data['menu_insights']['unavailable_items']
        ]
        self.assertIn('Quiet Salad', zero_sale_names)
        self.assertIn('Sold Out Shake', unavailable_names)

    def test_cancellation_warning_appears_when_rate_is_high(self):
        self.create_order(self.best_item, status='DELIVERED')
        self.create_order(self.best_item, status='CANCELLED')
        self.create_order(self.best_item, status='CANCELLED')

        response = self.get_insights()

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(
            response.data['operations_insights']['cancellation_rate'],
            20,
        )
        actions = response.data['action_recommendations']
        self.assertTrue(any('cancellations' in action.lower() for action in actions))

    def test_rating_issue_appears_when_reviews_are_low(self):
        order = self.create_order(self.best_item, status='DELIVERED')
        RestaurantReview.objects.create(
            restaurant=self.restaurant,
            customer=self.customer,
            order=order,
            rating=2,
            comment='Food was cold.',
        )

        response = self.get_insights()

        self.assertEqual(response.status_code, 200)
        issues = response.data['customer_insights']['recent_review_issues']
        self.assertEqual(issues[0]['rating'], 2)
        self.assertIn('Food was cold.', issues[0]['comment'])
        self.assertTrue(
            any('low ratings' in action.lower() for action in response.data['action_recommendations'])
        )

    def test_slow_prep_warning_uses_status_timeline(self):
        order = self.create_order(self.best_item, status='DELIVERED')
        self.add_status_timeline(order, ready_minutes=45)

        response = self.get_insights()

        self.assertEqual(response.status_code, 200)
        warnings = response.data['operations_insights']['slow_prep_warnings']
        self.assertTrue(warnings)
        self.assertEqual(warnings[0]['code'], 'prep_above_estimate')

    def test_endpoint_works_when_merchant_has_no_orders(self):
        response = self.get_insights()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['sales_insights']['best_selling_items'], [])
        self.assertEqual(
            response.data['sales_insights']['average_order_value'],
            Decimal('0.00'),
        )
        self.assertTrue(response.data['action_recommendations'])


class OperationsIntelligenceTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='ops-admin',
            password='pass12345',
            is_staff=True,
        )
        self.non_admin = User.objects.create_user(
            username='ops-not-admin',
            password='pass12345',
        )
        self.customer = User.objects.create_user(
            username='ops-customer',
            password='pass12345',
        )
        Customer.objects.create(user=self.customer)
        self.merchant_user = User.objects.create_user(
            username='ops-merchant',
            password='pass12345',
        )
        MerchantProfile.objects.create(
            user=self.merchant_user,
            business_name='Ops Biryani',
            is_verified=True,
        )
        self.restaurant = Restaurant.objects.create(
            owner=self.merchant_user,
            rest_name='Ops Biryani House',
            rest_email='ops-biryani@example.com',
            rest_contact='9999999999',
            rest_address='KIIT Road',
            rest_city='KIIT',
            is_active=True,
            is_open=True,
            estimated_prep_minutes=20,
        )
        self.food = FoodItem.objects.create(
            restaurant=self.restaurant,
            food_name='Ops Chicken Biryani',
            food_desc='Test item',
            food_price='180.00',
            food_categ='Non-Vegetarian',
            is_available=True,
        )
        self.partner_user = User.objects.create_user(
            username='ops-partner',
            password='pass12345',
        )
        self.partner = DeliveryPartner.objects.create(
            user=self.partner_user,
            partner_name='Ops Partner',
            partner_phone='9999999998',
            transport_details='Bike',
            is_available=True,
            is_verified=True,
        )

    def create_order(self, status='DELIVERED', created_minutes_ago=10):
        order = Order.objects.create(
            customer=self.customer,
            status=status,
            delivery_address='KIIT Square',
            total_amount='250.00',
            merchant_payout='200.00',
        )
        OrderItem.objects.create(
            order=order,
            food=self.food,
            quantity=1,
            price='180.00',
            base_price='180.00',
        )
        Order.objects.filter(id=order.id).update(
            created_at=timezone.now() - timedelta(minutes=created_minutes_ago)
        )
        order.refresh_from_db()
        return order

    def add_status_event(self, order, status, minutes_after_created):
        event = OrderStatusEvent.objects.create(
            order=order,
            status=status,
            source='SYSTEM',
            description=status,
        )
        OrderStatusEvent.objects.filter(id=event.id).update(
            created_at=order.created_at + timedelta(minutes=minutes_after_created)
        )

    def get_insights(self):
        self.client.force_authenticate(self.admin)
        return self.client.get('/api/v1/intelligence/operations/insights/')

    def create_scoped_marketplace(self):
        currency_a = Currency.objects.create(
            code='XGA',
            numeric_code='901',
            name='Scope Currency A',
        )
        currency_b = Currency.objects.create(
            code='XGB',
            numeric_code='902',
            name='Scope Currency B',
        )
        market_a = Market.objects.create(
            slug='scope-market-a',
            name='Scope Market A',
            country_code='XA',
            default_currency=currency_a,
        )
        market_b = Market.objects.create(
            slug='scope-market-b',
            name='Scope Market B',
            country_code='XB',
            default_currency=currency_b,
        )
        city_a = CommerceCity.objects.create(
            market=market_a,
            name='Scope City A',
            slug='scope-city-a',
        )
        area_a = CommerceArea.objects.create(
            market=market_a,
            city=city_a,
            name='Scope Area A',
            slug='scope-area-a',
        )
        self.restaurant.market = market_a
        self.restaurant.country_code = 'XA'
        self.restaurant.city_ref = city_a
        self.restaurant.area_ref = area_a
        self.restaurant.save(update_fields=['market', 'country_code', 'city_ref', 'area_ref', 'updated_at'])

        other_customer = User.objects.create_user(username='scope-other-customer')
        Customer.objects.create(user=other_customer)
        other_merchant_user = User.objects.create_user(username='scope-other-merchant')
        MerchantProfile.objects.create(
            user=other_merchant_user,
            business_name='Outside Merchant',
            is_verified=True,
        )
        other_restaurant = Restaurant.objects.create(
            owner=other_merchant_user,
            market=market_b,
            country_code='XB',
            rest_name='Outside Restaurant',
            rest_email='outside-scope@example.com',
            rest_contact='8888888888',
            rest_address='Outside Road',
            rest_city='Outside',
            is_active=True,
            is_open=True,
        )
        other_food = FoodItem.objects.create(
            restaurant=other_restaurant,
            food_name='Outside Meal',
            food_desc='Outside item',
            food_price='100.00',
            food_categ='Vegetarian',
            is_available=True,
        )
        outside_order = Order.objects.create(
            customer=other_customer,
            market=market_b,
            pickup_branch=other_restaurant,
            status='DELIVERED',
            delivery_address='Outside Street',
            total_amount='120.00',
            merchant_payout='90.00',
        )
        OrderItem.objects.create(
            order=outside_order,
            food=other_food,
            quantity=1,
            price='100.00',
            base_price='100.00',
        )
        scoped_order = self.create_order(status='DELIVERED')
        scoped_order.market = market_a
        scoped_order.pickup_branch = self.restaurant
        scoped_order.save(update_fields=['market', 'pickup_branch', 'updated_at'])
        return market_a, market_b, city_a, area_a

    def create_operations_profile(self, role, username, *, market=None, city=None, area=None):
        user = User.objects.create_user(username=username, is_staff=True)
        profile = OperationsStaffProfile.objects.create(
            user=user,
            role=role,
            status=OperationsStaffProfile.STATUS_ACTIVE,
        )
        if market:
            OperationsStaffMarketAccess.objects.create(profile=profile, market=market)
        if city:
            OperationsStaffCityAccess.objects.create(profile=profile, city=city)
        if area:
            OperationsStaffAreaAccess.objects.create(profile=profile, area=area)
        return user

    def test_operations_users_can_access(self):
        response = self.get_insights()

        self.assertEqual(response.status_code, 200)
        self.assertIn('marketplace_health', response.data)
        self.assertEqual(response.data['marketplace_health']['active_restaurants'], 1)

    def test_non_operations_users_cannot_access(self):
        self.client.force_authenticate(self.non_admin)

        response = self.client.get('/api/v1/intelligence/operations/insights/')

        self.assertEqual(response.status_code, 403)

    def test_country_admin_gets_only_assigned_market_insights(self):
        market_a, market_b, _, _ = self.create_scoped_marketplace()
        VisualSearchEvent.objects.create(
            provider_code='local_mock',
            labels=['rice'],
            normalized_query='rice',
            fallback_query='rice',
            confidence=Decimal('0.7000'),
            market=market_a,
            country_code='XA',
            result_count=1,
            matched_item_count=1,
            matched_merchant_count=0,
        )
        VisualSearchEvent.objects.create(
            provider_code='local_mock',
            labels=['outside'],
            normalized_query='outside',
            fallback_query='outside',
            confidence=Decimal('0.7000'),
            market=market_b,
            country_code='XB',
            result_count=1,
            matched_item_count=1,
            matched_merchant_count=0,
        )
        user = self.create_operations_profile(
            OperationsStaffProfile.ROLE_COUNTRY_ADMIN,
            'insights-country-admin',
            market=market_a,
        )
        self.client.force_authenticate(user)

        response = self.client.get('/api/v1/intelligence/operations/insights/')
        outside_response = self.client.get('/api/v1/intelligence/operations/insights/', {
            'market': market_b.id,
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['marketplace_health']['active_restaurants'], 1)
        self.assertIn('1 merchants', response.data['marketplace_health']['marketplace_growth_summary'])
        self.assertEqual(
            response.data['visual_search_intelligence']['total_visual_searches'],
            1,
        )
        self.assertEqual(outside_response.status_code, 200)
        self.assertEqual(outside_response.data['marketplace_health']['active_restaurants'], 0)
        self.assertEqual(
            outside_response.data['visual_search_intelligence']['total_visual_searches'],
            0,
        )

    def test_city_and_area_admin_get_only_assigned_scope_insights(self):
        _, _, city_a, area_a = self.create_scoped_marketplace()
        city_user = self.create_operations_profile(
            OperationsStaffProfile.ROLE_CITY_ADMIN,
            'insights-city-admin',
            city=city_a,
        )
        area_user = self.create_operations_profile(
            OperationsStaffProfile.ROLE_AREA_ADMIN,
            'insights-area-admin',
            area=area_a,
        )

        self.client.force_authenticate(city_user)
        city_response = self.client.get('/api/v1/intelligence/operations/insights/', {
            'city': city_a.id,
        })
        self.client.force_authenticate(area_user)
        area_response = self.client.get('/api/v1/intelligence/operations/insights/', {
            'area': area_a.id,
        })

        self.assertEqual(city_response.status_code, 200)
        self.assertEqual(city_response.data['marketplace_health']['active_restaurants'], 1)
        self.assertEqual(area_response.status_code, 200)
        self.assertEqual(area_response.data['marketplace_health']['active_restaurants'], 1)

    def test_missing_market_city_and_area_does_not_crash_scoped_insights(self):
        user = self.create_operations_profile(
            OperationsStaffProfile.ROLE_CITY_ADMIN,
            'insights-empty-city-admin',
        )
        self.client.force_authenticate(user)

        response = self.client.get('/api/v1/intelligence/operations/insights/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['marketplace_health']['active_restaurants'], 0)
        self.assertEqual(response.data['order_intelligence']['delayed_orders'], [])

    def test_delayed_order_calculation(self):
        order = self.create_order(status='PREPARING', created_minutes_ago=90)

        response = self.get_insights()

        self.assertEqual(response.status_code, 200)
        delayed = response.data['order_intelligence']['delayed_orders']
        self.assertEqual(delayed[0]['order_id'], order.id)
        self.assertGreaterEqual(delayed[0]['age_minutes'], 45)

    def test_cancellation_calculations(self):
        self.create_order(status='DELIVERED')
        self.create_order(status='CANCELLED')

        response = self.get_insights()

        areas = response.data['order_intelligence']['high_cancellation_areas']
        self.assertEqual(areas[0]['area'], 'KIIT')
        self.assertEqual(areas[0]['cancelled_orders'], 1)

    def test_merchant_ranking(self):
        self.create_order(status='DELIVERED')
        self.create_order(status='CANCELLED')
        self.create_order(status='CANCELLED')

        response = self.get_insights()

        merchants = response.data['merchant_intelligence']['high_cancellation_merchants']
        self.assertEqual(merchants[0]['name'], 'Ops Biryani')
        self.assertGreaterEqual(merchants[0]['cancellation_rate'], 20)

    def test_partner_ranking(self):
        order = self.create_order(status='DELIVERED', created_minutes_ago=80)
        self.add_status_event(order, 'READY_FOR_PICKUP', 10)
        self.add_status_event(order, 'DELIVERED', 70)
        Delivery.objects.create(
            order=order,
            delivery_partner=self.partner,
            status='DELIVERED',
            partner_fee='40.00',
        )

        response = self.get_insights()

        slow = response.data['delivery_intelligence']['slow_delivery_partners']
        self.assertEqual(slow[0]['name'], 'Ops Partner')
        self.assertGreater(slow[0]['average_delivery_minutes'], 45)

    def test_recommendation_generation(self):
        self.create_order(status='CANCELLED')
        Delivery.objects.create(
            order=self.create_order(status='READY_FOR_PICKUP'),
            delivery_partner=None,
            status='ASSIGNED',
        )

        response = self.get_insights()

        recommendations = response.data['marketplace_recommendations']
        self.assertTrue(recommendations)
        self.assertTrue(
            any('delivery partners' in recommendation.lower() for recommendation in recommendations)
        )

    def test_support_intelligence(self):
        order = self.create_order(status='DELIVERED')
        SupportTicket.objects.create(
            customer=self.customer,
            order=order,
            category='QUALITY',
            description='Cold food',
            refund_status='REQUESTED',
        )

        response = self.get_insights()

        categories = response.data['support_intelligence']['common_complaint_categories']
        self.assertEqual(categories[0]['category'], 'QUALITY')
        self.assertEqual(categories[0]['count'], 1)

    def test_visual_search_intelligence_summary(self):
        VisualSearchEvent.objects.create(
            user=self.customer,
            provider_code='local_mock',
            labels=['pizza', 'food'],
            normalized_query='pizza food',
            fallback_query='pizza food',
            confidence=Decimal('0.8500'),
            result_count=2,
            matched_item_count=1,
            matched_merchant_count=1,
        )
        VisualSearchEvent.objects.create(
            provider_code='local_mock',
            labels=['product'],
            normalized_query='product',
            fallback_query='product',
            confidence=Decimal('0.5000'),
            result_count=0,
            matched_item_count=0,
            matched_merchant_count=0,
        )

        response = self.get_insights()

        self.assertEqual(response.status_code, 200)
        summary = response.data['visual_search_intelligence']
        self.assertEqual(summary['total_visual_searches'], 2)
        self.assertEqual(summary['no_result_searches'], 1)
        labels = {item['label']: item['count'] for item in summary['top_labels']}
        self.assertEqual(labels['pizza'], 1)
        self.assertEqual(summary['top_fallback_queries'][0]['query'], 'product')
        self.assertEqual(summary['provider_usage'][0]['provider_code'], 'local_mock')
        self.assertEqual(summary['average_confidence'], 0.675)

    def test_empty_marketplace_returns_safe_defaults(self):
        SupportTicket.objects.all().delete()
        Delivery.objects.all().delete()
        Order.objects.all().delete()
        Restaurant.objects.all().delete()
        MerchantProfile.objects.all().delete()
        DeliveryPartner.objects.all().delete()
        Customer.objects.all().delete()

        response = self.get_insights()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['marketplace_health']['active_restaurants'], 0)
        self.assertEqual(response.data['order_intelligence']['delayed_orders'], [])
        self.assertTrue(response.data['marketplace_recommendations'])


class AssistantApiTests(APITestCase):
    endpoint = '/api/v1/intelligence/assistant/'

    def setUp(self):
        self.customer_user = User.objects.create_user(
            username='assistant-customer',
            password='pass',
            email='customer@t-food.test',
        )
        Customer.objects.create(user=self.customer_user)
        self.merchant_user = User.objects.create_user(
            username='assistant-merchant',
            password='pass',
            email='merchant@t-food.test',
        )
        MerchantProfile.objects.create(
            user=self.merchant_user,
            business_name='Assistant Merchant',
            is_verified=True,
            verification_status='VERIFIED',
        )
        self.ops_user = User.objects.create_user(
            username='assistant-ops',
            password='pass',
            email='ops@t-food.test',
            is_staff=True,
        )
        OperationsStaffProfile.objects.create(
            user=self.ops_user,
            role=OperationsStaffProfile.ROLE_GLOBAL_ADMIN,
            status=OperationsStaffProfile.STATUS_ACTIVE,
        )

    def test_assistant_requires_authentication(self):
        response = self.client.post(self.endpoint, {
            'surface': 'customer',
            'message': 'How do I track an order?',
        })

        self.assertEqual(response.status_code, 401)

    @override_settings(AI_ASSISTANT_ENABLED=False, OPENAI_API_KEY='')
    def test_disabled_assistant_returns_safe_response(self):
        self.client.force_authenticate(self.customer_user)

        response = self.client.post(self.endpoint, {
            'surface': 'customer',
            'message': 'How do I track an order?',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['enabled'])
        self.assertEqual(response.data['provider'], 'disabled')
        self.assertIn('not enabled', response.data['answer'])

    def test_customer_cannot_use_merchant_assistant(self):
        self.client.force_authenticate(self.customer_user)

        response = self.client.post(self.endpoint, {
            'surface': 'merchant',
            'message': 'How do I manage orders?',
        })

        self.assertEqual(response.status_code, 403)

    def test_customer_cannot_use_operations_assistant(self):
        self.client.force_authenticate(self.customer_user)

        response = self.client.post(self.endpoint, {
            'surface': 'operations',
            'message': 'How do scopes work?',
        })

        self.assertEqual(response.status_code, 403)

    @override_settings(AI_ASSISTANT_ENABLED=True, OPENAI_API_KEY='test-key')
    @patch('intelligence.views.ask_tfood_assistant')
    def test_enabled_assistant_calls_service(self, mocked_assistant):
        mocked_assistant.return_value = {
            'enabled': True,
            'provider': 'openai',
            'answer': 'Use the Orders tab to review active orders.',
        }
        self.client.force_authenticate(self.merchant_user)

        response = self.client.post(self.endpoint, {
            'surface': 'merchant',
            'message': 'Where are orders?',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['answer'], 'Use the Orders tab to review active orders.')
        mocked_assistant.assert_called_once_with('merchant', 'Where are orders?')

    def test_message_length_is_limited(self):
        self.client.force_authenticate(self.customer_user)

        response = self.client.post(self.endpoint, {
            'surface': 'customer',
            'message': 'x' * 2001,
        })

        self.assertEqual(response.status_code, 400)

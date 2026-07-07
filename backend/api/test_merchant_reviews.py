from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from merchant_staff.models import MerchantStaffBranchAccess, MerchantStaffMember
from orders.models import Order, OrderItem
from restaurants.models import (
    FoodItem,
    MerchantProfile,
    Restaurant,
    RestaurantReview,
    ReviewPhoto,
)


class MerchantReviewListTests(APITestCase):
    def setUp(self):
        self.merchant = User.objects.create_user(username='review-merchant')
        MerchantProfile.objects.create(user=self.merchant, is_verified=True)
        self.other_merchant = User.objects.create_user(username='other-review-merchant')
        MerchantProfile.objects.create(user=self.other_merchant, is_verified=True)
        self.customer = User.objects.create_user(
            username='review-customer',
            first_name='Review',
            last_name='Customer',
        )
        self.restaurant = Restaurant.objects.create(
            owner=self.merchant,
            rest_name='Merchant Review Kitchen',
            rest_email='merchant-review@example.com',
            rest_contact='+224620000001',
            rest_address='Review Road',
            rest_city='Conakry',
            is_active=True,
        )
        other_restaurant = Restaurant.objects.create(
            owner=self.other_merchant,
            rest_name='Other Review Kitchen',
            rest_email='other-review@example.com',
            rest_contact='+224620000002',
            rest_address='Other Road',
            rest_city='Conakry',
            is_active=True,
        )
        food = FoodItem.objects.create(
            restaurant=self.restaurant,
            food_name='Review Rice',
            food_price=Decimal('100.00'),
            food_categ='Food',
        )
        other_food = FoodItem.objects.create(
            restaurant=other_restaurant,
            food_name='Other Rice',
            food_price=Decimal('100.00'),
            food_categ='Food',
        )
        self.order = Order.objects.create(
            customer=self.customer,
            status='DELIVERED',
            total_amount=Decimal('100.00'),
        )
        OrderItem.objects.create(
            order=self.order,
            food=food,
            quantity=1,
            price=Decimal('100.00'),
            base_price=Decimal('100.00'),
        )
        self.review = RestaurantReview.objects.create(
            restaurant=self.restaurant,
            customer=self.customer,
            order=self.order,
            rating=2,
            comment='Needs attention',
        )
        ReviewPhoto.objects.create(
            review=self.review,
            uploaded_by=self.customer,
            image='reviews/photos/private/pending.jpg',
            status=ReviewPhoto.STATUS_PENDING,
        )
        other_order = Order.objects.create(
            customer=self.customer,
            status='DELIVERED',
            total_amount=Decimal('100.00'),
        )
        OrderItem.objects.create(
            order=other_order,
            food=other_food,
            quantity=1,
            price=Decimal('100.00'),
            base_price=Decimal('100.00'),
        )
        RestaurantReview.objects.create(
            restaurant=other_restaurant,
            customer=self.customer,
            order=other_order,
            rating=5,
            comment='Other merchant only',
        )

    def test_merchant_lists_own_reviews_with_private_photo_metadata_only(self):
        self.client.force_authenticate(self.merchant)
        response = self.client.get('/api/v1/merchants/reviews/')

        self.assertEqual(response.status_code, 200)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['comment'], 'Needs attention')
        self.assertEqual(results[0]['customer_name'], 'Review Customer')
        self.assertEqual(results[0]['branch_name'], self.restaurant.rest_name)
        self.assertEqual(results[0]['photos'][0]['status'], ReviewPhoto.STATUS_PENDING)
        self.assertIsNone(results[0]['photos'][0]['image_url'])

    def test_customer_cannot_access_merchant_review_list(self):
        self.client.force_authenticate(self.customer)
        response = self.client.get('/api/v1/merchants/reviews/')

        self.assertEqual(response.status_code, 403)

    def test_order_view_staff_can_list_assigned_branch_reviews(self):
        staff_user = User.objects.create_user(username='review-cashier')
        staff_member = MerchantStaffMember.objects.create(
            merchant=self.merchant.merchant_profile,
            user=staff_user,
            role=MerchantStaffMember.ROLE_CASHIER,
            membership_status=MerchantStaffMember.STATUS_ACTIVE,
            verification_status=MerchantStaffMember.VERIFICATION_VERIFIED,
        )
        MerchantStaffBranchAccess.objects.create(
            staff_member=staff_member,
            branch=self.restaurant,
            created_by=self.merchant,
        )

        self.client.force_authenticate(staff_user)
        response = self.client.get('/api/v1/merchants/reviews/')

        self.assertEqual(response.status_code, 200)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['comment'], 'Needs attention')

from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from delivery.models import DeliveryPartner, MerchantRider
from merchant_staff.models import MerchantStaffBranchAccess, MerchantStaffMember
from orders.models import Order, OrderItem
from payments.models import Payment
from restaurants.models import FoodItem, MerchantProfile, Restaurant


class MerchantStaffOperationalPermissionApiTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='staff-permission-owner')
        self.merchant = MerchantProfile.objects.create(
            user=self.owner,
            business_name='Permission Company',
            is_verified=True,
        )
        self.branch_a = Restaurant.objects.create(
            owner=self.owner,
            rest_name='Permission Branch A',
            rest_email='branch-a@example.com',
            rest_contact='9000001001',
            rest_address='A Road',
            rest_city='Bhubaneswar',
            is_active=True,
            is_open=True,
        )
        self.branch_b = Restaurant.objects.create(
            owner=self.owner,
            rest_name='Permission Branch B',
            rest_email='branch-b@example.com',
            rest_contact='9000001002',
            rest_address='B Road',
            rest_city='Bhubaneswar',
            is_active=True,
            is_open=True,
        )
        self.other_owner = User.objects.create_user(username='staff-permission-other')
        MerchantProfile.objects.create(
            user=self.other_owner,
            business_name='Other Permission Company',
            is_verified=True,
        )
        self.other_branch = Restaurant.objects.create(
            owner=self.other_owner,
            rest_name='Other Permission Branch',
            rest_email='other-branch@example.com',
            rest_contact='9000001003',
            rest_address='Other Road',
            rest_city='Bhubaneswar',
            is_active=True,
            is_open=True,
        )
        self.item_a = FoodItem.objects.create(
            restaurant=self.branch_a,
            food_name='Branch A Meal',
            food_price=Decimal('120.00'),
            food_categ='Food',
        )
        self.item_b = FoodItem.objects.create(
            restaurant=self.branch_b,
            food_name='Branch B Meal',
            food_price=Decimal('150.00'),
            food_categ='Food',
        )
        self.order_a = self.create_order(self.item_a)
        self.order_b = self.create_order(self.item_b)
        self.rider_a = self.create_rider('rider-a', self.branch_a)
        self.rider_b = self.create_rider('rider-b', self.branch_b)

    def create_order(self, item, status_value='CONFIRMED'):
        customer = User.objects.create_user(username=f'customer-{item.id}')
        order = Order.objects.create(
            customer=customer,
            status=status_value,
            subtotal_amount=item.food_price,
            total_amount=item.food_price,
            merchant_payout=item.food_price,
            pickup_branch=item.restaurant,
        )
        OrderItem.objects.create(
            order=order,
            food=item,
            quantity=1,
            price=item.food_price,
            base_price=item.food_price,
        )
        Payment.objects.create(order=order, method='COD', status='SUCCESS')
        return order

    def create_rider(self, username, branch):
        user = User.objects.create_user(username=username)
        partner = DeliveryPartner.objects.create(
            user=user,
            partner_name=username,
            partner_phone='9000001999',
            transport_details='Bike',
            is_verified=True,
            is_available=True,
        )
        return MerchantRider.objects.create(
            merchant=self.merchant,
            partner=partner,
            status=MerchantRider.STATUS_ACTIVE,
            home_restaurant=branch,
        )

    def create_staff(self, role, branches=None, is_company_wide=False):
        user = User.objects.create_user(username=f'staff-{role.lower()}-{User.objects.count()}')
        staff = MerchantStaffMember.objects.create(
            merchant=self.merchant,
            user=user,
            role=role,
            membership_status=MerchantStaffMember.STATUS_ACTIVE,
            verification_status=MerchantStaffMember.VERIFICATION_VERIFIED,
            is_company_wide=is_company_wide,
            created_by=self.owner,
        )
        for branch in branches or []:
            MerchantStaffBranchAccess.objects.create(
                staff_member=staff,
                branch=branch,
                created_by=self.owner,
            )
        return user, staff

    def response_items(self, response):
        if isinstance(response.data, dict) and 'results' in response.data:
            return response.data['results']
        return response.data

    def test_owner_retains_full_merchant_access(self):
        self.client.force_authenticate(self.owner)

        restaurants = self.client.get('/api/v1/merchants/restaurants/')
        orders = self.client.get('/api/v1/merchants/orders/')
        payouts = self.client.get('/api/v1/merchants/payouts/')

        self.assertEqual(restaurants.status_code, status.HTTP_200_OK)
        self.assertEqual(orders.status_code, status.HTTP_200_OK)
        self.assertEqual(payouts.status_code, status.HTTP_200_OK)
        restaurant_ids = {row['id'] for row in self.response_items(restaurants)}
        self.assertIn(self.branch_a.id, restaurant_ids)
        self.assertIn(self.branch_b.id, restaurant_ids)

    def test_branch_manager_is_limited_to_assigned_branch(self):
        user, _ = self.create_staff(
            MerchantStaffMember.ROLE_BRANCH_MANAGER,
            branches=[self.branch_a],
        )
        self.client.force_authenticate(user)

        restaurants = self.client.get('/api/v1/merchants/restaurants/')
        orders = self.client.get('/api/v1/merchants/orders/')
        other_branch = self.client.get(
            f'/api/v1/merchants/restaurants/{self.branch_b.id}/'
        )

        self.assertEqual(restaurants.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [row['id'] for row in self.response_items(restaurants)],
            [self.branch_a.id],
        )
        self.assertEqual(orders.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [row['id'] for row in self.response_items(orders)],
            [self.order_a.id],
        )
        self.assertEqual(other_branch.status_code, status.HTTP_404_NOT_FOUND)

    def test_kitchen_staff_can_manage_menu_but_not_finance_or_cancel_orders(self):
        user, _ = self.create_staff(
            MerchantStaffMember.ROLE_KITCHEN_STAFF,
            branches=[self.branch_a],
        )
        self.client.force_authenticate(user)

        create_item = self.client.post(
            f'/api/v1/merchants/restaurants/{self.branch_a.id}/items/',
            {
                'food_name': 'Kitchen Staff Dish',
                'food_desc': 'Prepared by kitchen staff.',
                'food_price': '99.00',
                'food_categ': 'Vegetarian',
            },
        )
        payout = self.client.get('/api/v1/merchants/payouts/')
        cancel = self.client.patch(
            f'/api/v1/merchants/orders/{self.order_a.id}/status/',
            {'status': 'CANCELLED'},
        )

        self.assertEqual(create_item.status_code, status.HTTP_201_CREATED)
        self.assertEqual(payout.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(cancel.status_code, status.HTTP_403_FORBIDDEN)

    def test_cashier_cannot_manage_menu_or_update_order_status(self):
        user, _ = self.create_staff(
            MerchantStaffMember.ROLE_CASHIER,
            branches=[self.branch_a],
        )
        self.client.force_authenticate(user)

        menu = self.client.post(
            f'/api/v1/merchants/restaurants/{self.branch_a.id}/items/',
            {
                'food_name': 'Cashier Dish',
                'food_desc': 'Cashier cannot create this.',
                'food_price': '80.00',
                'food_categ': 'Vegetarian',
            },
        )
        update_order = self.client.patch(
            f'/api/v1/merchants/orders/{self.order_a.id}/status/',
            {'status': 'PREPARING'},
        )
        orders = self.client.get('/api/v1/merchants/orders/')

        self.assertEqual(menu.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(update_order.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(orders.status_code, status.HTTP_200_OK)

    def test_dispatcher_can_manage_assigned_branch_riders_but_not_finance(self):
        user, _ = self.create_staff(
            MerchantStaffMember.ROLE_DISPATCHER,
            branches=[self.branch_a],
        )
        self.client.force_authenticate(user)

        riders = self.client.get('/api/v1/merchants/riders/')
        finance = self.client.get('/api/v1/merchants/payouts/')
        other_rider = self.client.patch(
            f'/api/v1/merchants/riders/{self.rider_b.id}/status/',
            {'status': MerchantRider.STATUS_INACTIVE},
        )

        self.assertEqual(riders.status_code, status.HTTP_200_OK)
        self.assertEqual(riders.data['count'], 1)
        self.assertEqual(riders.data['results'][0]['id'], self.rider_a.id)
        self.assertEqual(finance.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(other_rider.status_code, status.HTTP_404_NOT_FOUND)

    def test_finance_staff_can_view_payouts_but_not_manage_riders(self):
        user, _ = self.create_staff(
            MerchantStaffMember.ROLE_FINANCE_STAFF,
            is_company_wide=True,
        )
        self.client.force_authenticate(user)

        payouts = self.client.get('/api/v1/merchants/payouts/')
        riders = self.client.get('/api/v1/merchants/riders/')

        self.assertEqual(payouts.status_code, status.HTTP_200_OK)
        self.assertEqual(riders.status_code, status.HTTP_403_FORBIDDEN)

    def test_viewer_is_read_only(self):
        user, _ = self.create_staff(
            MerchantStaffMember.ROLE_VIEWER,
            branches=[self.branch_a],
        )
        self.client.force_authenticate(user)

        restaurants = self.client.get('/api/v1/merchants/restaurants/')
        create_item = self.client.post(
            f'/api/v1/merchants/restaurants/{self.branch_a.id}/items/',
            {
                'food_name': 'Viewer Dish',
                'food_desc': 'Viewer cannot create this.',
                'food_price': '50.00',
                'food_categ': 'Vegetarian',
            },
        )

        self.assertEqual(restaurants.status_code, status.HTTP_200_OK)
        self.assertEqual(create_item.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_cannot_access_another_merchant_branch(self):
        user, _ = self.create_staff(
            MerchantStaffMember.ROLE_BRANCH_MANAGER,
            branches=[self.branch_a],
        )
        self.client.force_authenticate(user)

        response = self.client.get(
            f'/api/v1/merchants/restaurants/{self.other_branch.id}/'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

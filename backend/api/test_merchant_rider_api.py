from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from delivery.models import DeliveryPartner, MerchantRider, MerchantRiderInvite
from restaurants.models import MerchantProfile, Restaurant


class MerchantRiderApiTests(APITestCase):
    def setUp(self):
        self.merchant_user = User.objects.create_user(
            username='rider-api-merchant',
            email='rider-api-merchant@example.com',
        )
        self.merchant = MerchantProfile.objects.create(
            user=self.merchant_user,
            business_name='Rider API Merchant',
            phone='9000000101',
            is_verified=True,
        )
        self.restaurant = Restaurant.objects.create(
            owner=self.merchant_user,
            rest_name='Rider API Kitchen',
            branch_name='KIIT Rider Branch',
            branch_type=Restaurant.BRANCH_TYPE_FOOD,
            rest_email='rider-api-kitchen@example.com',
            rest_contact='9000000102',
            rest_address='KIIT Road',
            rest_city='Bhubaneswar',
        )
        self.second_restaurant = Restaurant.objects.create(
            owner=self.merchant_user,
            rest_name='Rider API Second Kitchen',
            branch_name='Second Rider Branch',
            branch_type=Restaurant.BRANCH_TYPE_GROCERY,
            rest_email='rider-api-second-kitchen@example.com',
            rest_contact='9000000106',
            rest_address='Infocity Road',
            rest_city='Bhubaneswar',
        )
        self.other_merchant_user = User.objects.create_user(
            username='rider-api-other-merchant',
            email='rider-api-other-merchant@example.com',
        )
        self.other_merchant = MerchantProfile.objects.create(
            user=self.other_merchant_user,
            business_name='Other Rider API Merchant',
            is_verified=True,
        )
        self.other_restaurant = Restaurant.objects.create(
            owner=self.other_merchant_user,
            rest_name='Other Rider Kitchen',
            rest_email='other-rider-kitchen@example.com',
            rest_contact='9000000103',
            rest_address='Patia',
            rest_city='Bhubaneswar',
        )
        self.partner_user = User.objects.create_user(
            username='rider-api-partner',
            email='rider-api-partner@example.com',
        )
        self.partner = DeliveryPartner.objects.create(
            user=self.partner_user,
            partner_name='Rider API Partner',
            partner_phone='9000000104',
            transport_details='Bike',
            is_verified=True,
            is_available=True,
        )
        self.rider = MerchantRider.objects.create(
            merchant=self.merchant,
            partner=self.partner,
            status=MerchantRider.STATUS_PENDING_APPROVAL,
        )
        self.other_partner_user = User.objects.create_user(
            username='rider-api-other-partner',
            email='rider-api-other-partner@example.com',
        )
        self.other_partner = DeliveryPartner.objects.create(
            user=self.other_partner_user,
            partner_name='Other Rider API Partner',
            partner_phone='9000000105',
            transport_details='Scooter',
            is_verified=True,
            is_available=True,
        )
        self.other_rider = MerchantRider.objects.create(
            merchant=self.other_merchant,
            partner=self.other_partner,
        )
        self.admin = User.objects.create_user(
            username='rider-api-admin',
            email='rider-api-admin@example.com',
            is_staff=True,
        )

    def test_merchant_lists_own_riders_only(self):
        self.client.force_authenticate(self.merchant_user)

        response = self.client.get('/api/v1/merchants/riders/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.rider.id)
        self.assertEqual(
            response.data['results'][0]['rider_name'],
            self.partner.partner_name,
        )
        self.assertEqual(
            response.data['results'][0]['rider_phone'],
            self.partner.partner_phone,
        )
        self.assertIn('home_restaurant', response.data['results'][0])

    def test_merchant_cannot_update_another_merchants_rider(self):
        self.client.force_authenticate(self.merchant_user)

        response = self.client.patch(
            f'/api/v1/merchants/riders/{self.other_rider.id}/status/',
            {'status': MerchantRider.STATUS_INACTIVE},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_invite_creation_returns_unique_token(self):
        self.client.force_authenticate(self.merchant_user)

        first = self.client.post(
            '/api/v1/merchants/riders/invite/',
            {
                'name': 'Invited Rider One',
                'phone': '9000000106',
                'email': 'rider-one@example.com',
                'transport_type': 'Bike',
                'home_restaurant': self.restaurant.id,
            },
            format='json',
        )
        second = self.client.post(
            '/api/v1/merchants/riders/invite/',
            {
                'name': 'Invited Rider Two',
                'transport_type': 'Scooter',
            },
            format='json',
        )

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(first.data['invite_token'], second.data['invite_token'])
        invite = MerchantRiderInvite.objects.get(id=first.data['id'])
        self.assertEqual(invite.merchant, self.merchant)
        self.assertEqual(invite.invited_by, self.merchant_user)
        self.assertEqual(invite.home_restaurant, self.restaurant)

    def test_invite_rejects_other_merchants_restaurant(self):
        self.client.force_authenticate(self.merchant_user)

        response = self.client.post(
            '/api/v1/merchants/riders/invite/',
            {
                'name': 'Wrong Restaurant Rider',
                'home_restaurant': self.other_restaurant.id,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('home_restaurant', response.data)

    def test_status_update_rules_are_enforced(self):
        self.client.force_authenticate(self.merchant_user)

        active_response = self.client.patch(
            f'/api/v1/merchants/riders/{self.rider.id}/status/',
            {'status': MerchantRider.STATUS_ACTIVE},
            format='json',
        )
        inactive_response = self.client.patch(
            f'/api/v1/merchants/riders/{self.rider.id}/status/',
            {'status': MerchantRider.STATUS_INACTIVE},
            format='json',
        )

        self.assertEqual(active_response.status_code, status.HTTP_200_OK)
        self.assertEqual(active_response.data['status'], MerchantRider.STATUS_ACTIVE)
        self.assertEqual(inactive_response.status_code, status.HTTP_200_OK)
        self.assertEqual(inactive_response.data['status'], MerchantRider.STATUS_INACTIVE)

    def test_unverified_rider_cannot_become_active(self):
        self.partner.is_verified = False
        self.partner.save(update_fields=['is_verified'])
        self.client.force_authenticate(self.merchant_user)

        response = self.client.patch(
            f'/api/v1/merchants/riders/{self.rider.id}/status/',
            {'status': MerchantRider.STATUS_ACTIVE},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('operations must verify', response.data['status'][0])

    def test_home_restaurant_assignment_uses_owned_restaurants_only(self):
        self.client.force_authenticate(self.merchant_user)

        response = self.client.post(
            f'/api/v1/merchants/riders/{self.rider.id}/assign-restaurant/',
            {'home_restaurant': self.restaurant.id},
            format='json',
        )
        denied = self.client.post(
            f'/api/v1/merchants/riders/{self.rider.id}/assign-restaurant/',
            {'home_restaurant': self.other_restaurant.id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['home_restaurant']['id'], self.restaurant.id)
        self.assertEqual(
            response.data['home_restaurant']['branch_name'],
            'KIIT Rider Branch',
        )
        self.assertEqual(
            response.data['home_restaurant']['branch_type'],
            Restaurant.BRANCH_TYPE_FOOD,
        )
        self.assertEqual(denied.status_code, status.HTTP_400_BAD_REQUEST)

    def test_home_restaurant_assignment_can_change_and_remove_branch(self):
        self.rider.home_restaurant = self.restaurant
        self.rider.save(update_fields=['home_restaurant'])
        self.client.force_authenticate(self.merchant_user)

        changed = self.client.post(
            f'/api/v1/merchants/riders/{self.rider.id}/assign-restaurant/',
            {'home_restaurant': self.second_restaurant.id},
            format='json',
        )
        removed = self.client.post(
            f'/api/v1/merchants/riders/{self.rider.id}/assign-restaurant/',
            {'home_restaurant': None},
            format='json',
        )

        self.rider.refresh_from_db()
        self.assertEqual(changed.status_code, status.HTTP_200_OK)
        self.assertEqual(changed.data['home_restaurant']['id'], self.second_restaurant.id)
        self.assertEqual(removed.status_code, status.HTTP_200_OK)
        self.assertIsNone(removed.data['home_restaurant'])
        self.assertIsNone(self.rider.home_restaurant)

    def test_inactive_branch_assignment_is_rejected(self):
        self.restaurant.is_active = False
        self.restaurant.save(update_fields=['is_active'])
        self.client.force_authenticate(self.merchant_user)

        response = self.client.post(
            f'/api/v1/merchants/riders/{self.rider.id}/assign-restaurant/',
            {'home_restaurant': self.restaurant.id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('active branch', response.data['home_restaurant'][0])

    def test_removed_rider_cannot_be_assigned_to_branch(self):
        self.rider.status = MerchantRider.STATUS_REMOVED
        self.rider.save(update_fields=['status'])
        self.client.force_authenticate(self.merchant_user)

        response = self.client.post(
            f'/api/v1/merchants/riders/{self.rider.id}/assign-restaurant/',
            {'home_restaurant': self.restaurant.id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Removed riders', response.data['detail'])

    def test_rider_list_can_filter_by_branch(self):
        self.rider.home_restaurant = self.restaurant
        self.rider.save(update_fields=['home_restaurant'])
        self.client.force_authenticate(self.merchant_user)

        matching = self.client.get(
            f'/api/v1/merchants/riders/?branch={self.restaurant.id}'
        )
        empty = self.client.get(
            f'/api/v1/merchants/riders/?branch={self.second_restaurant.id}'
        )
        denied = self.client.get(
            f'/api/v1/merchants/riders/?branch={self.other_restaurant.id}'
        )

        self.assertEqual(matching.status_code, status.HTTP_200_OK)
        self.assertEqual(matching.data['count'], 1)
        self.assertEqual(empty.status_code, status.HTTP_200_OK)
        self.assertEqual(empty.data['count'], 0)
        self.assertEqual(denied.status_code, status.HTTP_400_BAD_REQUEST)

    def test_operations_endpoint_permissions(self):
        self.client.force_authenticate(self.merchant_user)
        denied = self.client.get('/api/v1/operations/merchant-riders/')

        self.client.force_authenticate(self.admin)
        allowed = self.client.get('/api/v1/operations/merchant-riders/')

        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)
        self.assertEqual(len(allowed.data), 2)
        self.assertIn('merchant', allowed.data[0])
        self.assertIn('rider', allowed.data[0])
        self.assertIn('verification', allowed.data[0])

    def test_existing_partner_available_api_still_works(self):
        self.client.force_authenticate(self.partner_user)

        response = self.client.get('/api/v1/delivery/available/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

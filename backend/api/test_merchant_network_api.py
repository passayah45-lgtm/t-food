from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from restaurants.models import MerchantNetworkRelationship, MerchantProfile, Restaurant


class MerchantNetworkApiTests(APITestCase):
    def setUp(self):
        self.merchant_user = User.objects.create_user(
            username='network-api-merchant',
            email='network-api-merchant@example.com',
        )
        self.merchant = MerchantProfile.objects.create(
            user=self.merchant_user,
            business_name='Network API Merchant',
            is_verified=True,
        )
        self.other_user = User.objects.create_user(
            username='network-api-other',
            email='network-api-other@example.com',
        )
        self.other_merchant = MerchantProfile.objects.create(
            user=self.other_user,
            business_name='Nearby Partner Merchant',
            is_verified=True,
        )
        self.far_user = User.objects.create_user(
            username='network-api-far',
            email='network-api-far@example.com',
        )
        self.far_merchant = MerchantProfile.objects.create(
            user=self.far_user,
            business_name='Far Partner Merchant',
            is_verified=True,
        )
        self.stranger_user = User.objects.create_user(
            username='network-api-stranger',
            email='network-api-stranger@example.com',
        )
        self.stranger = MerchantProfile.objects.create(
            user=self.stranger_user,
            business_name='Stranger Merchant',
            is_verified=True,
        )
        self.create_restaurant(
            self.merchant_user,
            'Network Anchor',
            '20.353000',
            '85.819000',
        )
        self.create_restaurant(
            self.other_user,
            'Network Close',
            '20.354000',
            '85.820000',
        )
        self.create_restaurant(
            self.far_user,
            'Network Far',
            '20.390000',
            '85.860000',
        )

    def create_restaurant(self, owner, name, latitude, longitude):
        return Restaurant.objects.create(
            owner=owner,
            rest_name=name,
            rest_email=f'{name.lower().replace(" ", "-")}@example.com',
            rest_contact='9000000200',
            rest_address=f'{name} Road',
            rest_city='Bhubaneswar',
            pickup_latitude=Decimal(str(latitude)),
            pickup_longitude=Decimal(str(longitude)),
            is_active=True,
        )

    def test_merchant_sees_nearby_merchants_sorted_by_distance(self):
        self.client.force_authenticate(self.merchant_user)

        response = self.client.get('/api/v1/merchants/network/nearby/?radius_km=10')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(response.data['results'][0]['id'], self.other_merchant.id)
        self.assertEqual(response.data['results'][1]['id'], self.far_merchant.id)
        self.assertLess(
            Decimal(response.data['results'][0]['distance_km']),
            Decimal(response.data['results'][1]['distance_km']),
        )

    def test_merchant_cannot_request_itself(self):
        self.client.force_authenticate(self.merchant_user)

        response = self.client.post(
            '/api/v1/merchants/network/requests/',
            {'to_merchant': self.merchant.id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('to_merchant', response.data)

    def test_duplicate_requests_are_prevented(self):
        self.client.force_authenticate(self.merchant_user)
        first = self.client.post(
            '/api/v1/merchants/network/requests/',
            {'to_merchant': self.other_merchant.id},
            format='json',
        )
        duplicate = self.client.post(
            '/api/v1/merchants/network/requests/',
            {'to_merchant': self.other_merchant.id},
            format='json',
        )

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)

    def test_accept_pause_and_block_work(self):
        relationship = MerchantNetworkRelationship.objects.create(
            from_merchant=self.merchant,
            to_merchant=self.other_merchant,
            requested_by=self.merchant_user,
        )

        self.client.force_authenticate(self.other_user)
        accepted = self.client.patch(
            f'/api/v1/merchants/network/{relationship.id}/',
            {'action': 'ACCEPT'},
            format='json',
        )
        paused = self.client.patch(
            f'/api/v1/merchants/network/{relationship.id}/',
            {'action': 'PAUSE'},
            format='json',
        )
        blocked = self.client.patch(
            f'/api/v1/merchants/network/{relationship.id}/',
            {'action': 'BLOCK'},
            format='json',
        )

        self.assertEqual(accepted.status_code, status.HTTP_200_OK)
        self.assertEqual(accepted.data['status'], MerchantNetworkRelationship.STATUS_ACTIVE)
        self.assertEqual(paused.status_code, status.HTTP_200_OK)
        self.assertEqual(paused.data['status'], MerchantNetworkRelationship.STATUS_PAUSED)
        self.assertEqual(blocked.status_code, status.HTTP_200_OK)
        self.assertEqual(blocked.data['status'], MerchantNetworkRelationship.STATUS_BLOCKED)

    def test_request_sender_cannot_accept_own_request(self):
        relationship = MerchantNetworkRelationship.objects.create(
            from_merchant=self.merchant,
            to_merchant=self.other_merchant,
            requested_by=self.merchant_user,
        )
        self.client.force_authenticate(self.merchant_user)

        response = self.client.patch(
            f'/api/v1/merchants/network/{relationship.id}/',
            {'action': 'ACCEPT'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('receiving merchant', response.data['action'][0])

    def test_unauthorized_merchant_cannot_modify_another_relationship(self):
        relationship = MerchantNetworkRelationship.objects.create(
            from_merchant=self.merchant,
            to_merchant=self.other_merchant,
            requested_by=self.merchant_user,
        )
        self.client.force_authenticate(self.stranger_user)

        response = self.client.patch(
            f'/api/v1/merchants/network/{relationship.id}/',
            {'action': 'BLOCK'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_collaboration_list_groups_relationships(self):
        MerchantNetworkRelationship.objects.create(
            from_merchant=self.merchant,
            to_merchant=self.other_merchant,
            requested_by=self.merchant_user,
            status=MerchantNetworkRelationship.STATUS_ACTIVE,
        )
        MerchantNetworkRelationship.objects.create(
            from_merchant=self.far_merchant,
            to_merchant=self.merchant,
            requested_by=self.far_user,
            status=MerchantNetworkRelationship.STATUS_REQUESTED,
        )
        self.client.force_authenticate(self.merchant_user)

        response = self.client.get('/api/v1/merchants/network/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['active']), 1)
        self.assertEqual(len(response.data['requested']), 1)
        self.assertEqual(response.data['count'], 2)

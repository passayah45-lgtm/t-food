from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from customers.models import DeliveryAddress


class DeliveryAddressTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='address-customer')
        self.other = User.objects.create_user(username='other-address-customer')
        self.client.force_authenticate(self.user)

    def payload(self, label='HOME', is_default=False):
        return {
            'label': label,
            'recipient_name': 'Test Customer',
            'phone': '1234567890',
            'address': f'{label} Street, Test City',
            'instructions': 'Call on arrival',
            'latitude': '12.971600',
            'longitude': '77.594600',
            'is_default': is_default,
        }

    def test_first_address_becomes_default(self):
        response = self.client.post(
            '/api/v1/users/addresses/', self.payload(), format='json'
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['is_default'])

    def test_new_default_replaces_previous_default(self):
        first = self.client.post(
            '/api/v1/users/addresses/', self.payload(), format='json'
        )
        second = self.client.post(
            '/api/v1/users/addresses/',
            self.payload('WORK', is_default=True),
            format='json',
        )

        self.assertEqual(second.status_code, 201)
        self.assertFalse(DeliveryAddress.objects.get(id=first.data['id']).is_default)
        self.assertTrue(DeliveryAddress.objects.get(id=second.data['id']).is_default)

    def test_deleting_default_promotes_another_address(self):
        first = self.client.post(
            '/api/v1/users/addresses/', self.payload(), format='json'
        )
        second = self.client.post(
            '/api/v1/users/addresses/', self.payload('WORK'), format='json'
        )

        response = self.client.delete(
            f"/api/v1/users/addresses/{first.data['id']}/"
        )

        self.assertEqual(response.status_code, 204)
        self.assertTrue(DeliveryAddress.objects.get(id=second.data['id']).is_default)

    def test_customer_cannot_access_another_customers_address(self):
        address = DeliveryAddress.objects.create(
            user=self.other,
            label='HOME',
            recipient_name='Other Customer',
            phone='9999999999',
            address='Private Address',
            is_default=True,
        )

        get_response = self.client.get(f'/api/v1/users/addresses/{address.id}/')
        delete_response = self.client.delete(f'/api/v1/users/addresses/{address.id}/')

        self.assertEqual(get_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)
        self.assertTrue(DeliveryAddress.objects.filter(id=address.id).exists())

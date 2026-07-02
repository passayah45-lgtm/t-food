from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from notifications.models import Notification
from restaurants.models import MerchantProfile


class MerchantNotificationDashboardApiTests(APITestCase):
    def setUp(self):
        self.merchant = User.objects.create_user(username='notification-merchant')
        MerchantProfile.objects.create(user=self.merchant, is_verified=True)
        self.other_merchant = User.objects.create_user(username='notification-other')
        MerchantProfile.objects.create(user=self.other_merchant, is_verified=True)
        self.customer = User.objects.create_user(username='notification-customer')
        self.unread = Notification.objects.create(
            user=self.merchant,
            kind='ORDER',
            title='New order',
            message='Order #1 needs action.',
        )
        self.read = Notification.objects.create(
            user=self.merchant,
            kind='PAYMENT',
            title='Payout sent',
            message='Payout was sent.',
            is_read=True,
        )
        Notification.objects.create(
            user=self.other_merchant,
            kind='ORDER',
            title='Other merchant order',
            message='This should not leak.',
        )

    def test_merchant_can_list_recent_notifications(self):
        self.client.force_authenticate(self.merchant)

        response = self.client.get('/api/v1/merchants/notifications/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['unread_count'], 1)
        self.assertEqual(len(response.data['results']), 2)
        titles = {row['title'] for row in response.data['results']}
        self.assertEqual(titles, {'New order', 'Payout sent'})

    def test_merchant_notification_limit_is_applied(self):
        self.client.force_authenticate(self.merchant)

        response = self.client.get('/api/v1/merchants/notifications/?limit=1')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)

    def test_invalid_notification_limit_is_rejected(self):
        self.client.force_authenticate(self.merchant)

        response = self.client.get('/api/v1/merchants/notifications/?limit=bad')

        self.assertEqual(response.status_code, 400)
        self.assertIn('limit', response.data)

    def test_non_merchant_cannot_access_merchant_notifications(self):
        self.client.force_authenticate(self.customer)

        response = self.client.get('/api/v1/merchants/notifications/')

        self.assertEqual(response.status_code, 403)

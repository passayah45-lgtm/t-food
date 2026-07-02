import asyncio

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from unittest.mock import patch

from markets.models import Currency, Market, CommerceArea, CommerceCity
from merchant_staff.models import MerchantStaffBranchAccess, MerchantStaffMember
from notifications.models import (
    Notification,
    NotificationDevice,
    NotificationDeliveryAttempt,
    NotificationPreference,
    NotificationTemplate,
)
from notifications.events import (
    notify_branch_event,
    notify_order_event,
    notify_payment_event,
    notify_payout_event,
    notify_staff_event,
    notify_support_event,
    notify_verification_event,
)
from notifications.services import notify, notify_event
from notifications.tasks import create_notification_task
from operations_access.models import (
    OperationsStaffAreaAccess,
    OperationsStaffCityAccess,
    OperationsStaffMarketAccess,
    OperationsStaffProfile,
)
from orders.models import Order, OrderItem, SupportTicket
from payments.models import Payment
from restaurants.models import FoodItem, MerchantProfile, Restaurant


TEST_CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}


class NotificationServiceCompatibilityTests(TestCase):
    def test_notify_remains_synchronous_by_default(self):
        user = User.objects.create_user(username='sync-notification-user')

        notification = notify(
            user,
            'ACCOUNT',
            'Welcome',
            'Your account is ready.',
        )

        self.assertIsInstance(notification, Notification)
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(notification.title, 'Welcome')
        self.assertEqual(notification.status, Notification.STATUS_UNREAD)
        self.assertEqual(notification.category, Notification.CATEGORY_SYSTEM)


class NotificationModelFoundationTests(TestCase):
    def test_old_notification_fields_still_work(self):
        user = User.objects.create_user(username='old-notification-user')

        notification = Notification.objects.create(
            user=user,
            kind='ORDER',
            title='Legacy order update',
            message='Still compatible.',
        )

        self.assertEqual(notification.user, user)
        self.assertEqual(notification.kind, 'ORDER')
        self.assertEqual(notification.title, 'Legacy order update')
        self.assertFalse(notification.is_read)
        self.assertEqual(notification.status, Notification.STATUS_UNREAD)
        self.assertEqual(notification.category, Notification.CATEGORY_ORDER)

    def test_is_read_true_maps_to_read_status_on_save(self):
        user = User.objects.create_user(username='read-compat-user')

        notification = Notification.objects.create(
            user=user,
            kind='PAYMENT',
            title='Payout update',
            message='Marked read immediately.',
            is_read=True,
        )

        self.assertTrue(notification.is_read)
        self.assertEqual(notification.status, Notification.STATUS_READ)

    def test_status_read_keeps_is_read_compatible(self):
        user = User.objects.create_user(username='status-read-user')

        notification = Notification.objects.create(
            user=user,
            kind='ACCOUNT',
            title='Account update',
            message='Status-first read.',
            status=Notification.STATUS_READ,
        )

        self.assertTrue(notification.is_read)
        self.assertEqual(notification.status, Notification.STATUS_READ)

    def test_idempotency_key_prevents_duplicates_when_present(self):
        user = User.objects.create_user(username='idempotent-notification-user')
        Notification.objects.create(
            user=user,
            kind='ORDER',
            title='Order confirmed',
            message='Order #1 confirmed.',
            idempotency_key='order-confirmed:1:user:1',
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Notification.objects.create(
                    user=user,
                    kind='ORDER',
                    title='Order confirmed again',
                    message='This should not duplicate.',
                    idempotency_key='order-confirmed:1:user:1',
                )

    def test_nullable_idempotency_key_allows_normal_notifications(self):
        user = User.objects.create_user(username='normal-notification-user')

        Notification.objects.create(
            user=user,
            kind='ORDER',
            title='First update',
            message='No idempotency key.',
        )
        Notification.objects.create(
            user=user,
            kind='ORDER',
            title='Second update',
            message='No idempotency key.',
        )

        self.assertEqual(Notification.objects.filter(user=user).count(), 2)

    def test_scope_fields_are_optional_for_minimum_configuration_mode(self):
        user = User.objects.create_user(username='minimum-config-notification-user')
        Market.objects.filter(slug='india').update(is_active=False)

        notification = Notification.objects.create(
            user=user,
            kind='ACCOUNT',
            title='Minimum configuration',
            message='No market, country, city, area, or branch required.',
            recipient_type=Notification.RECIPIENT_CUSTOMER,
            event_type='account.created',
            priority=Notification.PRIORITY_LOW,
            action_url='/account',
            metadata={'source': 'test'},
        )

        self.assertIsNone(notification.market)
        self.assertIsNone(notification.city)
        self.assertIsNone(notification.area)
        self.assertIsNone(notification.branch)
        self.assertEqual(notification.action_url, '/account')
        self.assertEqual(notification.metadata['source'], 'test')

    def test_notification_template_uniqueness_works(self):
        NotificationTemplate.objects.create(
            code='order.ready',
            category=Notification.CATEGORY_ORDER,
            event_type='order.ready',
            language='en',
            title_template='Order #{order_number} is ready.',
            message_template='Order #{order_number} is ready for pickup.',
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                NotificationTemplate.objects.create(
                    code='order.ready',
                    category=Notification.CATEGORY_ORDER,
                    event_type='order.ready',
                    language='en',
                    title_template='Duplicate',
                    message_template='Duplicate',
                )

        NotificationTemplate.objects.create(
            code='order.ready',
            category=Notification.CATEGORY_ORDER,
            event_type='order.ready',
            language='fr',
            title_template='Commande prete.',
            message_template='La commande est prete.',
        )
        self.assertEqual(NotificationTemplate.objects.count(), 2)

    def test_notification_delivery_attempt_can_be_created(self):
        user = User.objects.create_user(username='delivery-attempt-user')
        notification = Notification.objects.create(
            user=user,
            kind='DELIVERY',
            title='Delivery update',
            message='Future channel tracking.',
        )

        attempt = NotificationDeliveryAttempt.objects.create(
            notification=notification,
            channel=NotificationDeliveryAttempt.CHANNEL_IN_APP,
            status=NotificationDeliveryAttempt.STATUS_PENDING,
        )

        self.assertEqual(attempt.notification, notification)
        self.assertEqual(attempt.channel, NotificationDeliveryAttempt.CHANNEL_IN_APP)


class NotificationApiCompatibilityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='notification-api-user')

    def test_mark_read_updates_is_read_and_status(self):
        notification = Notification.objects.create(
            user=self.user,
            kind='ORDER',
            title='Unread order',
            message='Needs read state.',
        )
        self.client.force_authenticate(self.user)

        response = self.client.post(f'/api/v1/notifications/{notification.id}/read/')

        notification.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(notification.is_read)
        self.assertEqual(notification.status, Notification.STATUS_READ)

    def test_read_all_updates_is_read_and_status(self):
        Notification.objects.create(
            user=self.user,
            kind='ORDER',
            title='Unread one',
            message='Needs read state.',
        )
        Notification.objects.create(
            user=self.user,
            kind='PAYMENT',
            title='Unread two',
            message='Needs read state.',
        )
        self.client.force_authenticate(self.user)

        response = self.client.post('/api/v1/notifications/read-all/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Notification.objects.filter(
                user=self.user,
                is_read=True,
                status=Notification.STATUS_READ,
            ).count(),
            2,
        )


class NotificationApiUpgradeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='notification-upgrade-user')
        self.other_user = User.objects.create_user(username='notification-other-user')
        self.client.force_authenticate(self.user)

    def create_notification(self, **kwargs):
        defaults = {
            'user': self.user,
            'kind': 'ORDER',
            'title': 'Upgrade notification',
            'message': 'Unified fields are visible.',
            'category': Notification.CATEGORY_ORDER,
            'event_type': 'order.upgrade',
            'priority': Notification.PRIORITY_HIGH,
            'action_url': '/orders/upgrade',
            'metadata': {'safe': 'value', 'password': 'hidden'},
        }
        defaults.update(kwargs)
        return Notification.objects.create(**defaults)

    def response_items(self, response):
        return response.data.get('results', response.data)

    def test_existing_list_endpoint_still_works_and_new_fields_appear(self):
        market = Market.objects.get(slug='india')
        merchant = User.objects.create_user(username='notification-branch-owner')
        branch = Restaurant.objects.create(
            owner=merchant,
            market=market,
            country_code='IN',
            rest_name='Notification Branch',
            rest_email='notification-branch@example.com',
            rest_contact='9999999999',
            rest_address='Notification road',
            rest_city='Bhubaneswar',
        )
        self.create_notification(market=market, branch=branch, country_code='IN')

        response = self.client.get('/api/v1/notifications/')

        self.assertEqual(response.status_code, 200)
        item = self.response_items(response)[0]
        self.assertEqual(item['kind'], 'ORDER')
        self.assertEqual(item['recipient_type'], Notification.RECIPIENT_SYSTEM)
        self.assertEqual(item['category'], Notification.CATEGORY_ORDER)
        self.assertEqual(item['event_type'], 'order.upgrade')
        self.assertEqual(item['priority'], Notification.PRIORITY_HIGH)
        self.assertEqual(item['status'], Notification.STATUS_UNREAD)
        self.assertEqual(item['action_url'], '/orders/upgrade')
        self.assertEqual(item['metadata'], {'safe': 'value'})
        self.assertEqual(item['country_code'], 'IN')
        self.assertEqual(item['branch'], branch.id)
        self.assertEqual(item['branch_name'], branch.branch_name or branch.rest_name)
        self.assertEqual(item['market'], market.id)
        self.assertEqual(item['market_name'], market.name)

    def test_existing_unread_endpoint_still_works(self):
        self.create_notification()
        self.create_notification(status=Notification.STATUS_READ, is_read=True)

        response = self.client.get('/api/v1/notifications/unread/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['unread_count'], 1)

    def test_patch_mark_read_still_works(self):
        notification = self.create_notification()

        response = self.client.patch(f'/api/v1/notifications/{notification.id}/read/')

        notification.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(notification.is_read)
        self.assertEqual(notification.status, Notification.STATUS_READ)

    def test_read_all_still_works(self):
        self.create_notification()
        self.create_notification(title='Second unread')

        response = self.client.post('/api/v1/notifications/read-all/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Notification.objects.filter(
                user=self.user,
                status=Notification.STATUS_READ,
                is_read=True,
            ).count(),
            2,
        )

    def test_filters_work(self):
        today = self.create_notification(
            category=Notification.CATEGORY_ORDER,
            priority=Notification.PRIORITY_HIGH,
            event_type='order.filtered',
        )
        self.create_notification(
            category=Notification.CATEGORY_PAYMENT,
            priority=Notification.PRIORITY_LOW,
            event_type='payment.filtered',
            is_read=True,
            status=Notification.STATUS_READ,
        )

        response = self.client.get(
            '/api/v1/notifications/',
            {
                'status': Notification.STATUS_UNREAD,
                'category': Notification.CATEGORY_ORDER,
                'priority': Notification.PRIORITY_HIGH,
                'event_type': 'order.filtered',
                'unread': 'true',
                'date_from': (
                    today.created_at - timezone.timedelta(minutes=1)
                ).isoformat(),
                'date_to': (
                    today.created_at + timezone.timedelta(minutes=1)
                ).isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in self.response_items(response)], [today.id])

    def test_archive_and_dismiss_work(self):
        archive_target = self.create_notification(title='Archive me')
        dismiss_target = self.create_notification(title='Dismiss me')

        archive_response = self.client.patch(
            f'/api/v1/notifications/{archive_target.id}/archive/'
        )
        dismiss_response = self.client.patch(
            f'/api/v1/notifications/{dismiss_target.id}/dismiss/'
        )

        archive_target.refresh_from_db()
        dismiss_target.refresh_from_db()
        self.assertEqual(archive_response.status_code, 200)
        self.assertEqual(dismiss_response.status_code, 200)
        self.assertEqual(archive_target.status, Notification.STATUS_ARCHIVED)
        self.assertEqual(dismiss_target.status, Notification.STATUS_DISMISSED)
        self.assertTrue(archive_target.is_read)
        self.assertTrue(dismiss_target.is_read)

    def test_archive_read_works(self):
        read_notification = self.create_notification(
            is_read=True,
            status=Notification.STATUS_READ,
        )
        self.create_notification()

        response = self.client.post('/api/v1/notifications/archive-read/')

        read_notification.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(read_notification.status, Notification.STATUS_ARCHIVED)
        self.assertEqual(response.data['updated'], 1)

    def test_mark_by_filter_works(self):
        self.create_notification(category=Notification.CATEGORY_ORDER)
        self.create_notification(category=Notification.CATEGORY_PAYMENT)

        response = self.client.post(
            '/api/v1/notifications/mark-by-filter/?category=ORDER',
            {'action': 'archive'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['updated'], 1)
        self.assertEqual(
            Notification.objects.get(
                user=self.user,
                category=Notification.CATEGORY_ORDER,
            ).status,
            Notification.STATUS_ARCHIVED,
        )

    def test_user_cannot_access_another_users_notification(self):
        notification = self.create_notification(user=self.other_user)

        read_response = self.client.patch(f'/api/v1/notifications/{notification.id}/read/')
        archive_response = self.client.patch(f'/api/v1/notifications/{notification.id}/archive/')
        dismiss_response = self.client.patch(f'/api/v1/notifications/{notification.id}/dismiss/')

        self.assertEqual(read_response.status_code, 404)
        self.assertEqual(archive_response.status_code, 404)
        self.assertEqual(dismiss_response.status_code, 404)
        self.assertEqual(self.response_items(self.client.get('/api/v1/notifications/')), [])

    def test_expired_archived_and_dismissed_excluded_by_default(self):
        active = self.create_notification(title='Active')
        self.create_notification(
            title='Expired',
            expires_at=timezone.now() - timezone.timedelta(minutes=1),
        )
        self.create_notification(
            title='Archived',
            status=Notification.STATUS_ARCHIVED,
            is_read=True,
        )
        self.create_notification(
            title='Dismissed',
            status=Notification.STATUS_DISMISSED,
            is_read=True,
        )

        response = self.client.get('/api/v1/notifications/')

        self.assertEqual([item['id'] for item in self.response_items(response)], [active.id])

    def test_include_expired_and_status_filter_work(self):
        expired = self.create_notification(
            title='Expired',
            expires_at=timezone.now() - timezone.timedelta(minutes=1),
        )
        archived = self.create_notification(
            title='Archived',
            status=Notification.STATUS_ARCHIVED,
            is_read=True,
        )

        expired_response = self.client.get(
            '/api/v1/notifications/',
            {'include_expired': 'true'},
        )
        archived_response = self.client.get(
            '/api/v1/notifications/',
            {'status': Notification.STATUS_ARCHIVED},
        )

        self.assertIn(expired.id, [item['id'] for item in self.response_items(expired_response)])
        self.assertEqual(
            [item['id'] for item in self.response_items(archived_response)],
            [archived.id],
        )

    def test_minimum_configuration_mode_works(self):
        Market.objects.filter(slug='india').update(is_active=False)
        notification = self.create_notification(market=None, country_code=None)

        response = self.client.get('/api/v1/notifications/')

        self.assertEqual(response.status_code, 200)
        item = self.response_items(response)[0]
        self.assertEqual(item['id'], notification.id)
        self.assertIsNone(item['market'])
        self.assertIsNone(item['country_code'])


class NotificationPreferenceApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='preference-user')
        self.other_user = User.objects.create_user(username='preference-other')
        self.client.force_authenticate(self.user)

    def test_default_preferences_created_for_new_user(self):
        expected = (
            len(Notification.CATEGORY_CHOICES)
            * len(NotificationPreference.CHANNEL_CHOICES)
        )

        self.assertEqual(
            NotificationPreference.objects.filter(user=self.user).count(),
            expected,
        )
        self.assertTrue(NotificationPreference.objects.get(
            user=self.user,
            category=Notification.CATEGORY_ORDER,
            channel=NotificationPreference.CHANNEL_IN_APP,
        ).enabled)
        self.assertTrue(NotificationPreference.objects.get(
            user=self.user,
            category=Notification.CATEGORY_ORDER,
            channel=NotificationPreference.CHANNEL_REALTIME,
        ).enabled)
        self.assertFalse(NotificationPreference.objects.get(
            user=self.user,
            category=Notification.CATEGORY_ORDER,
            channel=NotificationPreference.CHANNEL_EMAIL,
        ).enabled)

    def test_get_preferences_returns_defaults_and_channel_state(self):
        NotificationPreference.objects.filter(user=self.user).delete()

        response = self.client.get('/api/v1/notifications/preferences/')

        self.assertEqual(response.status_code, 200)
        self.assertIn(NotificationPreference.CHANNEL_IN_APP, response.data['active_channels'])
        self.assertIn(NotificationPreference.CHANNEL_EMAIL, response.data['future_channels_inactive'])
        self.assertEqual(
            len(response.data['results']),
            len(Notification.CATEGORY_CHOICES) * len(NotificationPreference.CHANNEL_CHOICES),
        )

    def test_update_preferences_and_quiet_hours(self):
        response = self.client.patch(
            '/api/v1/notifications/preferences/',
            {
                'preferences': [
                    {
                        'category': 'ORDER',
                        'channel': 'REALTIME',
                        'enabled': False,
                        'quiet_hours_enabled': True,
                        'quiet_hours_start': '22:00',
                        'quiet_hours_end': '07:00',
                        'language': 'fr',
                    }
                ]
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        preference = NotificationPreference.objects.get(
            user=self.user,
            category=Notification.CATEGORY_ORDER,
            channel=NotificationPreference.CHANNEL_REALTIME,
        )
        self.assertFalse(preference.enabled)
        self.assertTrue(preference.quiet_hours_enabled)
        self.assertEqual(str(preference.quiet_hours_start), '22:00:00')
        self.assertEqual(str(preference.quiet_hours_end), '07:00:00')
        self.assertEqual(preference.language, 'fr')

    def test_users_cannot_modify_another_users_preferences(self):
        response = self.client.patch(
            '/api/v1/notifications/preferences/',
            {
                'user': self.other_user.id,
                'preferences': [
                    {
                        'category': 'ORDER',
                        'channel': 'IN_APP',
                        'enabled': False,
                    }
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(NotificationPreference.objects.get(
            user=self.user,
            category=Notification.CATEGORY_ORDER,
            channel=NotificationPreference.CHANNEL_IN_APP,
        ).enabled)
        self.assertTrue(NotificationPreference.objects.get(
            user=self.other_user,
            category=Notification.CATEGORY_ORDER,
            channel=NotificationPreference.CHANNEL_IN_APP,
        ).enabled)

    def test_future_channels_store_but_remain_inactive(self):
        response = self.client.patch(
            '/api/v1/notifications/preferences/',
            {
                'preferences': [
                    {
                        'category': 'PAYMENT',
                        'channel': 'WHATSAPP',
                        'enabled': True,
                    }
                ]
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        preference = NotificationPreference.objects.get(
            user=self.user,
            category=Notification.CATEGORY_PAYMENT,
            channel=NotificationPreference.CHANNEL_WHATSAPP,
        )
        self.assertTrue(preference.enabled)
        self.assertFalse(preference.effective_enabled)

    def test_existing_notifications_continue_with_default_preferences(self):
        result = notify_event(
            'order.default_preference',
            recipients=[self.user],
            payload={'title': 'Default', 'message': 'Still delivered.'},
            category=Notification.CATEGORY_ORDER,
        )

        self.assertEqual(len(result.notifications), 1)

    def test_disabled_in_app_preference_suppresses_notification(self):
        NotificationPreference.objects.filter(
            user=self.user,
            category=Notification.CATEGORY_ORDER,
            channel=NotificationPreference.CHANNEL_IN_APP,
        ).update(enabled=False)

        result = notify_event(
            'order.disabled_preference',
            recipients=[self.user],
            payload={'title': 'Disabled', 'message': 'Suppressed.'},
            category=Notification.CATEGORY_ORDER,
        )

        self.assertEqual(result.notifications, [])
        self.assertFalse(Notification.objects.filter(
            user=self.user,
            event_type='order.disabled_preference',
        ).exists())

    def test_minimum_configuration_mode_works(self):
        response = self.client.get('/api/v1/notifications/preferences/')

        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.data['results']), 0)

    def test_device_registration_works(self):
        response = self.client.post(
            '/api/v1/notifications/devices/',
            {
                'device_type': 'WEB',
                'device_identifier': 'browser-1',
                'push_token': 'future-token',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        device = NotificationDevice.objects.get(user=self.user)
        self.assertEqual(device.device_type, NotificationDevice.DEVICE_WEB)
        self.assertEqual(device.device_identifier, 'browser-1')
        self.assertEqual(device.push_token, 'future-token')
        self.assertTrue(device.is_active)

    def test_duplicate_device_updates_existing_record(self):
        first = self.client.post(
            '/api/v1/notifications/devices/',
            {
                'device_type': 'WEB',
                'device_identifier': 'same-device',
                'push_token': 'first-token',
            },
            format='json',
        )
        second = self.client.post(
            '/api/v1/notifications/devices/',
            {
                'device_type': 'ANDROID',
                'device_identifier': 'same-device',
                'push_token': 'second-token',
            },
            format='json',
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            NotificationDevice.objects.filter(user=self.user).count(),
            1,
        )
        device = NotificationDevice.objects.get(user=self.user)
        self.assertEqual(device.device_type, NotificationDevice.DEVICE_ANDROID)
        self.assertEqual(device.push_token, 'second-token')
        self.assertTrue(device.is_active)

    def test_device_list_and_delete_are_user_scoped(self):
        own = NotificationDevice.objects.create(
            user=self.user,
            device_type=NotificationDevice.DEVICE_WEB,
            device_identifier='own-device',
        )
        other = NotificationDevice.objects.create(
            user=self.other_user,
            device_type=NotificationDevice.DEVICE_IOS,
            device_identifier='other-device',
        )

        list_response = self.client.get('/api/v1/notifications/devices/')
        missing_delete = self.client.delete(
            f'/api/v1/notifications/devices/{other.id}/',
        )
        delete_response = self.client.delete(
            f'/api/v1/notifications/devices/{own.id}/',
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(
            [item['id'] for item in list_response.data['results']],
            [own.id],
        )
        self.assertFalse(list_response.data['push_active'])
        self.assertEqual(missing_delete.status_code, 404)
        self.assertEqual(delete_response.status_code, 204)
        own.refresh_from_db()
        other.refresh_from_db()
        self.assertFalse(own.is_active)
        self.assertTrue(other.is_active)


class OperationsNotificationCenterApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.global_admin = User.objects.create_superuser(
            username='ops-notification-global',
            email='ops-global@example.com',
            password='pass',
        )
        self.legacy_staff = User.objects.create_user(
            username='ops-notification-legacy',
            is_staff=True,
        )
        self.currency = Currency.objects.create(code='GNF', name='Guinean franc')
        self.guinea = Market.objects.create(
            slug='ops-notification-guinea',
            name='Operations Notification Guinea',
            country_code='GN',
            default_currency=self.currency,
        )
        self.india = Market.objects.get(slug='india')
        self.city = CommerceCity.objects.create(
            market=self.guinea,
            name='Conakry Ops Notifications',
            slug='conakry-ops-notifications',
        )
        self.area = CommerceArea.objects.create(
            market=self.guinea,
            city=self.city,
            name='Kaloum Ops Notifications',
            slug='kaloum-ops-notifications',
        )

    def response_items(self, response):
        return response.data.get('results', response.data)

    def create_ops_user(self, role, username, market=None, city=None, area=None):
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

    def create_ops_notification(self, user, **kwargs):
        defaults = {
            'user': user,
            'kind': 'ACCOUNT',
            'recipient_type': Notification.RECIPIENT_OPERATIONS,
            'category': Notification.CATEGORY_SYSTEM,
            'event_type': 'operations.alert',
            'priority': Notification.PRIORITY_NORMAL,
            'title': 'Operations alert',
            'message': 'Scoped operations alert.',
            'metadata': {'safe': 'value', 'provider_secret': 'hidden'},
        }
        defaults.update(kwargs)
        return Notification.objects.create(**defaults)

    def test_global_admin_sees_global_notifications(self):
        notification = self.create_ops_notification(
            self.global_admin,
            recipient_type=Notification.RECIPIENT_GLOBAL_ADMIN,
        )
        self.client.force_authenticate(self.global_admin)

        response = self.client.get('/api/v1/operations/notifications/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in self.response_items(response)], [notification.id])

    def test_country_admin_sees_only_assigned_country_market_notifications(self):
        user = self.create_ops_user(
            OperationsStaffProfile.ROLE_COUNTRY_ADMIN,
            'ops-country-notifications',
            market=self.guinea,
        )
        in_scope = self.create_ops_notification(
            user,
            recipient_type=Notification.RECIPIENT_COUNTRY_ADMIN,
            market=self.guinea,
            country_code='GN',
        )
        self.create_ops_notification(
            user,
            recipient_type=Notification.RECIPIENT_COUNTRY_ADMIN,
            market=self.india,
            country_code='IN',
            title='India hidden',
        )
        self.client.force_authenticate(user)

        response = self.client.get('/api/v1/operations/notifications/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in self.response_items(response)], [in_scope.id])

    def test_city_admin_sees_only_assigned_city_notifications(self):
        user = self.create_ops_user(
            OperationsStaffProfile.ROLE_CITY_ADMIN,
            'ops-city-notifications',
            city=self.city,
        )
        in_scope = self.create_ops_notification(
            user,
            recipient_type=Notification.RECIPIENT_CITY_ADMIN,
            city=self.city,
            market=self.guinea,
            country_code='GN',
        )
        other_city = CommerceCity.objects.create(
            market=self.guinea,
            name='Ratoma Ops Notifications',
            slug='ratoma-ops-notifications',
        )
        self.create_ops_notification(
            user,
            recipient_type=Notification.RECIPIENT_CITY_ADMIN,
            city=other_city,
            market=self.guinea,
            country_code='GN',
        )
        self.client.force_authenticate(user)

        response = self.client.get('/api/v1/operations/notifications/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in self.response_items(response)], [in_scope.id])

    def test_area_admin_sees_only_assigned_area_notifications(self):
        user = self.create_ops_user(
            OperationsStaffProfile.ROLE_AREA_ADMIN,
            'ops-area-notifications',
            area=self.area,
        )
        in_scope = self.create_ops_notification(
            user,
            recipient_type=Notification.RECIPIENT_AREA_ADMIN,
            area=self.area,
            city=self.city,
            market=self.guinea,
            country_code='GN',
        )
        other_area = CommerceArea.objects.create(
            market=self.guinea,
            city=self.city,
            name='Matam Ops Notifications',
            slug='matam-ops-notifications',
        )
        self.create_ops_notification(
            user,
            recipient_type=Notification.RECIPIENT_AREA_ADMIN,
            area=other_area,
            city=self.city,
            market=self.guinea,
            country_code='GN',
        )
        self.client.force_authenticate(user)

        response = self.client.get('/api/v1/operations/notifications/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in self.response_items(response)], [in_scope.id])

    def test_legacy_staff_remains_compatible(self):
        notification = self.create_ops_notification(
            self.legacy_staff,
            market=self.india,
            country_code='IN',
        )
        self.client.force_authenticate(self.legacy_staff)

        response = self.client.get('/api/v1/operations/notifications/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in self.response_items(response)], [notification.id])

    def test_read_archive_dismiss_and_read_all_work_within_scope(self):
        user = self.create_ops_user(
            OperationsStaffProfile.ROLE_COUNTRY_ADMIN,
            'ops-actions-notifications',
            market=self.guinea,
        )
        read_target = self.create_ops_notification(user, market=self.guinea, country_code='GN')
        archive_target = self.create_ops_notification(user, market=self.guinea, country_code='GN')
        dismiss_target = self.create_ops_notification(user, market=self.guinea, country_code='GN')
        read_all_target = self.create_ops_notification(user, market=self.guinea, country_code='GN')
        self.client.force_authenticate(user)

        read_response = self.client.patch(f'/api/v1/operations/notifications/{read_target.id}/read/')
        archive_response = self.client.patch(f'/api/v1/operations/notifications/{archive_target.id}/archive/')
        dismiss_response = self.client.patch(f'/api/v1/operations/notifications/{dismiss_target.id}/dismiss/')
        read_all_response = self.client.post('/api/v1/operations/notifications/read-all/')

        read_target.refresh_from_db()
        archive_target.refresh_from_db()
        dismiss_target.refresh_from_db()
        read_all_target.refresh_from_db()
        self.assertEqual(read_response.status_code, 200)
        self.assertEqual(archive_response.status_code, 200)
        self.assertEqual(dismiss_response.status_code, 200)
        self.assertEqual(read_all_response.status_code, 200)
        self.assertEqual(read_target.status, Notification.STATUS_READ)
        self.assertEqual(archive_target.status, Notification.STATUS_ARCHIVED)
        self.assertEqual(dismiss_target.status, Notification.STATUS_DISMISSED)
        self.assertEqual(read_all_target.status, Notification.STATUS_READ)

    def test_out_of_scope_notification_action_is_hidden(self):
        user = self.create_ops_user(
            OperationsStaffProfile.ROLE_COUNTRY_ADMIN,
            'ops-action-hidden-notifications',
            market=self.guinea,
        )
        hidden = self.create_ops_notification(
            user,
            recipient_type=Notification.RECIPIENT_COUNTRY_ADMIN,
            market=self.india,
            country_code='IN',
        )
        self.client.force_authenticate(user)

        response = self.client.patch(f'/api/v1/operations/notifications/{hidden.id}/read/')

        self.assertEqual(response.status_code, 404)

    def test_filters_and_secret_redaction_work(self):
        notification = self.create_ops_notification(
            self.global_admin,
            recipient_type=Notification.RECIPIENT_GLOBAL_ADMIN,
            category=Notification.CATEGORY_VERIFICATION,
            event_type='staff.verification.pending',
            priority=Notification.PRIORITY_HIGH,
            market=self.guinea,
            country_code='GN',
            city=self.city,
            area=self.area,
        )
        self.create_ops_notification(
            self.global_admin,
            recipient_type=Notification.RECIPIENT_GLOBAL_ADMIN,
            status=Notification.STATUS_READ,
            is_read=True,
        )
        self.client.force_authenticate(self.global_admin)

        response = self.client.get('/api/v1/operations/notifications/', {
            'status': Notification.STATUS_UNREAD,
            'category': Notification.CATEGORY_VERIFICATION,
            'priority': Notification.PRIORITY_HIGH,
            'event_type': 'staff.verification.pending',
            'market': self.guinea.id,
            'country_code': 'GN',
            'city': self.city.id,
            'area': self.area.id,
            'unread': 'true',
        })

        self.assertEqual(response.status_code, 200)
        items = self.response_items(response)
        self.assertEqual([item['id'] for item in items], [notification.id])
        self.assertEqual(items[0]['metadata'], {'safe': 'value'})

    def test_minimum_configuration_mode_works(self):
        notification = self.create_ops_notification(
            self.global_admin,
            recipient_type=Notification.RECIPIENT_GLOBAL_ADMIN,
            market=None,
            country_code=None,
            city=None,
            area=None,
        )
        self.client.force_authenticate(self.global_admin)

        response = self.client.get('/api/v1/operations/notifications/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in self.response_items(response)], [notification.id])


class NotificationRoutingServiceTests(TestCase):
    def _merchant_with_branch(self, suffix='routing'):
        owner = User.objects.create_user(username=f'merchant-owner-{suffix}')
        merchant = MerchantProfile.objects.create(
            user=owner,
            business_name=f'Merchant {suffix}',
            is_verified=True,
            verification_status='VERIFIED',
        )
        branch = Restaurant.objects.create(
            owner=owner,
            rest_name=f'Branch {suffix}',
            rest_email=f'branch-{suffix}@example.com',
            rest_contact='9999999999',
            rest_address='Main road',
            rest_city='Test City',
            is_active=True,
        )
        return merchant, branch

    def _staff(
        self,
        merchant,
        username,
        role,
        branch=None,
        is_company_wide=False,
        membership_status=MerchantStaffMember.STATUS_ACTIVE,
        verification_status=MerchantStaffMember.VERIFICATION_VERIFIED,
    ):
        user = User.objects.create_user(username=username)
        staff = MerchantStaffMember.objects.create(
            merchant=merchant,
            user=user,
            role=role,
            is_company_wide=is_company_wide,
            membership_status=membership_status,
            verification_status=verification_status,
        )
        if branch:
            MerchantStaffBranchAccess.objects.create(
                staff_member=staff,
                branch=branch,
            )
        return staff

    def test_notify_event_creates_notification_for_direct_user(self):
        user = User.objects.create_user(username='direct-route-user')

        result = notify_event(
            'order.placed',
            recipients=[user],
            payload={'title': 'Order placed', 'message': 'We got it.'},
            category=Notification.CATEGORY_ORDER,
            action_url='/orders/1',
        )

        self.assertEqual(len(result.notifications), 1)
        notification = result.notifications[0]
        self.assertEqual(notification.user, user)
        self.assertEqual(notification.event_type, 'order.placed')
        self.assertEqual(notification.category, Notification.CATEGORY_ORDER)
        self.assertEqual(notification.action_url, '/orders/1')

    def test_idempotency_prevents_duplicate_notification(self):
        user = User.objects.create_user(username='idempotent-route-user')

        first = notify_event(
            'payment.confirmed',
            recipients=[user],
            payload={'title': 'Paid', 'message': 'Payment confirmed.'},
            category=Notification.CATEGORY_PAYMENT,
            idempotency_key='payment.confirmed:1',
        )
        second = notify_event(
            'payment.confirmed',
            recipients=[user],
            payload={'title': 'Paid again', 'message': 'Duplicate.'},
            category=Notification.CATEGORY_PAYMENT,
            idempotency_key='payment.confirmed:1',
        )

        self.assertEqual(len(first.notifications), 1)
        self.assertEqual(len(second.notifications), 0)
        self.assertEqual(second.skipped_duplicates, 1)
        self.assertEqual(Notification.objects.filter(user=user).count(), 1)

    def test_missing_recipients_returns_empty_result_safely(self):
        result = notify_event(
            'system.empty',
            recipients=None,
            payload={'title': 'Nobody', 'message': 'No recipients.'},
        )

        self.assertEqual(result.notifications, [])
        self.assertEqual(result.skipped_duplicates, 0)
        self.assertEqual(result.errors, [])

    def test_template_fallback_uses_payload_title_and_message(self):
        user = User.objects.create_user(username='fallback-template-user')

        result = notify_event(
            'template.missing',
            recipients=[user],
            payload={'title': 'Fallback title', 'message': 'Fallback message'},
        )

        notification = result.notifications[0]
        self.assertEqual(notification.title, 'Fallback title')
        self.assertEqual(notification.message, 'Fallback message')

    def test_existing_template_renders_title_and_message(self):
        user = User.objects.create_user(username='render-template-user')
        NotificationTemplate.objects.create(
            code='order.ready',
            category=Notification.CATEGORY_ORDER,
            event_type='order.ready',
            language='en',
            title_template='Order #{order_number} is ready.',
            message_template='Pick up order #{order_number} at {branch_name}.',
        )

        result = notify_event(
            'order.ready',
            recipients=[user],
            payload={'order_number': 'T100', 'branch_name': 'Kaloum'},
            category=Notification.CATEGORY_ORDER,
        )

        notification = result.notifications[0]
        self.assertEqual(notification.title, 'Order #T100 is ready.')
        self.assertEqual(notification.message, 'Pick up order #T100 at Kaloum.')

    def test_merchant_owner_recipient_resolves(self):
        merchant, branch = self._merchant_with_branch('owner-route')

        result = notify_event(
            'merchant.branch.warning',
            recipients={'merchant': merchant},
            scope={'branch': branch},
            payload={'title': 'Branch warning', 'message': 'Check branch.'},
            category=Notification.CATEGORY_MERCHANT,
        )

        self.assertEqual(len(result.notifications), 1)
        self.assertEqual(result.notifications[0].user, merchant.user)
        self.assertEqual(
            result.notifications[0].recipient_type,
            Notification.RECIPIENT_MERCHANT_OWNER,
        )

    def test_merchant_owner_receives_company_notification_without_branch(self):
        merchant, _branch = self._merchant_with_branch('owner-company-route')

        result = notify_event(
            'merchant.company.notice',
            recipients={'merchant': merchant},
            payload={'title': 'Company notice', 'message': 'Company update.'},
            category=Notification.CATEGORY_MERCHANT,
        )

        self.assertEqual(len(result.notifications), 1)
        self.assertEqual(result.notifications[0].user, merchant.user)

    def test_merchant_staff_branch_and_role_recipient_resolves(self):
        merchant, branch = self._merchant_with_branch('staff-route')
        staff = self._staff(
            merchant=merchant,
            username='kitchen-staff-route',
            role=MerchantStaffMember.ROLE_KITCHEN_STAFF,
            branch=branch,
        )

        result = notify_event(
            'order.preparation.started',
            recipients={
                'merchant_staff': {
                    'merchant': merchant,
                    'branch': branch,
                    'roles': [MerchantStaffMember.ROLE_KITCHEN_STAFF],
                },
            },
            scope={'branch': branch},
            payload={'title': 'New preparation', 'message': 'Start cooking.'},
            category=Notification.CATEGORY_ORDER,
        )

        self.assertEqual(len(result.notifications), 1)
        self.assertEqual(result.notifications[0].user, staff.user)
        self.assertEqual(
            result.notifications[0].recipient_type,
            Notification.RECIPIENT_MERCHANT_STAFF,
        )

    def test_kitchen_staff_does_not_receive_finance_notification(self):
        merchant, branch = self._merchant_with_branch('kitchen-finance-route')
        self._staff(
            merchant,
            'kitchen-no-finance-route',
            MerchantStaffMember.ROLE_KITCHEN_STAFF,
            branch=branch,
        )

        result = notify_event(
            'merchant.payout.available',
            recipients={'merchant_staff': {'merchant': merchant, 'branch': branch}},
            scope={'branch': branch},
            payload={'title': 'Payout available', 'message': 'Finance update.'},
            category=Notification.CATEGORY_PAYMENT,
        )

        self.assertEqual(result.notifications, [])

    def test_finance_staff_receives_payout_notification(self):
        merchant, branch = self._merchant_with_branch('finance-route')
        finance = self._staff(
            merchant,
            'finance-staff-route',
            MerchantStaffMember.ROLE_FINANCE_STAFF,
            branch=branch,
        )

        result = notify_event(
            'merchant.payout.available',
            recipients={'merchant_staff': {'merchant': merchant, 'branch': branch}},
            scope={'branch': branch},
            payload={'title': 'Payout available', 'message': 'Finance update.'},
            category=Notification.CATEGORY_PAYMENT,
        )

        self.assertEqual(len(result.notifications), 1)
        self.assertEqual(result.notifications[0].user, finance.user)

    def test_dispatcher_receives_dispatch_notification(self):
        merchant, branch = self._merchant_with_branch('dispatcher-route')
        dispatcher = self._staff(
            merchant,
            'dispatcher-staff-route',
            MerchantStaffMember.ROLE_DISPATCHER,
            branch=branch,
        )

        result = notify_event(
            'dispatch.rider.issue',
            recipients={'merchant_staff': {'merchant': merchant, 'branch': branch}},
            scope={'branch': branch},
            payload={'title': 'Rider issue', 'message': 'Review dispatch.'},
            category=Notification.CATEGORY_DISPATCH,
        )

        self.assertEqual(len(result.notifications), 1)
        self.assertEqual(result.notifications[0].user, dispatcher.user)

    def test_viewer_receives_only_informational_notification(self):
        merchant, branch = self._merchant_with_branch('viewer-route')
        viewer = self._staff(
            merchant,
            'viewer-staff-route',
            MerchantStaffMember.ROLE_VIEWER,
            branch=branch,
        )

        info = notify_event(
            'analytics.weekly.summary',
            recipients={'merchant_staff': {'merchant': merchant, 'branch': branch}},
            scope={'branch': branch},
            payload={
                'title': 'Weekly summary',
                'message': 'Branch summary.',
                'action_required': False,
            },
            category=Notification.CATEGORY_INTELLIGENCE,
            priority=Notification.PRIORITY_LOW,
        )
        action_required = notify_event(
            'support.customer.escalation',
            recipients={'merchant_staff': {'merchant': merchant, 'branch': branch}},
            scope={'branch': branch},
            payload={
                'title': 'Escalation',
                'message': 'Action required.',
                'action_required': True,
            },
            category=Notification.CATEGORY_SUPPORT,
            priority=Notification.PRIORITY_HIGH,
        )

        self.assertEqual(len(info.notifications), 1)
        self.assertEqual(info.notifications[0].user, viewer.user)
        self.assertEqual(action_required.notifications, [])

    def test_branch_staff_only_receives_assigned_branch_notification(self):
        merchant, branch_a = self._merchant_with_branch('branch-a-route')
        branch_b = Restaurant.objects.create(
            owner=merchant.user,
            rest_name='Branch B route',
            rest_email='branch-b-route@example.com',
            rest_contact='9999999998',
            rest_address='Second road',
            rest_city='Test City',
            is_active=True,
        )
        self._staff(
            merchant,
            'branch-limited-kitchen-route',
            MerchantStaffMember.ROLE_KITCHEN_STAFF,
            branch=branch_a,
        )

        result = notify_event(
            'order.preparation.started',
            recipients={'merchant_staff': {'merchant': merchant, 'branch': branch_b}},
            scope={'branch': branch_b},
            payload={'title': 'New prep', 'message': 'Branch B.'},
            category=Notification.CATEGORY_ORDER,
        )

        self.assertEqual(result.notifications, [])

    def test_company_wide_staff_receives_all_merchant_branch_notifications(self):
        merchant, branch = self._merchant_with_branch('company-wide-route')
        staff = self._staff(
            merchant,
            'company-wide-kitchen-route',
            MerchantStaffMember.ROLE_KITCHEN_STAFF,
            is_company_wide=True,
        )

        result = notify_event(
            'order.preparation.started',
            recipients={'merchant_staff': {'merchant': merchant, 'branch': branch}},
            scope={'branch': branch},
            payload={'title': 'New prep', 'message': 'Any branch.'},
            category=Notification.CATEGORY_ORDER,
        )

        self.assertEqual(len(result.notifications), 1)
        self.assertEqual(result.notifications[0].user, staff.user)

    def test_merchant_without_branches_still_routes_company_staff_notification(self):
        owner = User.objects.create_user(username='no-branch-owner-route')
        merchant = MerchantProfile.objects.create(
            user=owner,
            business_name='No Branch Merchant',
            is_verified=True,
            verification_status='VERIFIED',
        )
        staff = self._staff(
            merchant,
            'no-branch-company-viewer-route',
            MerchantStaffMember.ROLE_VIEWER,
            is_company_wide=True,
        )

        result = notify_event(
            'analytics.weekly.summary',
            recipients={'merchant_staff': {'merchant': merchant}},
            payload={'title': 'Company summary', 'message': 'No branches yet.'},
            category=Notification.CATEGORY_INTELLIGENCE,
            priority=Notification.PRIORITY_LOW,
        )

        self.assertEqual(len(result.notifications), 1)
        self.assertEqual(result.notifications[0].user, staff.user)

    def test_unverified_suspended_and_removed_staff_receive_nothing(self):
        merchant, branch = self._merchant_with_branch('inactive-staff-route')
        self._staff(
            merchant,
            'unverified-kitchen-route',
            MerchantStaffMember.ROLE_KITCHEN_STAFF,
            branch=branch,
            membership_status=MerchantStaffMember.STATUS_PENDING_VERIFICATION,
            verification_status=MerchantStaffMember.VERIFICATION_SUBMITTED,
        )
        self._staff(
            merchant,
            'suspended-kitchen-route',
            MerchantStaffMember.ROLE_KITCHEN_STAFF,
            branch=branch,
            membership_status=MerchantStaffMember.STATUS_INACTIVE,
            verification_status=MerchantStaffMember.VERIFICATION_SUSPENDED,
        )
        self._staff(
            merchant,
            'removed-kitchen-route',
            MerchantStaffMember.ROLE_KITCHEN_STAFF,
            branch=branch,
            membership_status=MerchantStaffMember.STATUS_REMOVED,
            verification_status=MerchantStaffMember.VERIFICATION_VERIFIED,
        )

        result = notify_event(
            'order.preparation.started',
            recipients={'merchant_staff': {'merchant': merchant, 'branch': branch}},
            scope={'branch': branch},
            payload={'title': 'New prep', 'message': 'Trusted staff only.'},
            category=Notification.CATEGORY_ORDER,
        )

        self.assertEqual(result.notifications, [])

    def test_operations_global_recipient_resolves(self):
        admin = User.objects.create_superuser(
            username='global-notification-admin',
            email='global@example.com',
            password='pass',
        )

        result = notify_event(
            'operations.alert',
            recipients={'operations': True},
            payload={'title': 'Global alert', 'message': 'All clear.'},
            category=Notification.CATEGORY_SYSTEM,
        )

        self.assertEqual(len(result.notifications), 1)
        self.assertEqual(result.notifications[0].user, admin)
        self.assertEqual(
            result.notifications[0].recipient_type,
            Notification.RECIPIENT_GLOBAL_ADMIN,
        )

    def test_operations_scoped_recipient_resolves(self):
        market = Market.objects.get(slug='india')
        ops_user = User.objects.create_user(username='country-ops-route')
        profile = OperationsStaffProfile.objects.create(
            user=ops_user,
            role=OperationsStaffProfile.ROLE_COUNTRY_ADMIN,
            status=OperationsStaffProfile.STATUS_ACTIVE,
        )
        OperationsStaffMarketAccess.objects.create(profile=profile, market=market)

        result = notify_event(
            'operations.country.alert',
            recipients={'operations': True},
            scope={'market': market},
            payload={'title': 'Country alert', 'message': 'Scoped.'},
            category=Notification.CATEGORY_SYSTEM,
        )

        self.assertEqual(len(result.notifications), 1)
        self.assertEqual(result.notifications[0].user, ops_user)
        self.assertEqual(
            result.notifications[0].recipient_type,
            Notification.RECIPIENT_COUNTRY_ADMIN,
        )

    def test_operations_out_of_scope_recipient_excluded(self):
        india = Market.objects.get(slug='india')
        currency = Currency.objects.create(code='GNF', name='Guinean franc')
        guinea = Market.objects.create(
            slug='guinea-route',
            name='Guinea Route',
            country_code='GN',
            default_currency=currency,
        )
        ops_user = User.objects.create_user(username='out-of-scope-ops-route')
        profile = OperationsStaffProfile.objects.create(
            user=ops_user,
            role=OperationsStaffProfile.ROLE_COUNTRY_ADMIN,
            status=OperationsStaffProfile.STATUS_ACTIVE,
        )
        OperationsStaffMarketAccess.objects.create(profile=profile, market=india)

        result = notify_event(
            'operations.guinea.alert',
            recipients={'operations': True},
            scope={'market': guinea},
            payload={'title': 'Guinea alert', 'message': 'Out of scope.'},
        )

        self.assertEqual(result.notifications, [])

    def test_scope_fields_populated(self):
        market = Market.objects.get(slug='india')
        city = CommerceCity.objects.create(
            market=market,
            name='Routing City',
            slug='routing-city',
        )
        area = CommerceArea.objects.create(
            market=market,
            city=city,
            name='Routing Area',
            slug='routing-area',
        )
        merchant, branch = self._merchant_with_branch('scope-route')
        branch.market = market
        branch.country_code = 'IN'
        branch.city_ref = city
        branch.area_ref = area
        branch.save()

        result = notify_event(
            'branch.scope',
            recipients=[merchant.user],
            scope={'branch': branch},
            payload={'title': 'Scoped', 'message': 'Scoped fields.'},
        )

        notification = result.notifications[0]
        self.assertEqual(notification.market, market)
        self.assertEqual(notification.country_code, 'IN')
        self.assertEqual(notification.city, city)
        self.assertEqual(notification.area, area)
        self.assertEqual(notification.branch, branch)

    def test_minimum_configuration_mode_works(self):
        user = User.objects.create_user(username='minimum-route-user')
        Market.objects.filter(slug='india').update(is_active=False)

        result = notify_event(
            'minimum.notification',
            recipients=[user],
            payload={'title': 'Minimum', 'message': 'No hierarchy needed.'},
        )

        notification = result.notifications[0]
        self.assertIsNone(notification.market)
        self.assertIsNone(notification.city)
        self.assertIsNone(notification.area)
        self.assertIsNone(notification.branch)

    def test_no_external_channels_attempted(self):
        user = User.objects.create_user(username='no-channel-route-user')

        result = notify_event(
            'channel.inactive',
            recipients=[user],
            payload={'title': 'In-app only', 'message': 'No external send.'},
            channels=['EMAIL', 'SMS', 'PUSH'],
        )

        self.assertEqual(len(result.notifications), 1)
        self.assertEqual(NotificationDeliveryAttempt.objects.count(), 0)


class NotificationEventSourceIntegrationTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(username='event-customer')
        self.owner = User.objects.create_user(username='event-owner')
        self.merchant = MerchantProfile.objects.create(
            user=self.owner,
            business_name='Event Merchant',
            is_verified=True,
            verification_status='VERIFIED',
        )
        self.branch = Restaurant.objects.create(
            owner=self.owner,
            rest_name='Event Branch',
            rest_email='event-branch@example.com',
            rest_contact='9999999999',
            rest_address='Main road',
            rest_city='Event City',
            is_active=True,
        )
        self.food = FoodItem.objects.create(
            restaurant=self.branch,
            food_name='Event Meal',
            food_price='120.00',
            food_categ='Vegetarian',
        )
        self.order = Order.objects.create(
            customer=self.customer,
            pickup_branch=self.branch,
            status='CONFIRMED',
            total_amount='140.00',
            subtotal_amount='120.00',
            delivery_fee='20.00',
            merchant_payout='100.00',
        )
        OrderItem.objects.create(
            order=self.order,
            food=self.food,
            quantity=1,
            price='120.00',
            base_price='120.00',
        )
        self.payment = Payment.objects.create(
            order=self.order,
            method='COD',
            status='SUCCESS',
        )

    def _execute_event(self, callback):
        with self.captureOnCommitCallbacks(execute=True):
            callback()

    def test_order_event_creates_customer_and_merchant_notifications(self):
        self._execute_event(lambda: notify_order_event(self.order, 'placed'))

        self.assertTrue(Notification.objects.filter(
            user=self.customer,
            event_type='order.placed',
        ).exists())
        self.assertTrue(Notification.objects.filter(
            user=self.owner,
            event_type='order.placed',
        ).exists())

    def test_payment_and_refund_events_create_notifications(self):
        self._execute_event(lambda: notify_payment_event(self.payment, 'confirmed'))
        self._execute_event(lambda: notify_payment_event(self.payment, 'refund_completed'))

        self.assertTrue(Notification.objects.filter(event_type='payment.confirmed').exists())
        self.assertTrue(Notification.objects.filter(event_type='payment.refund_completed').exists())

    def test_verification_events_create_notifications(self):
        self._execute_event(lambda: notify_verification_event(
            self.merchant,
            'merchant_approved',
        ))

        self.assertTrue(Notification.objects.filter(
            user=self.owner,
            event_type='verification.merchant_approved',
        ).exists())

    def test_merchant_branch_and_staff_events_create_notifications(self):
        staff_user = User.objects.create_user(username='event-staff')
        staff = MerchantStaffMember.objects.create(
            merchant=self.merchant,
            user=staff_user,
            role=MerchantStaffMember.ROLE_BRANCH_MANAGER,
            membership_status=MerchantStaffMember.STATUS_ACTIVE,
            verification_status=MerchantStaffMember.VERIFICATION_VERIFIED,
            is_company_wide=True,
        )

        self._execute_event(lambda: notify_branch_event(self.branch, 'opened'))
        self._execute_event(lambda: notify_staff_event(staff, 'invited'))

        self.assertTrue(Notification.objects.filter(event_type='branch.opened').exists())
        self.assertTrue(Notification.objects.filter(event_type='staff.invited').exists())

    def test_support_event_creates_notification(self):
        ticket = SupportTicket.objects.create(
            customer=self.customer,
            order=self.order,
            category='PAYMENT',
            description='Refund please',
            refund_status='REQUESTED',
        )

        self._execute_event(lambda: notify_support_event(ticket, 'created'))

        self.assertTrue(Notification.objects.filter(
            user=self.customer,
            event_type='support.ticket_created',
        ).exists())

    def test_payout_event_creates_notification(self):
        self._execute_event(lambda: notify_payout_event(
            self.order,
            'merchant_available',
        ))

        self.assertTrue(Notification.objects.filter(
            user=self.owner,
            event_type='payout.merchant_available',
        ).exists())

    def test_transaction_rollback_produces_no_notification(self):
        try:
            with self.captureOnCommitCallbacks(execute=True):
                with transaction.atomic():
                    notify_order_event(self.order, 'cancelled')
                    raise RuntimeError('rollback')
        except RuntimeError:
            pass

        self.assertFalse(Notification.objects.filter(
            event_type='order.cancelled',
        ).exists())

    def test_duplicate_event_prevented(self):
        self._execute_event(lambda: notify_order_event(self.order, 'delivered'))
        self._execute_event(lambda: notify_order_event(self.order, 'delivered'))

        self.assertEqual(
            Notification.objects.filter(event_type='order.delivered').count(),
            2,
        )


@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class NotificationEventSourceRealtimeTests(TransactionTestCase):
    reset_sequences = True

    def test_event_source_still_creates_realtime_delivery_attempt(self):
        customer = User.objects.create_user(username='event-rt-customer')
        order = Order.objects.create(customer=customer, status='PLACED')

        notify_order_event(order, 'expired')

        self.assertTrue(Notification.objects.filter(
            user=customer,
            event_type='order.expired',
        ).exists())
        self.assertTrue(NotificationDeliveryAttempt.objects.filter(
            notification__user=customer,
            channel=NotificationDeliveryAttempt.CHANNEL_REALTIME,
            status=NotificationDeliveryAttempt.STATUS_SENT,
        ).exists())


@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class NotificationRealtimeDeliveryTests(TransactionTestCase):
    def listen(self, group):
        return async_to_sync(self._listen)(group)

    async def _listen(self, group):
        layer = get_channel_layer()
        channel = await layer.new_channel()
        await layer.group_add(group, channel)
        return channel

    def receive(self, channel, event_type='notification.created'):
        return async_to_sync(self._receive)(channel, event_type)

    async def _receive(self, channel, event_type):
        layer = get_channel_layer()
        seen = []
        for _ in range(5):
            message = await asyncio.wait_for(layer.receive(channel), timeout=1)
            payload = message['payload']
            seen.append(payload['type'])
            if payload['type'] == event_type:
                return payload
        self.fail(f'Did not receive {event_type}; saw {seen}.')

    def assert_no_message(self, channel):
        async_to_sync(self._assert_no_message)(channel)

    async def _assert_no_message(self, channel):
        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(get_channel_layer().receive(channel), timeout=0.1)

    def _merchant_with_branch(self, suffix='rt'):
        owner = User.objects.create_user(username=f'rt-merchant-{suffix}')
        merchant = MerchantProfile.objects.create(
            user=owner,
            business_name=f'RT Merchant {suffix}',
            is_verified=True,
            verification_status='VERIFIED',
        )
        branch = Restaurant.objects.create(
            owner=owner,
            rest_name=f'RT Branch {suffix}',
            rest_email=f'rt-branch-{suffix}@example.com',
            rest_contact='9999999999',
            rest_address='Realtime road',
            rest_city='Realtime City',
            is_active=True,
        )
        return merchant, branch

    def _market(self, suffix='rt-market', country_code='IN'):
        currency, _ = Currency.objects.get_or_create(
            code=f'X{suffix[:2].upper()}',
            defaults={'name': f'Currency {suffix}'},
        )
        market, _ = Market.objects.get_or_create(
            slug=suffix,
            defaults={
                'name': f'Market {suffix}',
                'country_code': country_code,
                'default_currency': currency,
            },
        )
        return market

    def assert_notification_payload(self, payload, notification):
        self.assertEqual(payload['type'], 'notification.created')
        self.assertEqual(payload['notification_id'], notification.id)
        self.assertEqual(payload['recipient_type'], notification.recipient_type)
        self.assertEqual(payload['category'], notification.category)
        self.assertEqual(payload['event_type'], notification.event_type)
        self.assertEqual(payload['priority'], notification.priority)
        self.assertEqual(payload['status'], notification.status)
        self.assertEqual(payload['title'], notification.title)
        self.assertEqual(payload['message'], notification.message)
        self.assertIn('created_at', payload)

    def test_customer_receives_notification_created(self):
        user = User.objects.create_user(username='rt-customer')
        channel = self.listen(f'user_{user.id}')

        result = notify_event(
            'order.placed',
            recipients=[user],
            payload={'title': 'Order placed', 'message': 'Realtime order.'},
            category=Notification.CATEGORY_ORDER,
        )

        notification = result.notifications[0]
        self.assert_notification_payload(self.receive(channel), notification)
        self.assertTrue(NotificationDeliveryAttempt.objects.filter(
            notification=notification,
            channel=NotificationDeliveryAttempt.CHANNEL_REALTIME,
            status=NotificationDeliveryAttempt.STATUS_SENT,
        ).exists())

    def test_merchant_owner_receives_notification_created(self):
        merchant, branch = self._merchant_with_branch('owner')
        channel = self.listen(f'merchant_{merchant.user_id}')

        result = notify_event(
            'merchant.alert',
            recipients={'merchant': merchant},
            scope={'branch': branch},
            payload={'title': 'Merchant alert', 'message': 'Realtime merchant.'},
            category=Notification.CATEGORY_MERCHANT,
        )

        self.assert_notification_payload(self.receive(channel), result.notifications[0])

    def test_merchant_staff_receives_branch_scoped_notification(self):
        merchant, branch = self._merchant_with_branch('staff')
        staff_user = User.objects.create_user(username='rt-kitchen-staff')
        staff = MerchantStaffMember.objects.create(
            merchant=merchant,
            user=staff_user,
            role=MerchantStaffMember.ROLE_KITCHEN_STAFF,
            membership_status=MerchantStaffMember.STATUS_ACTIVE,
            verification_status=MerchantStaffMember.VERIFICATION_VERIFIED,
        )
        MerchantStaffBranchAccess.objects.create(staff_member=staff, branch=branch)
        user_channel = self.listen(f'user_{staff_user.id}')
        branch_channel = self.listen(f'branch_{branch.id}')

        result = notify_event(
            'order.preparation',
            recipients={
                'merchant_staff': {
                    'merchant': merchant,
                    'branch': branch,
                    'roles': [MerchantStaffMember.ROLE_KITCHEN_STAFF],
                },
            },
            scope={'branch': branch},
            payload={'title': 'Prepare order', 'message': 'Branch scoped.'},
            category=Notification.CATEGORY_ORDER,
        )

        notification = result.notifications[0]
        self.assert_notification_payload(self.receive(user_channel), notification)
        self.assert_notification_payload(self.receive(branch_channel), notification)

    def test_delivery_partner_receives_own_notification(self):
        from delivery.models import DeliveryPartner

        partner_user = User.objects.create_user(username='rt-partner')
        partner = DeliveryPartner.objects.create(
            user=partner_user,
            partner_name='RT Partner',
            partner_phone='9000000000',
            transport_details='Bike',
        )
        channel = self.listen(f'partner_{partner_user.id}')

        result = notify_event(
            'delivery.assigned',
            recipients={'delivery_partner': partner},
            payload={'title': 'New delivery', 'message': 'Go pick it up.'},
            category=Notification.CATEGORY_DELIVERY,
        )

        self.assert_notification_payload(self.receive(channel), result.notifications[0])

    def test_global_operations_receives_global_notification(self):
        admin = User.objects.create_superuser(
            username='rt-global-admin',
            email='rt-global@example.com',
            password='pass',
        )
        channel = self.listen('operations_global')

        result = notify_event(
            'operations.global',
            recipients={'operations': True},
            payload={'title': 'Global ops', 'message': 'Realtime operations.'},
        )

        self.assertEqual(result.notifications[0].user, admin)
        self.assert_notification_payload(self.receive(channel), result.notifications[0])

    def test_country_admin_receives_only_country_notification(self):
        market = self._market('rt-india-country', 'AA')
        currency = Currency.objects.create(code='GNF', name='Guinean franc')
        guinea = Market.objects.create(
            slug='rt-guinea-country',
            name='RT Guinea Country',
            country_code='GN',
            default_currency=currency,
        )
        user = User.objects.create_user(username='rt-country-admin')
        profile = OperationsStaffProfile.objects.create(
            user=user,
            role=OperationsStaffProfile.ROLE_COUNTRY_ADMIN,
            status=OperationsStaffProfile.STATUS_ACTIVE,
        )
        from operations_access.models import OperationsStaffMarketAccess
        OperationsStaffMarketAccess.objects.create(profile=profile, market=market)
        india_channel = self.listen(f'operations_market_{market.id}')
        guinea_channel = self.listen(f'operations_market_{guinea.id}')

        result = notify_event(
            'operations.india',
            recipients={'operations': True},
            scope={'market': market},
            payload={'title': 'India ops', 'message': 'In scope.'},
        )
        out_of_scope = notify_event(
            'operations.guinea',
            recipients={'operations': True},
            scope={'market': guinea},
            payload={'title': 'Guinea ops', 'message': 'Out of scope.'},
        )

        self.assertEqual(len(result.notifications), 1)
        self.assertEqual(out_of_scope.notifications, [])
        self.assert_notification_payload(self.receive(india_channel), result.notifications[0])
        self.assert_no_message(guinea_channel)

    def test_city_and_area_admin_receive_scoped_notifications(self):
        market = self._market('rt-city-area', 'AB')
        city = CommerceCity.objects.create(
            market=market,
            name='RT City',
            slug='rt-city',
        )
        area = CommerceArea.objects.create(
            market=market,
            city=city,
            name='RT Area',
            slug='rt-area',
        )
        city_user = User.objects.create_user(username='rt-city-admin')
        city_profile = OperationsStaffProfile.objects.create(
            user=city_user,
            role=OperationsStaffProfile.ROLE_CITY_ADMIN,
            status=OperationsStaffProfile.STATUS_ACTIVE,
        )
        area_user = User.objects.create_user(username='rt-area-admin')
        area_profile = OperationsStaffProfile.objects.create(
            user=area_user,
            role=OperationsStaffProfile.ROLE_AREA_ADMIN,
            status=OperationsStaffProfile.STATUS_ACTIVE,
        )
        from operations_access.models import (
            OperationsStaffAreaAccess,
            OperationsStaffCityAccess,
        )
        OperationsStaffCityAccess.objects.create(profile=city_profile, city=city)
        OperationsStaffAreaAccess.objects.create(profile=area_profile, area=area)
        city_channel = self.listen(f'operations_city_{city.id}')
        area_channel = self.listen(f'operations_area_{area.id}')

        result = notify_event(
            'operations.area',
            recipients={'operations': True},
            scope={'area': area},
            payload={'title': 'Area ops', 'message': 'Scoped area.'},
        )

        self.assertEqual(len(result.notifications), 2)
        self.assertEqual(self.receive(city_channel)['type'], 'notification.created')
        self.assertEqual(self.receive(area_channel)['type'], 'notification.created')

    def test_unknown_scope_does_not_leak_to_scoped_operations(self):
        market = self._market('rt-unknown-scope', 'AC')
        user = User.objects.create_user(username='rt-scoped-no-leak')
        profile = OperationsStaffProfile.objects.create(
            user=user,
            role=OperationsStaffProfile.ROLE_COUNTRY_ADMIN,
            status=OperationsStaffProfile.STATUS_ACTIVE,
        )
        from operations_access.models import OperationsStaffMarketAccess
        OperationsStaffMarketAccess.objects.create(profile=profile, market=market)
        channel = self.listen(f'operations_market_{market.id}')

        result = notify_event(
            'operations.unknown',
            recipients={'operations': True},
            payload={'title': 'Unknown', 'message': 'No scope.'},
        )

        self.assertEqual(result.notifications, [])
        self.assert_no_message(channel)

    def test_realtime_failure_does_not_fail_notification_creation(self):
        user = User.objects.create_user(username='rt-failure-user')

        class FailingLayer:
            async def group_send(self, group, message):
                raise RuntimeError('send failed')

        with patch('notifications.realtime.get_channel_layer', return_value=FailingLayer()):
            result = notify_event(
                'notification.failure',
                recipients=[user],
                payload={'title': 'Still created', 'message': 'Broadcast failed.'},
            )

        notification = result.notifications[0]
        self.assertEqual(Notification.objects.filter(id=notification.id).count(), 1)
        self.assertTrue(NotificationDeliveryAttempt.objects.filter(
            notification=notification,
            channel=NotificationDeliveryAttempt.CHANNEL_REALTIME,
            status=NotificationDeliveryAttempt.STATUS_FAILED,
        ).exists())


class NotificationTaskTests(TransactionTestCase):
    @override_settings(
        NOTIFICATIONS_ASYNC_ENABLED=True,
        CELERY_TASK_ALWAYS_EAGER=True,
        CELERY_TASK_EAGER_PROPAGATES=True,
    )
    def test_notify_uses_task_when_feature_flag_is_enabled(self):
        user = User.objects.create_user(username='async-notification-user')

        result = notify(
            user,
            'ACCOUNT',
            'Async welcome',
            'Your account is ready.',
        )

        notification = Notification.objects.get(user=user)
        self.assertIsNone(result)
        self.assertEqual(notification.title, 'Async welcome')

    def test_notification_task_ignores_missing_user_idempotently(self):
        result = create_notification_task.apply(args=[
            999999,
            'ACCOUNT',
            'Missing user',
            'This should not fail.',
        ]).get()

        self.assertIsNone(result)
        self.assertEqual(Notification.objects.count(), 0)

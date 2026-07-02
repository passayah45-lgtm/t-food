from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.utils import timezone

from .models import Notification, NotificationDeliveryAttempt
from .preferences import realtime_enabled


def notification_realtime_payload(notification):
    return {
        'type': 'notification.created',
        'notification_id': notification.id,
        'recipient_type': notification.recipient_type,
        'category': notification.category,
        'event_type': notification.event_type,
        'priority': notification.priority,
        'status': notification.status,
        'title': notification.title,
        'message': notification.message,
        'action_url': notification.action_url,
        'created_at': notification.created_at.isoformat()
        if notification.created_at else None,
    }


def notification_realtime_groups(notification):
    groups = {f'user_{notification.user_id}'}
    if notification.recipient_type == Notification.RECIPIENT_MERCHANT_OWNER:
        groups.add(f'merchant_{notification.user_id}')
    elif notification.recipient_type == Notification.RECIPIENT_DELIVERY_PARTNER:
        groups.add(f'partner_{notification.user_id}')
    elif notification.recipient_type in {
        Notification.RECIPIENT_OPERATIONS,
        Notification.RECIPIENT_GLOBAL_ADMIN,
        Notification.RECIPIENT_COUNTRY_ADMIN,
        Notification.RECIPIENT_CITY_ADMIN,
        Notification.RECIPIENT_AREA_ADMIN,
    }:
        if notification.recipient_type == Notification.RECIPIENT_GLOBAL_ADMIN:
            groups.add('operations_global')
        if notification.market_id:
            groups.add(f'operations_market_{notification.market_id}')
        if notification.country_code:
            groups.add(f'operations_country_{notification.country_code.upper()}')
        if notification.city_id:
            groups.add(f'operations_city_{notification.city_id}')
        if notification.area_id:
            groups.add(f'operations_area_{notification.area_id}')
        if not any(group.startswith('operations_') for group in groups):
            groups.add('operations_global')
    if notification.branch_id:
        groups.add(f'branch_{notification.branch_id}')
    return sorted(groups)


def broadcast_notification_created(notification_id):
    notification = (
        Notification.objects
        .select_related('user', 'market', 'city', 'area', 'branch')
        .filter(id=notification_id)
        .first()
    )
    if not notification:
        return None
    attempt = NotificationDeliveryAttempt.objects.create(
        notification=notification,
        channel=NotificationDeliveryAttempt.CHANNEL_REALTIME,
        status=NotificationDeliveryAttempt.STATUS_PENDING,
    )
    if not realtime_enabled(notification):
        attempt.status = NotificationDeliveryAttempt.STATUS_SKIPPED
        attempt.error_message = 'Realtime notifications are disabled by preference.'
        attempt.attempted_at = timezone.now()
        attempt.save(update_fields=('status', 'error_message', 'attempted_at'))
        return attempt
    channel_layer = get_channel_layer()
    if channel_layer is None:
        attempt.status = NotificationDeliveryAttempt.STATUS_SKIPPED
        attempt.error_message = 'Realtime channel layer is not configured.'
        attempt.attempted_at = timezone.now()
        attempt.save(update_fields=('status', 'error_message', 'attempted_at'))
        return attempt
    try:
        payload = notification_realtime_payload(notification)
        for group in notification_realtime_groups(notification):
            async_to_sync(channel_layer.group_send)(
                group,
                {
                    'type': 'realtime.message',
                    'payload': payload,
                },
            )
    except Exception as exc:
        attempt.status = NotificationDeliveryAttempt.STATUS_FAILED
        attempt.error_message = str(exc)
    else:
        attempt.status = NotificationDeliveryAttempt.STATUS_SENT
        attempt.error_message = ''
    attempt.attempted_at = timezone.now()
    attempt.save(update_fields=('status', 'error_message', 'attempted_at'))
    return attempt


def broadcast_notification_created_on_commit(notification_id):
    transaction.on_commit(lambda: broadcast_notification_created(notification_id))

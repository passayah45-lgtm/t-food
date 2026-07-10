from django.db import transaction
from django.conf import settings

from .models import Notification, NotificationDeliveryAttempt, NotificationPreference


BASE_ACTIVE_NOTIFICATION_CHANNELS = {
    NotificationDeliveryAttempt.CHANNEL_IN_APP,
    NotificationDeliveryAttempt.CHANNEL_REALTIME,
}


def active_notification_channels():
    channels = set(BASE_ACTIVE_NOTIFICATION_CHANNELS)
    if getattr(settings, 'EMAIL_NOTIFICATIONS_ENABLED', False):
        channels.add(NotificationDeliveryAttempt.CHANNEL_EMAIL)
    return channels


def default_enabled_for_channel(channel):
    return channel in active_notification_channels()


def preference_categories():
    return [choice[0] for choice in Notification.CATEGORY_CHOICES]


def preference_channels():
    return [choice[0] for choice in NotificationPreference.CHANNEL_CHOICES]


def default_preference_payload(category, channel):
    return {
        'category': category,
        'channel': channel,
        'enabled': default_enabled_for_channel(channel),
        'quiet_hours_enabled': False,
        'quiet_hours_start': None,
        'quiet_hours_end': None,
        'language': 'en',
    }


def ensure_default_preferences(user):
    if not user or not getattr(user, 'id', None):
        return []
    preferences = []
    with transaction.atomic():
        for category in preference_categories():
            for channel in preference_channels():
                preference, _ = NotificationPreference.objects.get_or_create(
                    user=user,
                    category=category,
                    channel=channel,
                    defaults=default_preference_payload(category, channel),
                )
                preferences.append(preference)
    return preferences


def preference_enabled(user, category, channel):
    if not user or not getattr(user, 'id', None):
        return False
    preference = NotificationPreference.objects.filter(
        user=user,
        category=category or Notification.CATEGORY_SYSTEM,
        channel=channel,
    ).first()
    if not preference:
        return default_enabled_for_channel(channel)
    if channel not in active_notification_channels():
        return False
    return preference.enabled


def in_app_enabled(user, category):
    return preference_enabled(
        user,
        category,
        NotificationDeliveryAttempt.CHANNEL_IN_APP,
    )


def realtime_enabled(notification):
    return preference_enabled(
        notification.user,
        notification.category,
        NotificationDeliveryAttempt.CHANNEL_REALTIME,
    )

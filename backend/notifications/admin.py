from django.contrib import admin

from .models import (
    Notification,
    NotificationDevice,
    NotificationDeliveryAttempt,
    NotificationPreference,
    NotificationTemplate,
)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'recipient_type', 'category', 'priority', 'status',
        'kind', 'title', 'order', 'branch', 'is_read', 'created_at',
    )
    list_filter = (
        'recipient_type', 'category', 'priority', 'status', 'kind',
        'is_read', 'market', 'country_code', 'created_at',
    )
    search_fields = (
        'user__username', 'title', 'message', 'order__id',
        'event_type', 'idempotency_key',
    )
    readonly_fields = ('created_at',)


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ('code', 'language', 'category', 'event_type', 'is_active')
    list_filter = ('category', 'language', 'is_active')
    search_fields = ('code', 'event_type', 'title_template', 'message_template')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(NotificationDeliveryAttempt)
class NotificationDeliveryAttemptAdmin(admin.ModelAdmin):
    list_display = (
        'notification', 'channel', 'status', 'provider_code',
        'attempted_at', 'created_at',
    )
    list_filter = ('channel', 'status', 'provider_code', 'created_at')
    search_fields = (
        'notification__title', 'notification__user__username',
        'provider_code', 'error_message',
    )
    readonly_fields = ('created_at',)


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'category', 'channel', 'enabled',
        'quiet_hours_enabled', 'language', 'updated_at',
    )
    list_filter = (
        'category', 'channel', 'enabled',
        'quiet_hours_enabled', 'language',
    )
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(NotificationDevice)
class NotificationDeviceAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'device_type', 'device_identifier',
        'is_active', 'created_at', 'updated_at',
    )
    list_filter = ('device_type', 'is_active', 'created_at')
    search_fields = (
        'user__username', 'user__email',
        'device_identifier', 'push_token',
    )
    readonly_fields = ('created_at', 'updated_at')

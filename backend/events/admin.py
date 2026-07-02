from django.contrib import admin

from .models import InboxEvent, OutboxEvent


@admin.register(OutboxEvent)
class OutboxEventAdmin(admin.ModelAdmin):
    list_display = (
        'event_name',
        'event_version',
        'aggregate_type',
        'aggregate_id',
        'status',
        'attempts',
        'available_at',
        'published_at',
    )
    list_filter = ('status', 'event_name', 'event_version')
    search_fields = ('event_id', 'aggregate_type', 'aggregate_id')
    readonly_fields = (
        'event_id',
        'created_at',
        'updated_at',
        'published_at',
        'payload',
        'headers',
        'last_error',
    )
    ordering = ('status', 'available_at', 'id')


@admin.register(InboxEvent)
class InboxEventAdmin(admin.ModelAdmin):
    list_display = (
        'consumer',
        'event_name',
        'event_version',
        'status',
        'attempts',
        'processed_at',
        'created_at',
    )
    list_filter = ('consumer', 'status', 'event_name')
    search_fields = ('event_id', 'consumer', 'payload_hash')
    readonly_fields = (
        'event_id',
        'created_at',
        'updated_at',
        'processed_at',
        'payload',
        'headers',
        'last_error',
    )
    ordering = ('-created_at',)


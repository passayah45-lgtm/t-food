import uuid

from django.db import models
from django.utils import timezone


class OutboxEvent(models.Model):
    STATUS_PENDING = 'PENDING'
    STATUS_PUBLISHED = 'PUBLISHED'
    STATUS_FAILED = 'FAILED'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PUBLISHED, 'Published'),
        (STATUS_FAILED, 'Failed'),
    ]

    event_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    event_name = models.CharField(max_length=100)
    event_version = models.PositiveSmallIntegerField(default=1)
    aggregate_type = models.CharField(max_length=80)
    aggregate_id = models.CharField(max_length=80)
    payload = models.JSONField(default=dict)
    headers = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now)
    published_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('created_at', 'id')
        indexes = [
            models.Index(fields=('status', 'available_at', 'id')),
            models.Index(fields=('aggregate_type', 'aggregate_id')),
            models.Index(fields=('event_name', 'event_version')),
        ]

    def mark_published(self):
        self.status = self.STATUS_PUBLISHED
        self.published_at = timezone.now()
        self.last_error = ''
        self.save(update_fields=('status', 'published_at', 'last_error', 'updated_at'))

    def mark_failed(self, error: str):
        self.status = self.STATUS_FAILED
        self.attempts += 1
        self.last_error = str(error)[:4000]
        self.save(update_fields=('status', 'attempts', 'last_error', 'updated_at'))

    def __str__(self):
        return f'{self.event_name}.v{self.event_version} ({self.status})'


class InboxEvent(models.Model):
    STATUS_RECEIVED = 'RECEIVED'
    STATUS_PROCESSED = 'PROCESSED'
    STATUS_FAILED = 'FAILED'
    STATUS_CHOICES = [
        (STATUS_RECEIVED, 'Received'),
        (STATUS_PROCESSED, 'Processed'),
        (STATUS_FAILED, 'Failed'),
    ]

    event_id = models.UUIDField()
    consumer = models.CharField(max_length=100)
    event_name = models.CharField(max_length=100)
    event_version = models.PositiveSmallIntegerField(default=1)
    payload_hash = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    headers = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_RECEIVED,
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    processed_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=('consumer', 'status', 'created_at')),
            models.Index(fields=('event_name', 'event_version')),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=('event_id', 'consumer'),
                name='unique_inbox_event_per_consumer',
            ),
        ]

    def mark_processed(self):
        self.status = self.STATUS_PROCESSED
        self.processed_at = timezone.now()
        self.last_error = ''
        self.save(update_fields=('status', 'processed_at', 'last_error', 'updated_at'))

    def mark_failed(self, error: str):
        self.status = self.STATUS_FAILED
        self.attempts += 1
        self.last_error = str(error)[:4000]
        self.save(update_fields=('status', 'attempts', 'last_error', 'updated_at'))

    def __str__(self):
        return f'{self.consumer}: {self.event_name}.v{self.event_version}'


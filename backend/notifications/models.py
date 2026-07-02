from django.conf import settings
from django.db import models
from django.db.models import Q


class Notification(models.Model):
    RECIPIENT_CUSTOMER = 'CUSTOMER'
    RECIPIENT_MERCHANT_OWNER = 'MERCHANT_OWNER'
    RECIPIENT_MERCHANT_STAFF = 'MERCHANT_STAFF'
    RECIPIENT_DELIVERY_PARTNER = 'DELIVERY_PARTNER'
    RECIPIENT_OPERATIONS = 'OPERATIONS'
    RECIPIENT_GLOBAL_ADMIN = 'GLOBAL_ADMIN'
    RECIPIENT_COUNTRY_ADMIN = 'COUNTRY_ADMIN'
    RECIPIENT_CITY_ADMIN = 'CITY_ADMIN'
    RECIPIENT_AREA_ADMIN = 'AREA_ADMIN'
    RECIPIENT_SYSTEM = 'SYSTEM'
    RECIPIENT_TYPE_CHOICES = [
        (RECIPIENT_CUSTOMER, 'Customer'),
        (RECIPIENT_MERCHANT_OWNER, 'Merchant owner'),
        (RECIPIENT_MERCHANT_STAFF, 'Merchant staff'),
        (RECIPIENT_DELIVERY_PARTNER, 'Delivery partner'),
        (RECIPIENT_OPERATIONS, 'Operations'),
        (RECIPIENT_GLOBAL_ADMIN, 'Global admin'),
        (RECIPIENT_COUNTRY_ADMIN, 'Country admin'),
        (RECIPIENT_CITY_ADMIN, 'City admin'),
        (RECIPIENT_AREA_ADMIN, 'Area admin'),
        (RECIPIENT_SYSTEM, 'System'),
    ]

    CATEGORY_ORDER = 'ORDER'
    CATEGORY_PAYMENT = 'PAYMENT'
    CATEGORY_DELIVERY = 'DELIVERY'
    CATEGORY_MERCHANT = 'MERCHANT'
    CATEGORY_STAFF = 'STAFF'
    CATEGORY_RIDER = 'RIDER'
    CATEGORY_SUPPORT = 'SUPPORT'
    CATEGORY_VERIFICATION = 'VERIFICATION'
    CATEGORY_DISPATCH = 'DISPATCH'
    CATEGORY_INTELLIGENCE = 'INTELLIGENCE'
    CATEGORY_SYSTEM = 'SYSTEM'
    CATEGORY_CHOICES = [
        (CATEGORY_ORDER, 'Order'),
        (CATEGORY_PAYMENT, 'Payment'),
        (CATEGORY_DELIVERY, 'Delivery'),
        (CATEGORY_MERCHANT, 'Merchant'),
        (CATEGORY_STAFF, 'Staff'),
        (CATEGORY_RIDER, 'Rider'),
        (CATEGORY_SUPPORT, 'Support'),
        (CATEGORY_VERIFICATION, 'Verification'),
        (CATEGORY_DISPATCH, 'Dispatch'),
        (CATEGORY_INTELLIGENCE, 'Intelligence'),
        (CATEGORY_SYSTEM, 'System'),
    ]

    PRIORITY_LOW = 'LOW'
    PRIORITY_NORMAL = 'NORMAL'
    PRIORITY_HIGH = 'HIGH'
    PRIORITY_CRITICAL = 'CRITICAL'
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_NORMAL, 'Normal'),
        (PRIORITY_HIGH, 'High'),
        (PRIORITY_CRITICAL, 'Critical'),
    ]

    STATUS_UNREAD = 'UNREAD'
    STATUS_READ = 'READ'
    STATUS_ARCHIVED = 'ARCHIVED'
    STATUS_DISMISSED = 'DISMISSED'
    STATUS_CHOICES = [
        (STATUS_UNREAD, 'Unread'),
        (STATUS_READ, 'Read'),
        (STATUS_ARCHIVED, 'Archived'),
        (STATUS_DISMISSED, 'Dismissed'),
    ]

    KIND_CHOICES = [
        ('ORDER', 'Order'),
        ('PAYMENT', 'Payment'),
        ('DELIVERY', 'Delivery'),
        ('ACCOUNT', 'Account'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    market = models.ForeignKey(
        'markets.Market',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='notifications',
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    recipient_type = models.CharField(
        max_length=30,
        choices=RECIPIENT_TYPE_CHOICES,
        default=RECIPIENT_SYSTEM,
    )
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_SYSTEM,
    )
    event_type = models.CharField(max_length=80, blank=True)
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default=PRIORITY_NORMAL,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_UNREAD,
    )
    title = models.CharField(max_length=120)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    action_url = models.CharField(max_length=500, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(
        max_length=160,
        null=True,
        blank=True,
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    auto_archive_after = models.DurationField(null=True, blank=True)
    country_code = models.CharField(max_length=2, null=True, blank=True)
    city = models.ForeignKey(
        'markets.CommerceCity',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='notifications',
    )
    area = models.ForeignKey(
        'markets.CommerceArea',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='notifications',
    )
    branch = models.ForeignKey(
        'restaurants.Restaurant',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='notifications',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=('user', 'is_read', '-created_at')),
            models.Index(fields=('user', 'status', '-created_at')),
            models.Index(fields=('category', 'priority', '-created_at')),
            models.Index(fields=('market', 'country_code', '-created_at')),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=('idempotency_key',),
                condition=Q(idempotency_key__isnull=False),
                name='unique_notification_idempotency_key',
            ),
        ]

    def __str__(self):
        return f'{self.user}: {self.title}'

    def save(self, *args, **kwargs):
        if self.idempotency_key == '':
            self.idempotency_key = None
        if self.country_code:
            self.country_code = self.country_code.upper()
        if self.category == self.CATEGORY_SYSTEM and self.kind in {
            self.CATEGORY_ORDER,
            self.CATEGORY_PAYMENT,
            self.CATEGORY_DELIVERY,
        }:
            self.category = self.kind
        if self.is_read and self.status == self.STATUS_UNREAD:
            self.status = self.STATUS_READ
        elif self.status in {
            self.STATUS_READ,
            self.STATUS_ARCHIVED,
            self.STATUS_DISMISSED,
        }:
            self.is_read = True
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            update_fields = set(update_fields)
            if 'is_read' in update_fields and self.status == self.STATUS_READ:
                update_fields.add('status')
            if 'status' in update_fields and self.is_read:
                update_fields.add('is_read')
            if 'idempotency_key' in update_fields and self.idempotency_key is None:
                update_fields.add('idempotency_key')
            kwargs['update_fields'] = update_fields
        super().save(*args, **kwargs)


class NotificationTemplate(models.Model):
    code = models.CharField(max_length=120)
    category = models.CharField(
        max_length=30,
        choices=Notification.CATEGORY_CHOICES,
    )
    event_type = models.CharField(max_length=80, blank=True)
    language = models.CharField(max_length=12, default='en')
    title_template = models.CharField(max_length=200)
    message_template = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('code', 'language')
        constraints = [
            models.UniqueConstraint(
                fields=('code', 'language'),
                name='unique_notification_template_code_language',
            ),
        ]

    def __str__(self):
        return f'{self.code} ({self.language})'


class NotificationDeliveryAttempt(models.Model):
    CHANNEL_IN_APP = 'IN_APP'
    CHANNEL_REALTIME = 'REALTIME'
    CHANNEL_EMAIL = 'EMAIL'
    CHANNEL_SMS = 'SMS'
    CHANNEL_PUSH = 'PUSH'
    CHANNEL_WHATSAPP = 'WHATSAPP'
    CHANNEL_TELEGRAM = 'TELEGRAM'
    CHANNEL_CHOICES = [
        (CHANNEL_IN_APP, 'In-app'),
        (CHANNEL_REALTIME, 'Realtime'),
        (CHANNEL_EMAIL, 'Email'),
        (CHANNEL_SMS, 'SMS'),
        (CHANNEL_PUSH, 'Push'),
        (CHANNEL_WHATSAPP, 'WhatsApp'),
        (CHANNEL_TELEGRAM, 'Telegram'),
    ]

    STATUS_PENDING = 'PENDING'
    STATUS_SENT = 'SENT'
    STATUS_FAILED = 'FAILED'
    STATUS_SKIPPED = 'SKIPPED'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_SENT, 'Sent'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_SKIPPED, 'Skipped'),
    ]

    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name='delivery_attempts',
    )
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    provider_code = models.CharField(max_length=60, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    attempted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=('channel', 'status', '-created_at')),
        ]

    def __str__(self):
        return f'{self.notification_id}: {self.channel} {self.status}'


class NotificationPreference(models.Model):
    CHANNEL_IN_APP = NotificationDeliveryAttempt.CHANNEL_IN_APP
    CHANNEL_REALTIME = NotificationDeliveryAttempt.CHANNEL_REALTIME
    CHANNEL_EMAIL = NotificationDeliveryAttempt.CHANNEL_EMAIL
    CHANNEL_SMS = NotificationDeliveryAttempt.CHANNEL_SMS
    CHANNEL_PUSH = NotificationDeliveryAttempt.CHANNEL_PUSH
    CHANNEL_WHATSAPP = NotificationDeliveryAttempt.CHANNEL_WHATSAPP
    CHANNEL_TELEGRAM = NotificationDeliveryAttempt.CHANNEL_TELEGRAM
    CHANNEL_CHOICES = NotificationDeliveryAttempt.CHANNEL_CHOICES

    ACTIVE_CHANNELS = {CHANNEL_IN_APP, CHANNEL_REALTIME}

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences',
    )
    category = models.CharField(
        max_length=30,
        choices=Notification.CATEGORY_CHOICES,
    )
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    enabled = models.BooleanField(default=True)
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    language = models.CharField(max_length=12, default='en')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('category', 'channel')
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'category', 'channel'),
                name='unique_notification_preference_user_category_channel',
            ),
        ]
        indexes = [
            models.Index(fields=('user', 'category', 'channel')),
            models.Index(fields=('channel', 'enabled')),
        ]

    @property
    def is_active_channel(self):
        return self.channel in self.ACTIVE_CHANNELS

    @property
    def effective_enabled(self):
        return self.enabled and self.is_active_channel

    def __str__(self):
        return f'{self.user}: {self.category} {self.channel}'


class NotificationDevice(models.Model):
    DEVICE_WEB = 'WEB'
    DEVICE_ANDROID = 'ANDROID'
    DEVICE_IOS = 'IOS'
    DEVICE_TYPE_CHOICES = [
        (DEVICE_WEB, 'Web'),
        (DEVICE_ANDROID, 'Android'),
        (DEVICE_IOS, 'iOS'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_devices',
    )
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPE_CHOICES)
    device_identifier = models.CharField(max_length=160)
    push_token = models.CharField(max_length=500, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-updated_at', '-created_at')
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'device_identifier'),
                name='unique_notification_device_user_identifier',
            ),
        ]
        indexes = [
            models.Index(fields=('user', 'device_type', 'is_active')),
            models.Index(fields=('device_identifier',)),
        ]

    def __str__(self):
        return f'{self.user}: {self.device_type} {self.device_identifier}'

from django.db import models
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from fooddelivery.gis_fields import PointField
from fooddelivery.gis_utils import sync_point_from_lat_lng
from fooddelivery.media_storage import (
    attach_private_upload,
    publish_private_file_to_public,
)
from markets.models import country_code_validator
from restaurants.image_validation import (
    strip_review_photo_exif,
    validate_review_photo_image,
)
from verifications.constants import (
    VERIFICATION_PENDING,
    VERIFICATION_STATUS_CHOICES,
)


class Restaurant(models.Model):
    BRANCH_TYPE_FOOD = 'FOOD'
    BRANCH_TYPE_GROCERY = 'GROCERY'
    BRANCH_TYPE_PHARMACY = 'PHARMACY'
    BRANCH_TYPE_RETAIL = 'RETAIL'
    BRANCH_TYPE_COURIER = 'COURIER'
    BRANCH_TYPE_LOCAL_COMMERCE = 'LOCAL_COMMERCE'
    BRANCH_TYPE_CHOICES = [
        (BRANCH_TYPE_FOOD, 'Food'),
        (BRANCH_TYPE_GROCERY, 'Grocery'),
        (BRANCH_TYPE_PHARMACY, 'Pharmacy'),
        (BRANCH_TYPE_RETAIL, 'Retail'),
        (BRANCH_TYPE_COURIER, 'Courier'),
        (BRANCH_TYPE_LOCAL_COMMERCE, 'Local commerce'),
    ]

    market = models.ForeignKey(
        'markets.Market',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='restaurants',
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_restaurants',
    )
    rest_name = models.CharField(max_length=100)
    rest_email = models.EmailField(unique=True)
    rest_contact = models.CharField(max_length=15)
    rest_address = models.TextField()
    rest_city = models.CharField(max_length=50)
    branch_name = models.CharField(max_length=120, blank=True)
    branch_code = models.CharField(max_length=40, blank=True, null=True)
    branch_type = models.CharField(
        max_length=30,
        choices=BRANCH_TYPE_CHOICES,
        default=BRANCH_TYPE_FOOD,
    )
    country_code = models.CharField(
        max_length=2,
        blank=True,
        validators=[country_code_validator],
    )
    city_ref = models.ForeignKey(
        'markets.CommerceCity',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='branches',
    )
    area_ref = models.ForeignKey(
        'markets.CommerceArea',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='branches',
    )
    branch_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_branches',
    )
    pickup_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    pickup_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    pickup_point = PointField(srid=4326, null=True, blank=True)
    delivery_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    delivery_radius_km = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=15,
        validators=[MinValueValidator(1), MaxValueValidator(50)],
    )
    estimated_prep_minutes = models.PositiveSmallIntegerField(
        default=25,
        validators=[MinValueValidator(5), MaxValueValidator(180)],
    )
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    commission_percent = models.PositiveSmallIntegerField(
        default=15,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    cover_image = models.ImageField(
        upload_to='restaurants/covers/',
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    is_open = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return self.rest_name

    def save(self, *args, **kwargs):
        if not self.branch_name:
            self.branch_name = self.rest_name
            update_fields = kwargs.get('update_fields')
            if update_fields is not None and 'branch_name' not in update_fields:
                kwargs['update_fields'] = set(update_fields) | {'branch_name'}
        if self.market_id and not self.country_code:
            self.country_code = self.market.country_code
            update_fields = kwargs.get('update_fields')
            if update_fields is not None and 'country_code' not in update_fields:
                kwargs['update_fields'] = set(update_fields) | {'country_code'}
        if self.country_code:
            self.country_code = self.country_code.upper()
        kwargs['update_fields'] = sync_point_from_lat_lng(
            self,
            point_field='pickup_point',
            latitude_field='pickup_latitude',
            longitude_field='pickup_longitude',
            update_fields=kwargs.get('update_fields'),
        )
        super().save(*args, **kwargs)


class FoodItem(models.Model):
    CATEGORY_CHOICES = [
        ('Vegetarian', 'Vegetarian'),
        ('Non-Vegetarian', 'Non-Vegetarian'),
        ('Beverages', 'Beverages'),
        ('Desserts', 'Desserts'),
    ]

    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name='food_items'
    )
    food_name = models.CharField(max_length=100)
    food_desc = models.TextField(blank=True)
    food_price = models.DecimalField(max_digits=8, decimal_places=2)
    food_categ = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    is_available = models.BooleanField(default=True)
    image = models.ImageField(
        upload_to='restaurants/items/',
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.food_name


class FoodOptionGroup(models.Model):
    food = models.ForeignKey(
        FoodItem,
        on_delete=models.CASCADE,
        related_name='option_groups',
    )
    name = models.CharField(max_length=80)
    min_select = models.PositiveSmallIntegerField(default=0)
    max_select = models.PositiveSmallIntegerField(default=1)
    ordering = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ('ordering', 'id')

    def __str__(self):
        return f'{self.food}: {self.name}'


class FoodOption(models.Model):
    group = models.ForeignKey(
        FoodOptionGroup,
        on_delete=models.CASCADE,
        related_name='options',
    )
    name = models.CharField(max_length=80)
    price_delta = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_available = models.BooleanField(default=True)
    ordering = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ('ordering', 'id')

    def __str__(self):
        return f'{self.group}: {self.name}'


class RestaurantOperatingHour(models.Model):
    DAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]

    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name='operating_hours',
    )
    day_of_week = models.PositiveSmallIntegerField(choices=DAY_CHOICES)
    is_closed = models.BooleanField(default=False)
    opens_at = models.TimeField(default='09:00')
    closes_at = models.TimeField(default='22:00')

    class Meta:
        ordering = ('day_of_week',)
        constraints = [
            models.UniqueConstraint(
                fields=('restaurant', 'day_of_week'),
                name='unique_restaurant_operating_day',
            ),
        ]

    def __str__(self):
        return f'{self.restaurant} - {self.get_day_of_week_display()}'


class RestaurantReview(models.Model):
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='restaurant_reviews',
    )
    order = models.OneToOneField(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='review',
    )
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.restaurant} - {self.rating}/5'


class ReviewPhoto(models.Model):
    STATUS_PENDING = 'PENDING'
    STATUS_APPROVED = 'APPROVED'
    STATUS_REJECTED = 'REJECTED'
    STATUS_HIDDEN = 'HIDDEN'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_HIDDEN, 'Hidden'),
    ]

    review = models.ForeignKey(
        RestaurantReview,
        on_delete=models.CASCADE,
        related_name='photos',
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='review_photos',
    )
    image = models.ImageField(upload_to='reviews/photos/')
    caption = models.CharField(max_length=240, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    moderation_reason = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_review_photos',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at', '-id')
        indexes = [
            models.Index(fields=('review', 'status')),
            models.Index(fields=('uploaded_by', '-created_at')),
            models.Index(fields=('status', '-created_at')),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.review_id and self.uploaded_by_id:
            if self.review.customer_id != self.uploaded_by_id:
                errors['uploaded_by'] = 'Photo uploader must be the review customer.'
        if self.review_id and self.review.order.status != 'DELIVERED':
            errors['review'] = 'Review photos require a delivered order.'
        if self.image and not getattr(self.image, '_committed', True):
            try:
                validate_review_photo_image(self.image)
            except Exception as exc:
                errors['image'] = exc
        if errors:
            from django.core.exceptions import ValidationError

            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.image and not getattr(self.image, '_committed', True):
            self.image = strip_review_photo_exif(self.image)
        if self.status == self.STATUS_APPROVED:
            if self.image and not str(self.image.name).startswith('reviews/photos/approved/'):
                self.image.name = publish_private_file_to_public(self.image.name)
                update_fields = kwargs.get('update_fields')
                if update_fields is not None and 'image' not in update_fields:
                    kwargs['update_fields'] = set(update_fields) | {'image'}
        else:
            attach_private_upload(self, 'image', 'reviews/photos/private')
        super().save(*args, **kwargs)

    def __str__(self):
        return f'ReviewPhoto #{self.id or "new"} ({self.status})'


class MerchantProfile(models.Model):
    SUBSCRIPTION_NOT_CONFIGURED = 'NOT_CONFIGURED'
    SUBSCRIPTION_TRIAL = 'TRIAL'
    SUBSCRIPTION_MONTHLY = 'MONTHLY'
    SUBSCRIPTION_YEARLY = 'YEARLY'
    SUBSCRIPTION_PLAN_CHOICES = [
        (SUBSCRIPTION_NOT_CONFIGURED, 'Not configured'),
        (SUBSCRIPTION_TRIAL, 'Trial'),
        (SUBSCRIPTION_MONTHLY, 'Monthly'),
        (SUBSCRIPTION_YEARLY, 'Yearly'),
    ]

    market = models.ForeignKey(
        'markets.Market',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='merchant_profiles',
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='merchant_profile',
    )
    business_name = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=15, blank=True)
    subscription_plan = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_PLAN_CHOICES,
        default=SUBSCRIPTION_NOT_CONFIGURED,
    )
    is_verified = models.BooleanField(default=False)
    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS_CHOICES,
        default=VERIFICATION_PENDING,
    )
    verification_rejection_reason = models.TextField(blank=True)
    verification_submitted_at = models.DateTimeField(null=True, blank=True)
    verification_reviewed_at = models.DateTimeField(null=True, blank=True)
    verification_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_merchant_profiles',
    )

    def __str__(self):
        return self.business_name or self.user.get_full_name() or self.user.username

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        Restaurant.objects.filter(owner=self.user).update(
            is_active=self.is_verified
        )


class MerchantNetworkRelationship(models.Model):
    STATUS_REQUESTED = 'REQUESTED'
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_PAUSED = 'PAUSED'
    STATUS_BLOCKED = 'BLOCKED'
    STATUS_CHOICES = [
        (STATUS_REQUESTED, 'Requested'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_PAUSED, 'Paused'),
        (STATUS_BLOCKED, 'Blocked'),
    ]

    from_merchant = models.ForeignKey(
        MerchantProfile,
        on_delete=models.CASCADE,
        related_name='outgoing_network_relationships',
    )
    to_merchant = models.ForeignKey(
        MerchantProfile,
        on_delete=models.CASCADE,
        related_name='incoming_network_relationships',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_REQUESTED,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requested_merchant_network_relationships',
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_merchant_network_relationships',
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)
    distance_km = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ('-requested_at', '-id')
        constraints = [
            models.UniqueConstraint(
                fields=('from_merchant', 'to_merchant'),
                name='unique_directional_merchant_network_relationship',
            ),
            models.CheckConstraint(
                check=~models.Q(from_merchant=models.F('to_merchant')),
                name='merchant_network_no_self_relationship',
            ),
        ]
        indexes = [
            models.Index(fields=('from_merchant', 'status')),
            models.Index(fields=('to_merchant', 'status')),
        ]

    def __str__(self):
        return f'{self.from_merchant} -> {self.to_merchant} ({self.status})'


class MerchantFulfillmentRequest(models.Model):
    STATUS_REQUESTED = 'REQUESTED'
    STATUS_ACCEPTED = 'ACCEPTED'
    STATUS_REJECTED = 'REJECTED'
    STATUS_CANCELLED = 'CANCELLED'
    STATUS_CHOICES = [
        (STATUS_REQUESTED, 'Requested'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]
    INTERNAL_STATUS_PENDING = 'PENDING'
    INTERNAL_STATUS_ACCEPTED = 'ACCEPTED'
    INTERNAL_STATUS_IN_PROGRESS = 'IN_PROGRESS'
    INTERNAL_STATUS_READY_FOR_HANDOFF = 'READY_FOR_HANDOFF'
    INTERNAL_STATUS_UNABLE_TO_FULFILL = 'UNABLE_TO_FULFILL'
    INTERNAL_STATUS_RESOLVED = 'RESOLVED'
    INTERNAL_STATUS_REJECTED = 'REJECTED'
    INTERNAL_STATUS_CANCELLED = 'CANCELLED'
    INTERNAL_STATUS_CHOICES = [
        (INTERNAL_STATUS_PENDING, 'Pending'),
        (INTERNAL_STATUS_ACCEPTED, 'Accepted'),
        (INTERNAL_STATUS_IN_PROGRESS, 'In progress'),
        (INTERNAL_STATUS_READY_FOR_HANDOFF, 'Ready for handoff'),
        (INTERNAL_STATUS_UNABLE_TO_FULFILL, 'Unable to fulfill'),
        (INTERNAL_STATUS_RESOLVED, 'Resolved'),
        (INTERNAL_STATUS_REJECTED, 'Rejected'),
        (INTERNAL_STATUS_CANCELLED, 'Cancelled'),
    ]

    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='merchant_fulfillment_requests',
    )
    requesting_merchant = models.ForeignKey(
        MerchantProfile,
        on_delete=models.CASCADE,
        related_name='outgoing_fulfillment_requests',
    )
    fulfilling_merchant = models.ForeignKey(
        MerchantProfile,
        on_delete=models.CASCADE,
        related_name='incoming_fulfillment_requests',
    )
    relationship = models.ForeignKey(
        MerchantNetworkRelationship,
        on_delete=models.PROTECT,
        related_name='fulfillment_requests',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_REQUESTED,
    )
    internal_status = models.CharField(
        max_length=30,
        choices=INTERNAL_STATUS_CHOICES,
        default=INTERNAL_STATUS_PENDING,
    )
    notes = models.TextField(blank=True)
    operations_note = models.TextField(blank=True)
    blocked_reason = models.TextField(blank=True)
    settlement_preview = models.JSONField(default=dict, blank=True)
    preparation_started_at = models.DateTimeField(null=True, blank=True)
    ready_for_handoff_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requested_merchant_fulfillment_requests',
    )
    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='responded_merchant_fulfillment_requests',
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_merchant_fulfillment_requests',
    )
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cancelled_merchant_fulfillment_requests',
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at', '-id')
        indexes = [
            models.Index(fields=('order', 'status')),
            models.Index(fields=('requesting_merchant', 'status')),
            models.Index(fields=('fulfilling_merchant', 'status')),
            models.Index(fields=('internal_status', 'updated_at')),
        ]

    def __str__(self):
        return (
            f'Order #{self.order_id}: '
            f'{self.requesting_merchant} -> {self.fulfilling_merchant} '
            f'({self.status})'
        )


class MerchantFulfillmentRequestEvent(models.Model):
    EVENT_CREATED = 'CREATED'
    EVENT_STATUS_CHANGED = 'STATUS_CHANGED'
    EVENT_INTERNAL_STATUS_CHANGED = 'INTERNAL_STATUS_CHANGED'
    EVENT_SETTLEMENT_PREVIEWED = 'SETTLEMENT_PREVIEWED'
    EVENT_NOTE_ADDED = 'NOTE_ADDED'
    EVENT_CHOICES = [
        (EVENT_CREATED, 'Created'),
        (EVENT_STATUS_CHANGED, 'Status changed'),
        (EVENT_INTERNAL_STATUS_CHANGED, 'Internal status changed'),
        (EVENT_SETTLEMENT_PREVIEWED, 'Settlement previewed'),
        (EVENT_NOTE_ADDED, 'Note added'),
    ]

    fulfillment_request = models.ForeignKey(
        MerchantFulfillmentRequest,
        on_delete=models.CASCADE,
        related_name='events',
    )
    event_type = models.CharField(max_length=40, choices=EVENT_CHOICES)
    from_status = models.CharField(max_length=40, blank=True)
    to_status = models.CharField(max_length=40, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='merchant_fulfillment_events',
    )
    note = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at', 'id')
        indexes = [
            models.Index(fields=('fulfillment_request', 'created_at')),
            models.Index(fields=('event_type', 'created_at')),
        ]

    def __str__(self):
        return (
            f'Fulfillment request #{self.fulfillment_request_id}: '
            f'{self.event_type}'
        )

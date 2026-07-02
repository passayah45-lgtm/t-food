from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from secrets import randbelow, token_urlsafe
from datetime import timedelta
from fooddelivery.gis_fields import PointField
from fooddelivery.gis_utils import sync_point_from_lat_lng
from orders.models import Order
from verifications.constants import (
    VERIFICATION_PENDING,
    VERIFICATION_STATUS_CHOICES,
)


def merchant_rider_invite_token():
    return token_urlsafe(32)


def merchant_rider_invite_expiry():
    return timezone.now() + timedelta(days=7)


class DeliveryPartner(models.Model):
    market = models.ForeignKey(
        'markets.Market',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='delivery_partners',
    )
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='delivery_partner'
    )
    """
    Stores delivery partner information.
    A delivery partner can handle multiple deliveries over time.
    """
    partner_name = models.CharField(max_length=100)
    partner_phone = models.CharField(max_length=15)
    transport_details = models.CharField(
        max_length=100,
        help_text="Bike / Car / Scooter / Bicycle"
    )
    is_available = models.BooleanField(default=True)
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
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_delivery_partners',
    )
    current_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    current_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    current_point = PointField(srid=4326, null=True, blank=True)
    location_updated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.partner_name

    def save(self, *args, **kwargs):
        kwargs['update_fields'] = sync_point_from_lat_lng(
            self,
            point_field='current_point',
            latitude_field='current_latitude',
            longitude_field='current_longitude',
            update_fields=kwargs.get('update_fields'),
        )
        super().save(*args, **kwargs)


class MerchantRider(models.Model):
    STATUS_INVITED = 'INVITED'
    STATUS_PENDING_APPROVAL = 'PENDING_APPROVAL'
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_INACTIVE = 'INACTIVE'
    STATUS_REMOVED = 'REMOVED'
    STATUS_CHOICES = [
        (STATUS_INVITED, 'Invited'),
        (STATUS_PENDING_APPROVAL, 'Pending approval'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INACTIVE, 'Inactive'),
        (STATUS_REMOVED, 'Removed'),
    ]

    merchant = models.ForeignKey(
        'restaurants.MerchantProfile',
        on_delete=models.CASCADE,
        related_name='merchant_riders',
    )
    partner = models.OneToOneField(
        DeliveryPartner,
        on_delete=models.CASCADE,
        related_name='merchant_rider_link',
    )
    status = models.CharField(
        max_length=24,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING_APPROVAL,
    )
    invited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invited_merchant_riders',
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_merchant_riders',
    )
    home_restaurant = models.ForeignKey(
        'restaurants.Restaurant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='merchant_riders',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('merchant__business_name', 'partner__partner_name', 'id')
        indexes = [
            models.Index(fields=('merchant', 'status')),
            models.Index(fields=('status', 'created_at')),
        ]

    def __str__(self):
        return f'{self.partner.partner_name} for {self.merchant}'


class MerchantRiderInvite(models.Model):
    STATUS_PENDING = 'PENDING'
    STATUS_ACCEPTED = 'ACCEPTED'
    STATUS_EXPIRED = 'EXPIRED'
    STATUS_CANCELLED = 'CANCELLED'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_EXPIRED, 'Expired'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    merchant = models.ForeignKey(
        'restaurants.MerchantProfile',
        on_delete=models.CASCADE,
        related_name='rider_invites',
    )
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    transport_type = models.CharField(max_length=100, blank=True)
    home_restaurant = models.ForeignKey(
        'restaurants.Restaurant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='merchant_rider_invites',
    )
    invite_token = models.CharField(
        max_length=96,
        unique=True,
        default=merchant_rider_invite_token,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    expires_at = models.DateTimeField(default=merchant_rider_invite_expiry)
    linked_partner = models.ForeignKey(
        DeliveryPartner,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='merchant_rider_invites',
    )
    invited_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='merchant_rider_invites_sent',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at', 'id')
        indexes = [
            models.Index(fields=('merchant', 'status')),
            models.Index(fields=('invite_token',)),
            models.Index(fields=('expires_at',)),
        ]

    def __str__(self):
        return f'{self.name} invited by {self.merchant}'

    def is_expired(self, now=None):
        return self.status == self.STATUS_PENDING and self.expires_at <= (now or timezone.now())


class Delivery(models.Model):
    """
    Each order is tied to exactly one delivery.
    Delivery is handled by one delivery partner.
    """

    DELIVERY_STATUS_CHOICES = [
        ('ASSIGNED', 'Assigned'),
        ('PICKED_UP', 'Picked Up'),
        ('ON_THE_WAY', 'On the Way'),
        ('DELIVERED', 'Delivered'),
    ]
    PAYOUT_STATUS_CHOICES = [
        ('PENDING', 'Pending delivery'),
        ('AVAILABLE', 'Available for payout'),
        ('PAID', 'Paid'),
    ]

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='delivery'
    )
    market = models.ForeignKey(
        'markets.Market',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='deliveries',
    )

    delivery_partner = models.ForeignKey(
        DeliveryPartner,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deliveries'
    )

    status = models.CharField(
        max_length=20,
        choices=DELIVERY_STATUS_CHOICES,
        default='ASSIGNED'
    )

    #  longitude and latitude
    current_latitude = models.FloatField(null=True, blank=True)
    current_longitude = models.FloatField(null=True, blank=True)
    current_point = PointField(srid=4326, null=True, blank=True)

    #  will be set automatically
    assigned_at = models.DateTimeField(null=True, blank=True)

    # optional: when delivery record was created
    delivery_date = models.DateTimeField(auto_now_add=True)
    partner_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payout_status = models.CharField(
        max_length=20,
        choices=PAYOUT_STATUS_CHOICES,
        default='PENDING',
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    confirmation_code = models.CharField(max_length=6, blank=True)
    confirmation_verified_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        """
        Automatically set assigned_at
        when a delivery partner is assigned
        """
        if self.delivery_partner and not self.assigned_at:
            self.assigned_at = timezone.now()
        if (
            self.delivery_partner
            and self.status != 'DELIVERED'
            and not self.confirmation_code
        ):
            self.confirmation_code = f'{randbelow(1000000):06d}'

        kwargs['update_fields'] = sync_point_from_lat_lng(
            self,
            point_field='current_point',
            latitude_field='current_latitude',
            longitude_field='current_longitude',
            update_fields=kwargs.get('update_fields'),
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Delivery for Order #{self.order.id}"

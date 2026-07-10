from django.db import models
from django.contrib.auth.models import User
from restaurants.models import FoodItem
from django.core.validators import MinValueValidator
from fooddelivery.gis_fields import PointField
from fooddelivery.gis_utils import sync_point_from_lat_lng


class Offer(models.Model):
    market = models.ForeignKey(
        'markets.Market',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='offers',
    )
    code = models.CharField(max_length=30, unique=True)
    discount_percent = models.PositiveSmallIntegerField()
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    max_uses_total = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1)]
    )
    max_uses_per_customer = models.PositiveIntegerField(
        null=True, blank=True, default=1, validators=[MinValueValidator(1)]
    )
    first_order_only = models.BooleanField(default=False)

    def __str__(self):
        return self.code


class Order(models.Model):
    """
    Stores a single order placed by a customer.
    One order can have multiple food items.

    STATUS LIFECYCLE (single source of truth - used by orders, delivery & admin):
        PLACED -> CONFIRMED -> PREPARING -> ON_THE_WAY -> DELIVERED
                                                       -> CANCELLED
    """

    STATUS_CHOICES = [
        ('PLACED',      'Placed'),           # Order created, awaiting payment
        ('CONFIRMED',   'Confirmed'),        # Payment received, delivery assigned
        ('PREPARING',   'Preparing'),        # Merchant accepted and is preparing
        ('READY_FOR_PICKUP', 'Ready for Pickup'),
        ('ON_THE_WAY',  'On the Way'),       # Partner en route
        ('DELIVERED',   'Delivered'),        # Successfully delivered
        ('CANCELLED',   'Cancelled'),        # Cancelled
        ('EXPIRED',     'Payment Expired'),
    ]
    MERCHANT_PAYOUT_STATUS_CHOICES = [
        ('PENDING', 'Pending delivery'),
        ('AVAILABLE', 'Available for payout'),
        ('PAID', 'Paid'),
        ('CANCELLED', 'Cancelled'),
    ]

    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='orders'
    )
    market = models.ForeignKey(
        'markets.Market',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='orders',
    )
    pickup_branch = models.ForeignKey(
        'restaurants.Restaurant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='branch_orders',
    )
    client_order_id = models.UUIDField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PLACED'
    )

    # Customer's delivery location
    delivery_address = models.TextField(blank=True)
    delivery_instructions = models.CharField(max_length=300, blank=True)
    contact_phone = models.CharField(max_length=15, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    delivery_point = PointField(srid=4326, null=True, blank=True)

    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    subtotal_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    merchant_payout = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    merchant_payout_status = models.CharField(
        max_length=20,
        choices=MERCHANT_PAYOUT_STATUS_CHOICES,
        default='PENDING',
    )
    merchant_paid_at = models.DateTimeField(null=True, blank=True)
    payment_expires_at = models.DateTimeField(null=True, blank=True)
    delivery_distance_km = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    estimated_delivery_at = models.DateTimeField(null=True, blank=True)
    offer = models.ForeignKey(
        Offer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
    )
    merchant_sequence_date = models.DateField(null=True, blank=True, db_index=True)
    merchant_daily_sequence = models.PositiveIntegerField(null=True, blank=True)
    merchant_order_code = models.CharField(max_length=80, blank=True, db_index=True)
    loyalty_points_awarded = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.id} - {self.customer.username}"

    def save(self, *args, **kwargs):
        kwargs['update_fields'] = sync_point_from_lat_lng(
            self,
            point_field='delivery_point',
            latitude_field='latitude',
            longitude_field='longitude',
            update_fields=kwargs.get('update_fields'),
        )
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['pickup_branch', 'merchant_sequence_date']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['customer', 'client_order_id'],
                condition=models.Q(client_order_id__isnull=False),
                name='unique_customer_client_order_id',
            ),
            models.UniqueConstraint(
                fields=['pickup_branch', 'merchant_sequence_date', 'merchant_daily_sequence'],
                condition=models.Q(merchant_daily_sequence__isnull=False),
                name='unique_branch_daily_order_sequence',
            ),
        ]


class OrderItem(models.Model):
    """
    Individual food item line inside an order.
    Price is frozen at the time of ordering.
    """

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    food = models.ForeignKey(FoodItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    # Frozen price - never reflects future price changes on FoodItem
    price = models.DecimalField(max_digits=8, decimal_places=2)
    base_price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    selected_options = models.JSONField(default=list, blank=True)

    def get_subtotal(self):
        return self.price * self.quantity

    def __str__(self):
        return f"{self.food.food_name} x {self.quantity}"


class OrderStatusEvent(models.Model):
    SOURCE_CHOICES = [
        ('CHECKOUT', 'Checkout'),
        ('PAYMENT', 'Payment'),
        ('MERCHANT', 'Merchant'),
        ('DELIVERY', 'Delivery'),
        ('CANCELLATION', 'Cancellation'),
        ('SYSTEM', 'System'),
    ]

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='status_events',
    )
    status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    description = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at', 'id')
        indexes = [models.Index(fields=('order', 'created_at'))]

    def __str__(self):
        return f'Order #{self.order_id}: {self.status}'


class SupportTicket(models.Model):
    CATEGORY_CHOICES = [
        ('MISSING_ITEMS', 'Missing items'),
        ('QUALITY', 'Food quality'),
        ('DELIVERY', 'Delivery issue'),
        ('PAYMENT', 'Payment issue'),
        ('OTHER', 'Other'),
    ]
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('IN_REVIEW', 'In review'),
        ('RESOLVED', 'Resolved'),
        ('REJECTED', 'Rejected'),
    ]
    REFUND_CHOICES = [
        ('NONE', 'Not requested'),
        ('REQUESTED', 'Requested'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='support_tickets',
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='support_tickets',
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    description = models.TextField(max_length=2000)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    refund_status = models.CharField(max_length=20, choices=REFUND_CHOICES, default='NONE')
    refunded_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    resolution = models.TextField(max_length=2000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [models.Index(fields=('status', '-created_at'))]

    def __str__(self):
        return f'Ticket #{self.id} for order #{self.order_id}'

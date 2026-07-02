from django.db import models
from django.db.models import Q

from markets.models import country_code_validator, currency_code_validator
from orders.models import Order

class Payment(models.Model):

    PAYMENT_METHODS = [
        ('COD', 'Cash on Delivery'),
        ('UPI', 'UPI'),
        ('CARD', 'Credit / Debit Card'),
        ('WALLET', 'Wallet'),
    ]

    PAYMENT_STATUS = [
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('REFUNDED', 'Refunded'),
        ('CANCELLED', 'Cancelled'),
    ]

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='payment'
    )
    market = models.ForeignKey(
        'markets.Market',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='payments',
    )

    method = models.CharField(
        max_length=10,
        choices=PAYMENT_METHODS
    )

    status = models.CharField(
        max_length=10,
        choices=PAYMENT_STATUS,
        default='PENDING'
    )

    transaction_id = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )
    provider = models.CharField(max_length=30, blank=True)
    provider_order_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment for Order #{self.order.id}"


class PaymentWebhookEvent(models.Model):
    market = models.ForeignKey(
        'markets.Market',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='payment_webhook_events',
    )
    event_id = models.CharField(max_length=100, unique=True)
    event_type = models.CharField(max_length=100)
    payload_hash = models.CharField(max_length=64)
    processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.event_type} ({self.event_id})'


class PaymentProviderConfig(models.Model):
    METHOD_COD = 'COD'
    METHOD_CARD = 'CARD'
    METHOD_MOBILE_MONEY = 'MOBILE_MONEY'
    METHOD_UPI = 'UPI'
    METHOD_WALLET = 'WALLET'
    METHOD_BANK_TRANSFER = 'BANK_TRANSFER'
    METHOD_QR_PAYMENT = 'QR_PAYMENT'
    PAYMENT_METHOD_CHOICES = [
        (METHOD_COD, 'Cash on Delivery'),
        (METHOD_CARD, 'Card'),
        (METHOD_MOBILE_MONEY, 'Mobile Money'),
        (METHOD_UPI, 'UPI'),
        (METHOD_WALLET, 'Wallet'),
        (METHOD_BANK_TRANSFER, 'Bank Transfer'),
        (METHOD_QR_PAYMENT, 'QR Payment'),
    ]

    market = models.ForeignKey(
        'markets.Market',
        on_delete=models.PROTECT,
        related_name='payment_provider_configs',
    )
    country_code = models.CharField(
        max_length=2,
        validators=[country_code_validator],
    )
    currency = models.CharField(
        max_length=3,
        validators=[currency_code_validator],
    )
    provider_code = models.CharField(max_length=40)
    payment_method = models.CharField(
        max_length=30,
        choices=PAYMENT_METHOD_CHOICES,
    )
    is_active = models.BooleanField(default=False)
    is_preferred = models.BooleanField(default=False)
    priority = models.PositiveSmallIntegerField(default=100)
    supports_refund = models.BooleanField(default=False)
    supports_webhook = models.BooleanField(default=False)
    supports_partial_refund = models.BooleanField(default=False)
    credentials_present = models.BooleanField(default=False)
    config_metadata = models.JSONField(default=dict, blank=True)
    updated_by = models.ForeignKey(
        'auth.User',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='updated_payment_provider_configs',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('country_code', 'payment_method', 'priority', 'provider_code')
        indexes = [
            models.Index(fields=('country_code', 'currency', 'payment_method')),
            models.Index(fields=('market', 'payment_method')),
            models.Index(fields=('provider_code', 'is_active')),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=('market', 'provider_code', 'payment_method'),
                name='unique_provider_config_per_market_method',
            ),
            models.UniqueConstraint(
                fields=('market', 'payment_method'),
                condition=Q(is_preferred=True),
                name='unique_preferred_provider_per_market_method',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.country_code:
            self.country_code = self.country_code.upper()
        if self.currency:
            self.currency = self.currency.upper()
        if self.provider_code:
            self.provider_code = self.provider_code.lower()
        if self.payment_method:
            self.payment_method = self.payment_method.upper()
        if self.market_id:
            self.country_code = self.country_code or self.market.country_code
            if not self.currency and self.market.default_currency_id:
                self.currency = self.market.default_currency.code
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.provider_code} {self.payment_method} in {self.country_code}'


class RefundAudit(models.Model):
    STATUS_REQUESTED = 'REQUESTED'
    STATUS_APPROVED = 'APPROVED'
    STATUS_PROCESSING = 'PROCESSING'
    STATUS_SUCCEEDED = 'SUCCEEDED'
    STATUS_FAILED = 'FAILED'
    STATUS_CANCELLED = 'CANCELLED'
    STATUS_CHOICES = [
        (STATUS_REQUESTED, 'Requested'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_SUCCEEDED, 'Succeeded'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    order = models.ForeignKey(
        Order,
        on_delete=models.PROTECT,
        related_name='refund_audits',
    )
    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        related_name='refund_audits',
    )
    support_ticket = models.ForeignKey(
        'orders.SupportTicket',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='refund_audits',
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3)
    reason = models.TextField(blank=True)
    initiated_by = models.ForeignKey(
        'auth.User',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='initiated_refund_audits',
    )
    provider_code = models.CharField(max_length=40)
    provider_refund_id = models.CharField(max_length=120, null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_REQUESTED,
    )
    ledger_transaction = models.ForeignKey(
        'ledger.LedgerTransaction',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='refund_audits',
    )
    idempotency_key = models.CharField(max_length=160, unique=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at', '-id')
        indexes = [
            models.Index(fields=('order', 'status')),
            models.Index(fields=('payment', 'status')),
            models.Index(fields=('provider_code', 'status')),
        ]

    def save(self, *args, **kwargs):
        if self.currency:
            self.currency = self.currency.upper()
        if self.provider_code:
            self.provider_code = self.provider_code.upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Refund {self.currency} {self.amount} for order #{self.order_id}'


class MerchantPayoutAudit(models.Model):
    STATUS_AVAILABLE = 'AVAILABLE'
    STATUS_PAID = 'PAID'
    STATUS_FAILED = 'FAILED'
    STATUS_REVERSED = 'REVERSED'
    STATUS_CHOICES = [
        (STATUS_AVAILABLE, 'Available'),
        (STATUS_PAID, 'Paid'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_REVERSED, 'Reversed'),
    ]

    order = models.ForeignKey(
        Order,
        on_delete=models.PROTECT,
        related_name='merchant_payout_audits',
    )
    merchant = models.ForeignKey(
        'restaurants.MerchantProfile',
        on_delete=models.PROTECT,
        related_name='payout_audits',
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3)
    market = models.ForeignKey(
        'markets.Market',
        on_delete=models.PROTECT,
        related_name='merchant_payout_audits',
    )
    country_code = models.CharField(max_length=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    marked_by = models.ForeignKey(
        'auth.User',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='marked_merchant_payout_audits',
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    ledger_transaction = models.ForeignKey(
        'ledger.LedgerTransaction',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='merchant_payout_audits',
    )
    idempotency_key = models.CharField(max_length=160, unique=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at', '-id')
        indexes = [
            models.Index(fields=('merchant', 'status')),
            models.Index(fields=('order', 'status')),
            models.Index(fields=('market', 'status')),
        ]

    def save(self, *args, **kwargs):
        if self.currency:
            self.currency = self.currency.upper()
        if self.country_code:
            self.country_code = self.country_code.upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Merchant payout {self.currency} {self.amount} for order #{self.order_id}'


class PartnerPayoutAudit(models.Model):
    STATUS_AVAILABLE = 'AVAILABLE'
    STATUS_PAID = 'PAID'
    STATUS_FAILED = 'FAILED'
    STATUS_REVERSED = 'REVERSED'
    STATUS_CHOICES = [
        (STATUS_AVAILABLE, 'Available'),
        (STATUS_PAID, 'Paid'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_REVERSED, 'Reversed'),
    ]

    delivery = models.ForeignKey(
        'delivery.Delivery',
        on_delete=models.PROTECT,
        related_name='partner_payout_audits',
    )
    partner = models.ForeignKey(
        'delivery.DeliveryPartner',
        on_delete=models.PROTECT,
        related_name='payout_audits',
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3)
    market = models.ForeignKey(
        'markets.Market',
        on_delete=models.PROTECT,
        related_name='partner_payout_audits',
    )
    country_code = models.CharField(max_length=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    marked_by = models.ForeignKey(
        'auth.User',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='marked_partner_payout_audits',
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    ledger_transaction = models.ForeignKey(
        'ledger.LedgerTransaction',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='partner_payout_audits',
    )
    idempotency_key = models.CharField(max_length=160, unique=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at', '-id')
        indexes = [
            models.Index(fields=('partner', 'status')),
            models.Index(fields=('delivery', 'status')),
            models.Index(fields=('market', 'status')),
        ]

    def save(self, *args, **kwargs):
        if self.currency:
            self.currency = self.currency.upper()
        if self.country_code:
            self.country_code = self.country_code.upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Partner payout {self.currency} {self.amount} for delivery #{self.delivery_id}'

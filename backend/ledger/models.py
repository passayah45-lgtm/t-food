from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction

from markets.models import country_code_validator, currency_code_validator


class ImmutableLedgerError(ValidationError):
    pass


def _money(value):
    try:
        return Decimal(str(value)).quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError('Ledger amounts must be valid decimal values.') from exc


class ImmutableQuerySet(models.QuerySet):
    def delete(self):
        raise ImmutableLedgerError('Ledger records are immutable and cannot be deleted.')

    def update(self, **kwargs):
        raise ImmutableLedgerError('Ledger records are immutable and cannot be updated.')


class LedgerAccount(models.Model):
    ACCOUNT_CUSTOMER = 'CUSTOMER'
    ACCOUNT_MERCHANT = 'MERCHANT'
    ACCOUNT_PARTNER = 'PARTNER'
    ACCOUNT_PLATFORM = 'PLATFORM'
    ACCOUNT_PAYMENT_PROVIDER = 'PAYMENT_PROVIDER'
    ACCOUNT_CASH_CLEARING = 'CASH_CLEARING'
    ACCOUNT_REFUND_CLEARING = 'REFUND_CLEARING'
    ACCOUNT_FULFILLMENT_CLEARING = 'FULFILLMENT_CLEARING'
    ACCOUNT_CHOICES = [
        (ACCOUNT_CUSTOMER, 'Customer'),
        (ACCOUNT_MERCHANT, 'Merchant'),
        (ACCOUNT_PARTNER, 'Delivery partner'),
        (ACCOUNT_PLATFORM, 'Platform'),
        (ACCOUNT_PAYMENT_PROVIDER, 'Payment provider'),
        (ACCOUNT_CASH_CLEARING, 'Cash clearing'),
        (ACCOUNT_REFUND_CLEARING, 'Refund clearing'),
        (ACCOUNT_FULFILLMENT_CLEARING, 'Fulfillment clearing'),
    ]

    market = models.ForeignKey(
        'markets.Market',
        on_delete=models.PROTECT,
        related_name='ledger_accounts',
    )
    country_code = models.CharField(
        max_length=2,
        validators=[country_code_validator],
    )
    currency = models.CharField(
        max_length=3,
        validators=[currency_code_validator],
    )
    account_type = models.CharField(max_length=30, choices=ACCOUNT_CHOICES)
    name = models.CharField(max_length=120)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='ledger_accounts',
    )
    merchant = models.ForeignKey(
        'restaurants.MerchantProfile',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='ledger_accounts',
    )
    partner = models.ForeignKey(
        'delivery.DeliveryPartner',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='ledger_accounts',
    )
    provider_code = models.CharField(max_length=40, blank=True)
    external_reference = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('account_type', 'name', 'id')
        indexes = [
            models.Index(fields=('market', 'currency', 'account_type')),
            models.Index(fields=('provider_code', 'external_reference')),
        ]

    def save(self, *args, **kwargs):
        if self.country_code:
            self.country_code = self.country_code.upper()
        if self.currency:
            self.currency = self.currency.upper()
        if self.provider_code:
            self.provider_code = self.provider_code.upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.name} ({self.account_type}, {self.currency})'


class LedgerTransactionManager(models.Manager):
    def get_queryset(self):
        return ImmutableQuerySet(self.model, using=self._db)

    @transaction.atomic
    def create_balanced(self, *, entries, **transaction_fields):
        if not entries:
            raise ValidationError('Ledger transactions require at least two entries.')

        market = transaction_fields.get('market')
        if not market:
            raise ValidationError({'market': ['Market is required.']})

        currency = str(
            transaction_fields.get('currency') or market.default_currency.code
        ).upper()
        country_code = str(
            transaction_fields.get('country_code') or market.country_code
        ).upper()
        provider_code = str(transaction_fields.get('provider_code') or '').upper()
        if not provider_code:
            raise ValidationError({'provider_code': ['Provider code is required.']})

        debits = Decimal('0.00')
        credits = Decimal('0.00')
        normalized_entries = []
        for entry in entries:
            entry_currency = str(entry.get('currency') or currency).upper()
            if entry_currency != currency:
                raise ValidationError(
                    'Different currencies cannot exist inside the same ledger transaction.'
                )
            account = entry['account']
            if account.currency != currency:
                raise ValidationError('Ledger entry account currency must match transaction currency.')
            amount = _money(entry['amount'])
            if amount <= 0:
                raise ValidationError('Ledger entry amount must be greater than zero.')
            direction = entry['direction']
            if direction == LedgerEntry.DIRECTION_DEBIT:
                debits += amount
            elif direction == LedgerEntry.DIRECTION_CREDIT:
                credits += amount
            else:
                raise ValidationError('Ledger entry direction must be DEBIT or CREDIT.')
            normalized_entries.append({
                **entry,
                'amount': amount,
                'currency': currency,
            })

        if debits != credits:
            raise ValidationError('Ledger transaction must balance: total debits must equal total credits.')

        ledger_transaction = self.model(
            **{
                **transaction_fields,
                'country_code': country_code,
                'currency': currency,
                'provider_code': provider_code,
                'amount': debits,
                'debit_total': debits,
                'credit_total': credits,
            }
        )
        ledger_transaction._allow_ledger_create = True
        ledger_transaction.save(force_insert=True)
        for entry in normalized_entries:
            ledger_entry = LedgerEntry(
                transaction=ledger_transaction,
                account=entry['account'],
                direction=entry['direction'],
                amount=entry['amount'],
                currency=entry['currency'],
                memo=entry.get('memo', ''),
                metadata=entry.get('metadata', {}),
            )
            ledger_entry._allow_ledger_create = True
            ledger_entry.save(force_insert=True)
        return ledger_transaction


class LedgerTransaction(models.Model):
    TYPE_ORDER_GROSS = 'ORDER_GROSS'
    TYPE_PLATFORM_FEE = 'PLATFORM_FEE'
    TYPE_MERCHANT_PAYOUT = 'MERCHANT_PAYOUT'
    TYPE_PARTNER_DELIVERY_FEE = 'PARTNER_DELIVERY_FEE'
    TYPE_REFUND = 'REFUND'
    TYPE_PAYOUT_SETTLEMENT = 'PAYOUT_SETTLEMENT'
    TYPE_FULFILLMENT_PREVIEW = 'FULFILLMENT_PREVIEW'
    TYPE_FULFILLMENT_SETTLEMENT = 'FULFILLMENT_SETTLEMENT'
    TYPE_ADJUSTMENT = 'ADJUSTMENT'
    TYPE_REVERSAL = 'REVERSAL'
    TYPE_CHOICES = [
        (TYPE_ORDER_GROSS, 'Order gross amount'),
        (TYPE_PLATFORM_FEE, 'Platform fee'),
        (TYPE_MERCHANT_PAYOUT, 'Merchant payout'),
        (TYPE_PARTNER_DELIVERY_FEE, 'Partner delivery fee'),
        (TYPE_REFUND, 'Refund'),
        (TYPE_PAYOUT_SETTLEMENT, 'Payout settlement'),
        (TYPE_FULFILLMENT_PREVIEW, 'Cross-merchant settlement preview'),
        (TYPE_FULFILLMENT_SETTLEMENT, 'Cross-merchant settlement'),
        (TYPE_ADJUSTMENT, 'Adjustment'),
        (TYPE_REVERSAL, 'Reversal'),
    ]

    market = models.ForeignKey(
        'markets.Market',
        on_delete=models.PROTECT,
        related_name='ledger_transactions',
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
    transaction_type = models.CharField(max_length=40, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    debit_total = models.DecimalField(max_digits=14, decimal_places=2)
    credit_total = models.DecimalField(max_digits=14, decimal_places=2)
    idempotency_key = models.CharField(max_length=160, unique=True)
    source_type = models.CharField(max_length=80, blank=True)
    source_id = models.CharField(max_length=80, blank=True)
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='ledger_transactions',
    )
    payment = models.ForeignKey(
        'payments.Payment',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='ledger_transactions',
    )
    delivery = models.ForeignKey(
        'delivery.Delivery',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='ledger_transactions',
    )
    fulfillment_request = models.ForeignKey(
        'restaurants.MerchantFulfillmentRequest',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='ledger_transactions',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='created_ledger_transactions',
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = LedgerTransactionManager()

    class Meta:
        ordering = ('-created_at', '-id')
        indexes = [
            models.Index(fields=('market', 'currency', 'transaction_type')),
            models.Index(fields=('provider_code', 'transaction_type')),
            models.Index(fields=('source_type', 'source_id')),
            models.Index(fields=('order', 'transaction_type')),
        ]

    def clean(self):
        if self.country_code:
            self.country_code = self.country_code.upper()
        if self.currency:
            self.currency = self.currency.upper()
        if self.provider_code:
            self.provider_code = self.provider_code.upper()
        if self.debit_total != self.credit_total:
            raise ValidationError('Ledger transaction must balance: total debits must equal total credits.')
        if self.amount != self.debit_total:
            raise ValidationError('Ledger transaction amount must match balanced totals.')
        if not self.provider_code:
            raise ValidationError({'provider_code': ['Provider code is required.']})

    def save(self, *args, **kwargs):
        if self.pk:
            raise ImmutableLedgerError('LedgerTransaction records are immutable after creation.')
        if not getattr(self, '_allow_ledger_create', False):
            raise ImmutableLedgerError(
                'Use LedgerTransaction.objects.create_balanced() to create committed ledger transactions.'
            )
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableLedgerError('LedgerTransaction records are immutable and cannot be deleted.')

    def __str__(self):
        return f'{self.transaction_type} {self.currency} {self.amount}'


class LedgerEntryManager(models.Manager):
    def get_queryset(self):
        return ImmutableQuerySet(self.model, using=self._db)


class LedgerEntry(models.Model):
    DIRECTION_DEBIT = 'DEBIT'
    DIRECTION_CREDIT = 'CREDIT'
    DIRECTION_CHOICES = [
        (DIRECTION_DEBIT, 'Debit'),
        (DIRECTION_CREDIT, 'Credit'),
    ]

    transaction = models.ForeignKey(
        LedgerTransaction,
        on_delete=models.PROTECT,
        related_name='entries',
    )
    account = models.ForeignKey(
        LedgerAccount,
        on_delete=models.PROTECT,
        related_name='ledger_entries',
    )
    direction = models.CharField(max_length=6, choices=DIRECTION_CHOICES)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(
        max_length=3,
        validators=[currency_code_validator],
    )
    memo = models.CharField(max_length=240, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = LedgerEntryManager()

    class Meta:
        ordering = ('transaction_id', 'id')
        indexes = [
            models.Index(fields=('transaction', 'direction')),
            models.Index(fields=('account', 'currency')),
        ]

    def clean(self):
        if self.currency:
            self.currency = self.currency.upper()
        if self.currency != self.transaction.currency:
            raise ValidationError('LedgerEntry currency must match its LedgerTransaction currency.')
        if self.account.currency != self.currency:
            raise ValidationError('LedgerEntry account currency must match entry currency.')
        if self.amount <= 0:
            raise ValidationError('LedgerEntry amount must be greater than zero.')

    def save(self, *args, **kwargs):
        if self.pk:
            raise ImmutableLedgerError('LedgerEntry records are immutable after creation.')
        if not getattr(self, '_allow_ledger_create', False):
            raise ImmutableLedgerError(
                'LedgerEntry records can only be created by a balanced LedgerTransaction.'
            )
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableLedgerError('LedgerEntry records are immutable and cannot be deleted.')

    def __str__(self):
        return f'{self.direction} {self.currency} {self.amount}'

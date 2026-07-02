from django.contrib import admin
from .models import (
    MerchantPayoutAudit,
    PartnerPayoutAudit,
    Payment,
    PaymentProviderConfig,
    PaymentWebhookEvent,
    RefundAudit,
)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('order', 'method', 'status', 'transaction_id', 'created_at')
    list_filter = ('method', 'status', 'created_at')
    search_fields = ('order__id', 'transaction_id', 'order__customer__username')
    readonly_fields = ('created_at',)


@admin.register(PaymentWebhookEvent)
class PaymentWebhookEventAdmin(admin.ModelAdmin):
    list_display = ('event_id', 'event_type', 'processed', 'created_at', 'processed_at')
    list_filter = ('event_type', 'processed')
    search_fields = ('event_id', 'payload_hash')
    readonly_fields = (
        'event_id', 'event_type', 'payload_hash', 'processed',
        'created_at', 'processed_at',
    )


@admin.register(PaymentProviderConfig)
class PaymentProviderConfigAdmin(admin.ModelAdmin):
    list_display = (
        'provider_code', 'market', 'country_code', 'currency',
        'payment_method', 'is_active', 'is_preferred', 'priority',
        'credentials_present', 'updated_at',
    )
    list_filter = (
        'is_active', 'is_preferred', 'credentials_present',
        'provider_code', 'country_code', 'currency', 'payment_method',
    )
    search_fields = ('provider_code', 'market__name', 'country_code', 'currency')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(RefundAudit)
class RefundAuditAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'order', 'payment', 'amount', 'currency', 'status',
        'provider_code', 'created_at',
    )
    list_filter = ('status', 'provider_code', 'currency', 'created_at')
    search_fields = (
        'order__id', 'payment__id', 'support_ticket__id',
        'idempotency_key', 'provider_refund_id',
    )
    readonly_fields = (
        'order', 'payment', 'support_ticket', 'amount', 'currency', 'reason',
        'initiated_by', 'provider_code', 'provider_refund_id', 'status',
        'ledger_transaction', 'idempotency_key', 'metadata',
        'created_at', 'updated_at',
    )


@admin.register(MerchantPayoutAudit)
class MerchantPayoutAuditAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'order', 'merchant', 'amount', 'currency', 'status',
        'paid_at', 'created_at',
    )
    list_filter = ('status', 'currency', 'country_code', 'created_at')
    search_fields = ('order__id', 'merchant__business_name', 'idempotency_key')
    readonly_fields = (
        'order', 'merchant', 'amount', 'currency', 'market', 'country_code',
        'status', 'marked_by', 'paid_at', 'ledger_transaction',
        'idempotency_key', 'metadata', 'created_at', 'updated_at',
    )


@admin.register(PartnerPayoutAudit)
class PartnerPayoutAuditAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'delivery', 'partner', 'amount', 'currency', 'status',
        'paid_at', 'created_at',
    )
    list_filter = ('status', 'currency', 'country_code', 'created_at')
    search_fields = ('delivery__id', 'partner__partner_name', 'idempotency_key')
    readonly_fields = (
        'delivery', 'partner', 'amount', 'currency', 'market', 'country_code',
        'status', 'marked_by', 'paid_at', 'ledger_transaction',
        'idempotency_key', 'metadata', 'created_at', 'updated_at',
    )

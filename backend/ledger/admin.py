from django.contrib import admin

from .models import LedgerAccount, LedgerEntry, LedgerTransaction


@admin.register(LedgerAccount)
class LedgerAccountAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'account_type', 'market', 'country_code', 'currency',
        'provider_code', 'is_active',
    )
    list_filter = ('account_type', 'market', 'currency', 'provider_code', 'is_active')
    search_fields = (
        'name', 'external_reference', 'user__username',
        'merchant__business_name', 'partner__partner_name',
    )
    readonly_fields = ('created_at', 'updated_at')


class LedgerEntryInline(admin.TabularInline):
    model = LedgerEntry
    extra = 0
    can_delete = False
    readonly_fields = (
        'account', 'direction', 'amount', 'currency', 'memo',
        'metadata', 'created_at',
    )

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(LedgerTransaction)
class LedgerTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'transaction_type', 'market', 'country_code', 'currency',
        'amount', 'provider_code', 'idempotency_key', 'created_at',
    )
    list_filter = ('transaction_type', 'market', 'currency', 'provider_code')
    search_fields = ('idempotency_key', 'source_type', 'source_id', 'order__id')
    readonly_fields = (
        'market', 'country_code', 'currency', 'provider_code',
        'transaction_type', 'amount', 'debit_total', 'credit_total',
        'idempotency_key', 'source_type', 'source_id', 'order', 'payment',
        'delivery', 'fulfillment_request', 'created_by', 'metadata',
        'created_at',
    )
    inlines = [LedgerEntryInline]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'transaction', 'account', 'direction', 'amount',
        'currency', 'created_at',
    )
    list_filter = ('direction', 'currency', 'account__account_type')
    search_fields = ('transaction__idempotency_key', 'account__name', 'memo')
    readonly_fields = (
        'transaction', 'account', 'direction', 'amount', 'currency',
        'memo', 'metadata', 'created_at',
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

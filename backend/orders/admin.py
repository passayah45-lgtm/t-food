from django.contrib import admin
from .models import Offer, Order, OrderItem, OrderStatusEvent, SupportTicket


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('food', 'quantity', 'price')


class OrderStatusEventInline(admin.TabularInline):
    model = OrderStatusEvent
    extra = 0
    can_delete = False
    readonly_fields = ('status', 'source', 'description', 'created_at')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'customer', 'status', 'subtotal_amount', 'discount_amount',
        'delivery_fee', 'platform_fee', 'merchant_payout',
        'merchant_payout_status', 'total_amount', 'created_at',
    )
    list_filter = ('status', 'merchant_payout_status', 'created_at', 'offer')
    search_fields = (
        'id', 'customer__username', 'customer__email',
        'delivery_address', 'contact_phone',
    )
    readonly_fields = (
        'subtotal_amount', 'discount_amount', 'delivery_fee',
        'platform_fee', 'merchant_payout', 'total_amount',
        'created_at', 'updated_at', 'loyalty_points_awarded',
    )
    inlines = (OrderItemInline, OrderStatusEventInline)
    date_hierarchy = 'created_at'


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'food', 'quantity', 'price')
    search_fields = ('order__id', 'food__food_name')


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = (
        'code', 'discount_percent', 'min_order_amount',
        'is_active', 'valid_until', 'max_uses_total',
        'max_uses_per_customer', 'first_order_only',
    )
    list_filter = ('is_active', 'first_order_only')
    search_fields = ('code',)


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'customer', 'category', 'status', 'refund_status', 'created_at')
    list_filter = ('status', 'refund_status', 'category')
    search_fields = ('order__id', 'customer__username', 'description')
    readonly_fields = ('customer', 'order', 'category', 'description', 'created_at', 'updated_at')

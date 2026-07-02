from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Delivery, DeliveryPartner, MerchantRider, MerchantRiderInvite


@admin.register(DeliveryPartner)
class DeliveryPartnerAdmin(admin.ModelAdmin):
    list_display = ('partner_name', 'partner_phone', 'transport_details', 'is_available')
    search_fields = ('partner_name', 'partner_phone')
    list_filter = ('is_available',)


@admin.register(MerchantRider)
class MerchantRiderAdmin(admin.ModelAdmin):
    list_display = (
        'merchant', 'partner', 'status', 'home_restaurant',
        'approved_by', 'approved_at',
    )
    list_filter = ('status', 'created_at', 'approved_at')
    search_fields = (
        'merchant__business_name',
        'merchant__user__username',
        'partner__partner_name',
        'partner__partner_phone',
    )
    autocomplete_fields = (
        'merchant', 'partner', 'invited_by', 'approved_by', 'home_restaurant',
    )
    readonly_fields = ('created_at', 'updated_at')


@admin.register(MerchantRiderInvite)
class MerchantRiderInviteAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'merchant', 'status', 'phone', 'email',
        'transport_type', 'expires_at', 'linked_partner',
    )
    list_filter = ('status', 'expires_at', 'created_at')
    search_fields = (
        'name', 'phone', 'email', 'merchant__business_name',
        'merchant__user__username',
    )
    autocomplete_fields = ('merchant', 'linked_partner', 'invited_by')
    readonly_fields = ('invite_token', 'created_at', 'updated_at')


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ('order', 'delivery_partner', 'status', 'partner_fee', 'payout_status', 'assigned_at')
    list_filter = ('status', 'payout_status')
    search_fields = ('order__id', 'delivery_partner__partner_name')
    readonly_fields = ('confirmation_code', 'confirmation_verified_at')

    def save_model(self, request, obj, form, change):
        """
        - Auto-set assigned_at on first assignment
        - Lock / free delivery partner availability
        - Sync Order.status using the unified STATUS_CHOICES constants
        """

        if change and obj.status == 'DELIVERED':
            previous_status = Delivery.objects.filter(pk=obj.pk).values_list(
                'status', flat=True
            ).first()
            if previous_status != 'DELIVERED' and not obj.confirmation_verified_at:
                raise ValidationError(
                    'Use the partner handoff-code flow to complete this delivery.'
                )

        # When first assigned
        if obj.status == 'ASSIGNED' and obj.assigned_at is None:
            obj.assigned_at = timezone.now()
            if obj.delivery_partner:
                obj.delivery_partner.is_available = False
                obj.delivery_partner.save()

        # When delivered — free the partner
        if obj.status == 'DELIVERED':
            if obj.delivery_partner:
                obj.delivery_partner.is_available = True
                obj.delivery_partner.save()

        # FIX: sync Order status using the unified constants from orders/models.py
        delivery_to_order_status = {
            'ASSIGNED':    'CONFIRMED',
            'PICKED_UP':   'PREPARING',
            'ON_THE_WAY':  'ON_THE_WAY',
            'DELIVERED':   'DELIVERED',
        }
        new_order_status = delivery_to_order_status.get(obj.status)
        if new_order_status:
            obj.order.status = new_order_status
            obj.order.save()

        super().save_model(request, obj, form, change)

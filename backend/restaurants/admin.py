from django.contrib import admin
from .models import (
    FoodItem,
    FoodOption,
    FoodOptionGroup,
    MerchantFulfillmentRequest,
    MerchantFulfillmentRequestEvent,
    MerchantNetworkRelationship,
    MerchantProfile,
    Restaurant,
    RestaurantReview,
    ReviewPhoto,
)


class FoodItemInline(admin.TabularInline):
    model = FoodItem
    extra = 0


class FoodOptionInline(admin.TabularInline):
    model = FoodOption
    extra = 0


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = (
        'rest_name', 'branch_name', 'branch_type', 'owner', 'market',
        'country_code', 'rest_city', 'area_ref', 'is_open',
        'is_active', 'delivery_fee', 'min_order_amount', 'commission_percent',
    )
    search_fields = ('rest_name', 'branch_name', 'branch_code', 'rest_city', 'rest_email')
    list_filter = ('branch_type', 'market', 'country_code', 'rest_city', 'area_ref')
    inlines = (FoodItemInline,)


@admin.register(MerchantProfile)
class MerchantProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'business_name', 'phone', 'is_verified')
    list_filter = ('is_verified',)
    search_fields = ('user__username', 'business_name', 'phone')
    actions = ('approve_merchants', 'suspend_merchants')

    @admin.action(description='Approve selected merchants')
    def approve_merchants(self, request, queryset):
        for merchant in queryset:
            merchant.is_verified = True
            merchant.save(update_fields=['is_verified'])


@admin.register(MerchantNetworkRelationship)
class MerchantNetworkRelationshipAdmin(admin.ModelAdmin):
    list_display = (
        'from_merchant', 'to_merchant', 'status',
        'distance_km', 'requested_by', 'approved_by', 'requested_at',
    )
    list_filter = ('status', 'requested_at', 'approved_at')
    search_fields = (
        'from_merchant__business_name',
        'from_merchant__user__username',
        'to_merchant__business_name',
        'to_merchant__user__username',
        'notes',
    )
    readonly_fields = ('requested_at', 'updated_at')


@admin.register(MerchantFulfillmentRequest)
class MerchantFulfillmentRequestAdmin(admin.ModelAdmin):
    list_display = (
        'order', 'requesting_merchant', 'fulfilling_merchant',
        'status', 'internal_status', 'requested_by', 'responded_by',
        'created_at',
    )
    list_filter = ('status', 'internal_status', 'created_at', 'responded_at')
    search_fields = (
        'order__id',
        'requesting_merchant__business_name',
        'fulfilling_merchant__business_name',
        'notes',
    )
    readonly_fields = (
        'requested_at', 'created_at', 'updated_at',
        'preparation_started_at', 'ready_for_handoff_at',
        'resolved_at', 'cancelled_at',
    )

    @admin.action(description='Suspend selected merchants')
    def suspend_merchants(self, request, queryset):
        for merchant in queryset:
            merchant.is_verified = False
            merchant.save(update_fields=['is_verified'])


@admin.register(MerchantFulfillmentRequestEvent)
class MerchantFulfillmentRequestEventAdmin(admin.ModelAdmin):
    list_display = (
        'fulfillment_request', 'event_type', 'from_status',
        'to_status', 'actor', 'created_at',
    )
    list_filter = ('event_type', 'created_at')
    search_fields = (
        'fulfillment_request__order__id',
        'fulfillment_request__requesting_merchant__business_name',
        'fulfillment_request__fulfilling_merchant__business_name',
        'note',
    )
    readonly_fields = ('created_at',)


@admin.register(FoodItem)
class FoodItemAdmin(admin.ModelAdmin):
    list_display = ('food_name', 'restaurant', 'food_categ', 'food_price')
    list_filter = ('food_categ', 'restaurant')
    search_fields = ('food_name', 'restaurant__rest_name')


@admin.register(FoodOptionGroup)
class FoodOptionGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'food', 'min_select', 'max_select', 'ordering')
    list_filter = ('food__restaurant',)
    search_fields = ('name', 'food__food_name')
    inlines = (FoodOptionInline,)


@admin.register(RestaurantReview)
class RestaurantReviewAdmin(admin.ModelAdmin):
    list_display = ('restaurant', 'customer', 'rating', 'order', 'created_at')
    list_filter = ('rating', 'restaurant', 'created_at')
    search_fields = ('customer__username', 'restaurant__rest_name', 'comment')
    readonly_fields = ('created_at',)


@admin.register(ReviewPhoto)
class ReviewPhotoAdmin(admin.ModelAdmin):
    list_display = (
        'review', 'uploaded_by', 'status', 'reviewed_by',
        'reviewed_at', 'created_at',
    )
    list_filter = ('status', 'created_at', 'reviewed_at')
    search_fields = (
        'review__restaurant__rest_name',
        'review__customer__username',
        'uploaded_by__username',
        'caption',
        'moderation_reason',
    )
    readonly_fields = ('created_at', 'updated_at')

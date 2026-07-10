from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from delivery.models import DeliveryPartner, MerchantRider, MerchantRiderInvite
from delivery.services import auto_assign_delivery
from fooddelivery.dashboard_cache import (
    get_cached_response_data,
    set_cached_response_data,
)
from fooddelivery.upload_validation import prepare_public_image_upload
from merchant_staff.models import (
    MerchantStaffBranchAccess,
    MerchantStaffInvite,
    MerchantStaffMember,
)
from merchant_staff.permissions import (
    MANAGE_BRANCHES,
    MANAGE_FULFILLMENT,
    MANAGE_MENU,
    MANAGE_RIDERS,
    UPDATE_ORDER_STATUS,
    VIEW_ANALYTICS,
    VIEW_BRANCHES,
    VIEW_FINANCE,
    VIEW_FULFILLMENT,
    VIEW_MENU,
    VIEW_ORDERS,
    VIEW_RIDERS,
    VIEW_SUPPORT,
    can_access_branch,
    filter_queryset_for_actor,
    get_merchant_actor,
    permitted_branch_ids,
)
from notifications.models import Notification
from notifications.events import (
    notify_order_event,
    notify_payment_event,
    schedule_notification_event,
)
from orders.models import Order, OrderItem
from restaurants.models import (
    FoodItem,
    FoodOption,
    FoodOptionGroup,
    MerchantFulfillmentRequest,
    MerchantFulfillmentRequestEvent,
    MerchantNetworkRelationship,
    RestaurantReview,
    ReviewPhoto,
    Restaurant,
    RestaurantOperatingHour,
)
from restaurants.models import MerchantProfile
from restaurants.services import (
    SETTLEMENT_PREVIEW_LABEL,
    ensure_fulfillment_settlement_preview,
    find_nearby_merchants,
    restaurant_accepting_orders,
)


def require_merchant(user):
    if not hasattr(user, 'merchant_profile'):
        raise PermissionDenied('Merchant access required.')
    return user.merchant_profile


def require_merchant_actor(user, permission=None, owner_only=False):
    actor = get_merchant_actor(user)
    if owner_only:
        if not actor.is_owner:
            raise PermissionDenied('Merchant owner access required.')
        return actor
    if not actor.has_merchant_access:
        raise PermissionDenied('Merchant access required.')
    if permission and not actor.has_permission(permission):
        raise PermissionDenied('You do not have permission for this merchant action.')
    return actor


def _normalized_phone_candidates(phone):
    if not phone:
        return set()
    compact = ''.join(char for char in str(phone).strip() if char.isdigit() or char == '+')
    digits = ''.join(char for char in str(phone) if char.isdigit())
    return {value for value in {phone.strip(), compact, digits} if value}


def _match_existing_delivery_partner(email='', phone=''):
    query = Q()
    if email:
        query |= Q(user__email__iexact=email.strip())
    phone_candidates = _normalized_phone_candidates(phone)
    if phone_candidates:
        query |= Q(partner_phone__in=phone_candidates)
    if not query:
        return None
    return DeliveryPartner.objects.select_related('user').filter(query).first()


def _branch_scope(branch):
    if not branch:
        return {}
    market = branch.market
    return {
        'branch': branch,
        'market': market,
        'country_code': branch.country_code or getattr(market, 'country_code', None),
        'city': branch.city_ref,
        'area': branch.area_ref,
    }


def _notify_existing_partner_invited(invite):
    if not invite.linked_partner_id:
        return
    merchant_name = invite.merchant.business_name or invite.merchant.user.get_full_name() or invite.merchant.user.username
    branch_name = (
        invite.home_restaurant.branch_name
        or invite.home_restaurant.rest_name
        if invite.home_restaurant_id else ''
    )
    schedule_notification_event(
        event_type='rider.merchant_invite',
        actor=invite.invited_by,
        recipients={'delivery_partner': invite.linked_partner},
        subject=invite,
        scope=_branch_scope(invite.home_restaurant),
        payload={
            'title': f'Merchant invitation from {merchant_name}',
            'message': (
                f'{merchant_name} invited you to deliver for'
                f' {branch_name or "their T-Food storefront"}. Open your partner dashboard to review it.'
            ),
            'intent': 'dispatch',
            'metadata': {
                'merchant_rider_invite_id': invite.id,
                'merchant_id': invite.merchant_id,
                'branch_id': invite.home_restaurant_id,
            },
        },
        priority=Notification.PRIORITY_NORMAL,
        category=Notification.CATEGORY_RIDER,
        action_url='/partner/dashboard',
        idempotency_key=f'rider.merchant_invite:{invite.id}',
    )


def merchant_actor_branch_queryset(actor):
    if not actor or not actor.merchant:
        return Restaurant.objects.none()
    return filter_queryset_for_actor(
        Restaurant.objects.filter(owner=actor.merchant.user),
        actor,
        'id',
    )


def merchant_actor_order_queryset(actor, payment_statuses=None):
    payment_statuses = payment_statuses or (
        'SUCCESS', 'PENDING', 'REFUNDED', 'CANCELLED'
    )
    return (
        Order.objects.filter(
            items__food__restaurant__id__in=permitted_branch_ids(actor),
            payment__status__in=payment_statuses,
        )
        .distinct()
    )


def get_actor_branch_or_404(actor, branch_id):
    branch = Restaurant.objects.filter(
        id=branch_id,
        owner=actor.merchant.user,
    ).first()
    if not branch or not can_access_branch(actor, branch):
        raise PermissionDenied('You do not have access to this branch.')
    return branch


def actor_can_access_order_branch(actor, order):
    if not actor or not order:
        return False
    if actor.is_owner or actor.is_company_wide:
        return order_belongs_to_merchant(order, actor.merchant)
    branch = getattr(order, 'pickup_branch', None)
    if branch:
        return can_access_branch(actor, branch)
    return order.items.filter(
        food__restaurant_id__in=permitted_branch_ids(actor)
    ).exists()


def merchant_order_queryset(user):
    return Order.objects.filter(
        items__food__restaurant__owner=user,
        payment__status__in=('SUCCESS', 'PENDING', 'REFUNDED', 'CANCELLED'),
    ).distinct()


def merchant_branch_order_queryset(user, branch):
    return Order.objects.filter(
        items__food__restaurant=branch,
        payment__status__in=('SUCCESS', 'PENDING', 'REFUNDED', 'CANCELLED'),
    ).distinct()


def analytics_start(range_key):
    now = timezone.localtime()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if range_key == 'today':
        return today
    if range_key == 'yesterday':
        return today - timedelta(days=1)
    if range_key == '30d':
        return today - timedelta(days=29)
    if range_key == 'month':
        return today.replace(day=1)
    if range_key == 'year':
        return today.replace(month=1, day=1)
    return today - timedelta(days=6)


def average_minutes(durations):
    values = [value for value in durations if value is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def prep_metric_minutes(order, start_status, end_status):
    events = {event.status: event.created_at for event in order.status_events.all()}
    if start_status not in events or end_status not in events:
        return None
    seconds = (events[end_status] - events[start_status]).total_seconds()
    if seconds < 0:
        return None
    return seconds / 60


def percent_change(current, previous):
    if not previous:
        return None if current else 0
    return round(((current - previous) / previous) * 100, 2)


def period_stats(base_orders, start, end=None):
    orders = base_orders.filter(created_at__gte=start)
    if end:
        orders = orders.filter(created_at__lt=end)
    delivered_ids = list(
        orders.filter(
            status='DELIVERED',
            payment__status='SUCCESS',
        ).values_list('id', flat=True)
    )
    delivered = Order.objects.filter(id__in=delivered_ids)
    gross_sales = delivered.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    merchant_earnings = delivered.aggregate(total=Sum('merchant_payout'))['total'] or Decimal('0.00')
    delivered_count = delivered.count()
    cancelled_count = orders.filter(status='CANCELLED').count()
    average_order_value = (
        (gross_sales / delivered_count).quantize(Decimal('0.01'))
        if delivered_count else Decimal('0.00')
    )
    return {
        'gross_sales': gross_sales,
        'merchant_earnings': merchant_earnings,
        'average_order_value': average_order_value,
        'delivered_orders': delivered_count,
        'cancelled_orders': cancelled_count,
    }


class MerchantRestaurantSerializer(serializers.ModelSerializer):
    item_count = serializers.IntegerField(read_only=True, default=0)
    accepting_orders = serializers.SerializerMethodField()
    menu_items = serializers.SerializerMethodField()
    operating_hours = serializers.SerializerMethodField()
    branch_manager_name = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    area = serializers.SerializerMethodField()
    market_name = serializers.CharField(source='market.name', read_only=True)
    market_slug = serializers.CharField(source='market.slug', read_only=True)
    currency_code = serializers.SerializerMethodField()

    class Meta:
        model = Restaurant
        fields = (
            'id', 'rest_name', 'rest_email', 'rest_contact', 'rest_address',
            'rest_city', 'branch_name', 'branch_code', 'branch_type', 'delivery_mode',
            'country_code', 'market', 'market_name', 'market_slug',
            'currency_code', 'city', 'area', 'city_ref', 'area_ref',
            'branch_manager', 'branch_manager_name',
            'delivery_fee', 'is_active', 'is_open', 'accepting_orders', 'item_count',
            'min_order_amount', 'delivery_radius_km',
            'estimated_prep_minutes', 'commission_percent', 'menu_items',
            'cover_image',
            'pickup_latitude', 'pickup_longitude',
            'operating_hours',
        )
        read_only_fields = (
            'id', 'is_active', 'accepting_orders', 'item_count', 'commission_percent',
            'operating_hours', 'market_name', 'market_slug', 'currency_code', 'city', 'area',
            'branch_manager_name',
        )

    def get_branch_manager_name(self, obj):
        manager = obj.branch_manager
        if not manager:
            return ''
        return manager.get_full_name() or manager.username

    def get_city(self, obj):
        return obj.city_ref.name if obj.city_ref_id else obj.rest_city

    def get_area(self, obj):
        return obj.area_ref.name if obj.area_ref_id else ''

    def get_currency_code(self, obj):
        country_currency = {
            'GN': 'GNF',
            'IN': 'INR',
            'US': 'USD',
            'SA': 'SAR',
        }.get((obj.country_code or '').upper())
        if country_currency:
            return country_currency
        if obj.market_id and obj.market.default_currency_id:
            return obj.market.default_currency.code
        return 'GNF'

    def get_accepting_orders(self, obj):
        return restaurant_accepting_orders(obj)

    def get_menu_items(self, obj):
        return [
            {
                'id': item.id,
                'food_name': item.food_name,
                'food_desc': item.food_desc,
                'food_price': item.food_price,
                'food_categ': item.food_categ,
                'is_available': item.is_available,
                'image': (
                    self.context['request'].build_absolute_uri(item.image.url)
                    if item.image else None
                ),
                'option_groups': [
                    {
                        'id': group.id,
                        'name': group.name,
                        'min_select': group.min_select,
                        'max_select': group.max_select,
                        'ordering': group.ordering,
                        'options': [
                            {
                                'id': option.id,
                                'name': option.name,
                                'price_delta': option.price_delta,
                                'is_available': option.is_available,
                                'ordering': option.ordering,
                            }
                            for option in group.options.all()
                        ],
                    }
                    for group in item.option_groups.all()
                ],
            }
            for item in obj.food_items.all()
        ]

    def get_operating_hours(self, obj):
        return [
            {
                'day_of_week': entry.day_of_week,
                'day_display': entry.get_day_of_week_display(),
                'is_closed': entry.is_closed,
                'opens_at': entry.opens_at.strftime('%H:%M'),
                'closes_at': entry.closes_at.strftime('%H:%M'),
            }
            for entry in obj.operating_hours.all()
        ]

    def validate_cover_image(self, value):
        if not value:
            return value
        try:
            return prepare_public_image_upload(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)

    def validate(self, attrs):
        latitude = attrs.get(
            'pickup_latitude', getattr(self.instance, 'pickup_latitude', None)
        )
        longitude = attrs.get(
            'pickup_longitude', getattr(self.instance, 'pickup_longitude', None)
        )
        if (latitude is None) != (longitude is None):
            raise serializers.ValidationError(
                'Pickup latitude and longitude must be provided together.'
            )
        city_ref = attrs.get('city_ref', getattr(self.instance, 'city_ref', None))
        area_ref = attrs.get('area_ref', getattr(self.instance, 'area_ref', None))
        if area_ref and not city_ref:
            city_ref = area_ref.city
            attrs['city_ref'] = city_ref
        if city_ref and area_ref and area_ref.city_id != city_ref.id:
            raise serializers.ValidationError({
                'area_ref': 'Choose an area inside the selected city.'
            })
        if city_ref and not attrs.get('country_code'):
            attrs['country_code'] = city_ref.market.country_code
        if city_ref and not attrs.get('market'):
            attrs['market'] = city_ref.market
        return attrs

    def create(self, validated_data):
        if 'is_open' not in self.context['request'].data:
            validated_data['is_open'] = True
        return super().create(validated_data)


class MerchantFoodItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = FoodItem
        fields = (
            'id', 'food_name', 'food_desc', 'food_price',
            'food_categ', 'is_available',
            'image',
        )
        read_only_fields = ('id',)

    def validate_image(self, value):
        if not value:
            return value
        try:
            return prepare_public_image_upload(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)

    def create(self, validated_data):
        if 'is_available' not in self.context['request'].data:
            validated_data['is_available'] = True
        return super().create(validated_data)


class MerchantOrderSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()
    customer_phone = serializers.CharField(source='contact_phone', read_only=True)
    items = serializers.SerializerMethodField()
    payment_method = serializers.CharField(source='payment.method', read_only=True)
    payment_status = serializers.CharField(source='payment.status', read_only=True)
    pickup_branch = serializers.IntegerField(source='pickup_branch_id', read_only=True)
    pickup_branch_name = serializers.SerializerMethodField()
    branch_type = serializers.SerializerMethodField()
    delivery_status = serializers.CharField(source='delivery.status', read_only=True, allow_null=True)
    delivery_partner_name = serializers.CharField(source='delivery.delivery_partner.partner_name', read_only=True, allow_null=True)
    delivery_partner_phone = serializers.CharField(source='delivery.delivery_partner.partner_phone', read_only=True, allow_null=True)
    delivery_partner_transport = serializers.CharField(source='delivery.delivery_partner.transport_details', read_only=True, allow_null=True)
    delivery_partner_assigned_at = serializers.DateTimeField(source='delivery.assigned_at', read_only=True, allow_null=True)

    class Meta:
        model = Order
        fields = (
            'id', 'merchant_order_code', 'merchant_sequence_date',
            'merchant_daily_sequence', 'customer_name', 'customer_phone', 'delivery_address',
            'delivery_instructions',
            'status', 'subtotal_amount', 'discount_amount', 'delivery_fee',
            'total_amount', 'platform_fee', 'merchant_payout',
            'payment_method', 'payment_status', 'items', 'created_at',
            'merchant_payout_status', 'merchant_paid_at',
            'delivery_distance_km', 'estimated_delivery_at',
            'pickup_branch', 'pickup_branch_name', 'branch_type',
            'delivery_status', 'delivery_partner_name', 'delivery_partner_phone',
            'delivery_partner_transport', 'delivery_partner_assigned_at',
        )

    def get_customer_name(self, obj):
        return obj.customer.get_full_name() or obj.customer.username

    def get_items(self, obj):
        return [
            {
                'id': item.id,
                'name': item.food.food_name,
                'quantity': item.quantity,
                'price': item.price,
                'selected_options': item.selected_options,
            }
            for item in obj.items.all()
        ]

    def get_pickup_branch(self, obj):
        if hasattr(obj, '_cached_pickup_branch_for_serializer'):
            return obj._cached_pickup_branch_for_serializer
        branch = obj.pickup_branch
        if branch:
            obj._cached_pickup_branch_for_serializer = branch
            return branch
        first_item = obj.items.first()
        branch = first_item.food.restaurant if first_item else None
        obj._cached_pickup_branch_for_serializer = branch
        return branch

    def get_pickup_branch_name(self, obj):
        branch = self.get_pickup_branch(obj)
        return branch.branch_name or branch.rest_name if branch else ''

    def get_branch_type(self, obj):
        branch = self.get_pickup_branch(obj)
        return branch.branch_type if branch else ''


class MerchantPayoutSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(source='id', read_only=True)
    customer_name = serializers.SerializerMethodField()
    payment_method = serializers.CharField(source='payment.method', read_only=True)
    payment_status = serializers.CharField(source='payment.status', read_only=True)

    class Meta:
        model = Order
        fields = (
            'order_id', 'customer_name', 'status', 'total_amount',
            'platform_fee', 'merchant_payout', 'merchant_payout_status',
            'merchant_paid_at', 'payment_method', 'payment_status',
            'created_at',
        )

    def get_customer_name(self, obj):
        return obj.customer.get_full_name() or obj.customer.username


class MerchantNotificationSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = Notification
        fields = (
            'id', 'kind', 'title', 'message', 'order_id',
            'is_read', 'created_at',
        )


class MerchantReviewPhotoSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ReviewPhoto
        fields = (
            'id', 'caption', 'status', 'image_url', 'created_at',
        )

    def get_image_url(self, obj):
        if obj.status != ReviewPhoto.STATUS_APPROVED or not obj.image:
            return None
        request = self.context.get('request')
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url


class MerchantReviewSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()
    branch_id = serializers.IntegerField(source='restaurant_id', read_only=True)
    branch_name = serializers.SerializerMethodField()
    order_id = serializers.IntegerField(source='order.id', read_only=True)
    photos = MerchantReviewPhotoSerializer(many=True, read_only=True)

    class Meta:
        model = RestaurantReview
        fields = (
            'id', 'branch_id', 'branch_name', 'order_id', 'customer_name',
            'rating', 'comment', 'created_at', 'photos',
        )

    def get_customer_name(self, obj):
        return obj.customer.get_full_name() or obj.customer.username

    def get_branch_name(self, obj):
        return obj.restaurant.branch_name or obj.restaurant.rest_name


class MerchantRestaurantListCreateView(generics.ListCreateAPIView):
    serializer_class = MerchantRestaurantSerializer

    def get_queryset(self):
        actor = require_merchant_actor(self.request.user, VIEW_BRANCHES)
        return merchant_actor_branch_queryset(actor).select_related(
            'market__default_currency', 'city_ref', 'area_ref', 'branch_manager',
        ).annotate(
            item_count=Count('food_items', distinct=True),
        ).prefetch_related(
            'operating_hours', 'food_items__option_groups__options'
        ).order_by('rest_name')

    def perform_create(self, serializer):
        actor = require_merchant_actor(self.request.user, MANAGE_BRANCHES)
        profile = actor.merchant
        restaurant = serializer.save(
            owner=profile.user,
            is_active=profile.is_verified,
        )
        if not profile.business_name:
            profile.business_name = restaurant.rest_name
            profile.phone = restaurant.rest_contact
            profile.save(update_fields=['business_name', 'phone'])


class MerchantProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = MerchantProfile
        fields = (
            'business_name', 'phone', 'subscription_plan', 'is_verified',
            'verification_status', 'verification_rejection_reason',
            'verification_submitted_at', 'verification_reviewed_at',
        )
        read_only_fields = (
            'is_verified', 'verification_status',
            'verification_rejection_reason', 'verification_submitted_at',
            'verification_reviewed_at',
        )


class MerchantProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = MerchantProfileSerializer

    def get_object(self):
        return require_merchant(self.request.user)


def branch_payload(branch):
    if not branch:
        return None
    market = branch.market
    return {
        'id': branch.id,
        'name': branch.rest_name,
        'branch_name': branch.branch_name or branch.rest_name,
        'branch_type': branch.branch_type,
        'is_active': branch.is_active,
        'is_open': branch.is_open,
        'market': {
            'id': market.id,
            'name': market.name,
            'slug': market.slug,
            'country_code': market.country_code,
        } if market else None,
        'city': branch.city_ref.name if branch.city_ref_id else branch.rest_city,
        'area': branch.area_ref.name if branch.area_ref_id else '',
    }


class MerchantStaffMemberSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    email = serializers.EmailField(source='user.email', read_only=True)
    phone = serializers.SerializerMethodField()
    assigned_branches = serializers.SerializerMethodField()

    class Meta:
        model = MerchantStaffMember
        fields = (
            'id', 'user', 'name', 'email', 'phone', 'role',
            'membership_status', 'verification_status',
            'verification_rejection_reason', 'is_company_wide',
            'assigned_branches', 'created_at', 'updated_at',
        )

    def get_user(self, obj):
        return {
            'id': obj.user_id,
            'username': obj.user.username,
            'email': obj.user.email,
        }

    def get_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    def get_phone(self, obj):
        return (
            obj.accepted_invites
            .exclude(phone='')
            .order_by('-updated_at', '-created_at')
            .values_list('phone', flat=True)
            .first()
        ) or ''

    def get_assigned_branches(self, obj):
        branches = [access.branch for access in obj.branch_access.all()]
        return [branch_payload(branch) for branch in branches]


class MerchantStaffInviteSerializer(serializers.ModelSerializer):
    branch_ids = serializers.PrimaryKeyRelatedField(
        queryset=Restaurant.objects.none(),
        many=True,
        required=False,
        write_only=True,
    )
    branches = serializers.SerializerMethodField()

    class Meta:
        model = MerchantStaffInvite
        fields = (
            'id', 'name', 'email', 'phone', 'role', 'is_company_wide',
            'branch_ids', 'branches', 'invite_token', 'status', 'expires_at',
            'linked_staff_member', 'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'branches', 'invite_token', 'status', 'expires_at',
            'linked_staff_member', 'created_at', 'updated_at',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['branch_ids'].child_relation.queryset = Restaurant.objects.all()

    def validate(self, attrs):
        request = self.context.get('request')
        branches = attrs.get('branch_ids') or []
        for branch in branches:
            if not request or branch.owner_id != request.user.id:
                raise serializers.ValidationError({
                    'branch_ids': ['Choose branches owned by this merchant.'],
                })
            if not branch.is_active:
                raise serializers.ValidationError({
                    'branch_ids': ['Choose active branches only.'],
                })
        if not attrs.get('is_company_wide') and not attrs.get('branch_ids'):
            raise serializers.ValidationError({
                'branch_ids': [
                    'Choose at least one branch or make this staff company-wide.'
                ],
            })
        return attrs

    def create(self, validated_data):
        branches = validated_data.pop('branch_ids', [])
        invite = super().create(validated_data)
        invite.branches.set(branches)
        return invite

    def get_branches(self, obj):
        return [branch_payload(branch) for branch in obj.branches.all()]


class MerchantStaffUpdateSerializer(serializers.Serializer):
    blocked_fields = {
        'verification_status',
        'verification_rejection_reason',
        'verification_submitted_at',
        'verification_reviewed_at',
        'verification_reviewed_by',
    }
    role = serializers.ChoiceField(
        choices=MerchantStaffMember.ROLE_CHOICES,
        required=False,
    )
    is_company_wide = serializers.BooleanField(required=False)
    membership_status = serializers.ChoiceField(
        choices=(
            MerchantStaffMember.STATUS_ACTIVE,
            MerchantStaffMember.STATUS_INACTIVE,
            MerchantStaffMember.STATUS_REMOVED,
        ),
        required=False,
    )

    def validate(self, attrs):
        blocked = self.blocked_fields.intersection(self.initial_data.keys())
        if blocked:
            raise serializers.ValidationError({
                field: ['Only T-Food Operations can change verification fields.']
                for field in sorted(blocked)
            })
        staff_member = self.context['staff_member']
        if (
            attrs.get('membership_status') == MerchantStaffMember.STATUS_ACTIVE
            and staff_member.verification_status != (
                MerchantStaffMember.VERIFICATION_VERIFIED
            )
        ):
            raise serializers.ValidationError({
                'membership_status': [
                    'T-Food Operations must verify this staff member before activation.'
                ],
            })
        return attrs


class MerchantStaffBranchAssignSerializer(serializers.Serializer):
    branch_ids = serializers.PrimaryKeyRelatedField(
        queryset=Restaurant.objects.none(),
        many=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['branch_ids'].child_relation.queryset = Restaurant.objects.all()

    def validate_branch_ids(self, value):
        request = self.context.get('request')
        for branch in value:
            if not request or branch.owner_id != request.user.id:
                raise serializers.ValidationError(
                    'Choose branches owned by this merchant.'
                )
            if not branch.is_active:
                raise serializers.ValidationError('Choose active branches only.')
        return value


def merchant_staff_with_branch_details():
    return (
        MerchantStaffMember.objects
        .select_related('user')
        .prefetch_related(
            'branch_access__branch__market',
            'branch_access__branch__city_ref',
            'branch_access__branch__area_ref',
        )
    )


class MerchantStaffListView(APIView):
    def get(self, request):
        merchant = require_merchant(request.user)
        staff = (
            merchant_staff_with_branch_details()
            .filter(merchant=merchant)
            .order_by('membership_status', 'user__username')
        )
        invites = (
            MerchantStaffInvite.objects
            .filter(merchant=merchant)
            .prefetch_related('branches__market', 'branches__city_ref', 'branches__area_ref')
            .order_by('-created_at')
        )
        return Response({
            'count': staff.count(),
            'results': MerchantStaffMemberSerializer(staff, many=True).data,
            'invites': MerchantStaffInviteSerializer(invites, many=True).data,
        })


class MerchantStaffInviteView(APIView):
    def post(self, request):
        merchant = require_merchant(request.user)
        serializer = MerchantStaffInviteSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        invite = serializer.save(merchant=merchant, invited_by=request.user)
        return Response(
            MerchantStaffInviteSerializer(invite).data,
            status=status.HTTP_201_CREATED,
        )


class MerchantStaffDetailView(APIView):
    @transaction.atomic
    def patch(self, request, staff_id):
        merchant = require_merchant(request.user)
        staff_member = (
            MerchantStaffMember.objects
            .select_for_update()
            .select_related('user')
            .filter(id=staff_id, merchant=merchant)
            .first()
        )
        if not staff_member:
            return Response(
                {'detail': 'Merchant staff member not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = MerchantStaffUpdateSerializer(
            data=request.data,
            context={'staff_member': staff_member},
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        update_fields = ['updated_at', 'updated_by']
        for field, value in serializer.validated_data.items():
            setattr(staff_member, field, value)
            update_fields.append(field)
        staff_member.updated_by = request.user
        staff_member.save(update_fields=update_fields)
        staff_member = (
            merchant_staff_with_branch_details()
            .get(id=staff_member.id)
        )
        return Response(MerchantStaffMemberSerializer(staff_member).data)


class MerchantStaffBranchListView(APIView):
    @transaction.atomic
    def post(self, request, staff_id):
        merchant = require_merchant(request.user)
        staff_member = (
            MerchantStaffMember.objects
            .select_for_update()
            .filter(id=staff_id, merchant=merchant)
            .first()
        )
        if not staff_member:
            return Response(
                {'detail': 'Merchant staff member not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if staff_member.membership_status == MerchantStaffMember.STATUS_REMOVED:
            return Response(
                {'detail': 'Removed staff cannot be assigned to branches.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = MerchantStaffBranchAssignSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        branches = serializer.validated_data['branch_ids']
        for branch in branches:
            MerchantStaffBranchAccess.objects.get_or_create(
                staff_member=staff_member,
                branch=branch,
                defaults={'created_by': request.user},
            )
        staff_member = (
            merchant_staff_with_branch_details()
            .get(id=staff_member.id)
        )
        return Response(MerchantStaffMemberSerializer(staff_member).data)


class MerchantStaffBranchDetailView(APIView):
    @transaction.atomic
    def delete(self, request, staff_id, branch_id):
        merchant = require_merchant(request.user)
        staff_member = MerchantStaffMember.objects.filter(
            id=staff_id,
            merchant=merchant,
        ).first()
        if not staff_member:
            return Response(
                {'detail': 'Merchant staff member not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        deleted, _ = MerchantStaffBranchAccess.objects.filter(
            staff_member=staff_member,
            branch_id=branch_id,
            branch__owner=request.user,
        ).delete()
        if not deleted:
            return Response(
                {'detail': 'Branch access not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class MerchantRiderSerializer(serializers.ModelSerializer):
    rider_name = serializers.CharField(source='partner.partner_name', read_only=True)
    rider_phone = serializers.CharField(source='partner.partner_phone', read_only=True)
    partner_account = serializers.SerializerMethodField()
    verification_status = serializers.CharField(
        source='partner.verification_status',
        read_only=True,
    )
    partner_is_verified = serializers.BooleanField(
        source='partner.is_verified',
        read_only=True,
    )
    availability = serializers.BooleanField(
        source='partner.is_available',
        read_only=True,
    )
    transport_type = serializers.CharField(
        source='partner.transport_details',
        read_only=True,
    )
    home_restaurant = serializers.SerializerMethodField()
    invitation_state = serializers.SerializerMethodField()

    class Meta:
        model = MerchantRider
        fields = (
            'id', 'rider_name', 'partner_account', 'verification_status',
            'partner_is_verified', 'rider_phone', 'status', 'home_restaurant',
            'availability', 'transport_type', 'invitation_state', 'approved_at',
            'created_at', 'updated_at',
        )

    def get_partner_account(self, obj):
        return {
            'id': obj.partner.user_id,
            'username': obj.partner.user.username,
            'email': obj.partner.user.email,
        }

    def get_home_restaurant(self, obj):
        if not obj.home_restaurant:
            return None
        market = obj.home_restaurant.market
        return {
            'id': obj.home_restaurant_id,
            'name': obj.home_restaurant.rest_name,
            'branch_name': obj.home_restaurant.branch_name or obj.home_restaurant.rest_name,
            'branch_type': obj.home_restaurant.branch_type,
            'is_active': obj.home_restaurant.is_active,
            'is_open': obj.home_restaurant.is_open,
            'market': {
                'id': market.id,
                'name': market.name,
                'slug': market.slug,
                'country_code': market.country_code,
            } if market else None,
            'city': obj.home_restaurant.city_ref.name if obj.home_restaurant.city_ref_id else obj.home_restaurant.rest_city,
            'area': obj.home_restaurant.area_ref.name if obj.home_restaurant.area_ref_id else '',
        }

    def get_invitation_state(self, obj):
        invite = obj.partner.merchant_rider_invites.order_by('-created_at').first()
        return invite.status if invite else None


class MerchantRiderInviteSerializer(serializers.ModelSerializer):
    home_restaurant = serializers.PrimaryKeyRelatedField(
        queryset=Restaurant.objects.none(),
        required=False,
        allow_null=True,
    )
    home_restaurant_detail = serializers.SerializerMethodField()

    class Meta:
        model = MerchantRiderInvite
        fields = (
            'id', 'name', 'phone', 'email', 'transport_type',
            'home_restaurant', 'home_restaurant_detail', 'invite_token',
            'status', 'expires_at', 'linked_partner', 'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'invite_token', 'status', 'expires_at',
            'linked_partner', 'created_at', 'updated_at',
            'home_restaurant_detail',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            actor = get_merchant_actor(request.user)
            self.fields['home_restaurant'].queryset = merchant_actor_branch_queryset(actor)

    def validate_home_restaurant(self, value):
        if value and not value.is_active:
            raise serializers.ValidationError(
                'Choose an active branch / storefront.'
            )
        return value

    def get_home_restaurant_detail(self, obj):
        if not obj.home_restaurant:
            return None
        market = obj.home_restaurant.market
        return {
            'id': obj.home_restaurant_id,
            'name': obj.home_restaurant.rest_name,
            'branch_name': obj.home_restaurant.branch_name or obj.home_restaurant.rest_name,
            'branch_type': obj.home_restaurant.branch_type,
            'is_active': obj.home_restaurant.is_active,
            'is_open': obj.home_restaurant.is_open,
            'market': {
                'id': market.id,
                'name': market.name,
                'slug': market.slug,
                'country_code': market.country_code,
            } if market else None,
            'city': obj.home_restaurant.city_ref.name if obj.home_restaurant.city_ref_id else obj.home_restaurant.rest_city,
            'area': obj.home_restaurant.area_ref.name if obj.home_restaurant.area_ref_id else '',
        }


class MerchantRiderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=(
        MerchantRider.STATUS_ACTIVE,
        MerchantRider.STATUS_INACTIVE,
        MerchantRider.STATUS_REMOVED,
    ))


class MerchantRiderAssignRestaurantSerializer(serializers.Serializer):
    home_restaurant = serializers.PrimaryKeyRelatedField(
        queryset=Restaurant.objects.none(),
        required=False,
        allow_null=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            actor = get_merchant_actor(request.user)
            self.fields['home_restaurant'].queryset = merchant_actor_branch_queryset(actor)

    def validate_home_restaurant(self, value):
        if value and not value.is_active:
            raise serializers.ValidationError(
                'Choose an active branch / storefront.'
            )
        return value


class MerchantRiderListView(APIView):
    def get(self, request):
        actor = require_merchant_actor(request.user, VIEW_RIDERS)
        merchant = actor.merchant
        riders = MerchantRider.objects.filter(
            merchant=merchant
        ).select_related(
            'partner__user',
            'home_restaurant__market',
            'home_restaurant__city_ref',
            'home_restaurant__area_ref',
        ).prefetch_related(
            'partner__merchant_rider_invites'
        ).order_by('status', 'partner__partner_name')
        if not actor.is_company_wide and not actor.is_owner:
            riders = riders.filter(home_restaurant_id__in=permitted_branch_ids(actor))
        branch_id = request.query_params.get('branch') or request.query_params.get('branch_id')
        if branch_id not in (None, ''):
            branch = Restaurant.objects.filter(
                id=branch_id,
                owner=merchant.user,
            ).first()
            if not branch or not can_access_branch(actor, branch):
                return Response(
                    {'branch': ['Choose a branch owned by this merchant.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            riders = riders.filter(home_restaurant_id=branch_id)
        invites = MerchantRiderInvite.objects.filter(
            merchant=merchant
        ).select_related('home_restaurant', 'linked_partner').order_by('-created_at')
        if not actor.is_company_wide and not actor.is_owner:
            invites = invites.filter(home_restaurant_id__in=permitted_branch_ids(actor))
        return Response({
            'count': riders.count(),
            'results': MerchantRiderSerializer(riders, many=True).data,
            'invites': MerchantRiderInviteSerializer(
                invites,
                many=True,
                context={'request': request},
            ).data,
        })


class MerchantRiderInviteView(APIView):
    def post(self, request):
        actor = require_merchant_actor(request.user, MANAGE_RIDERS)
        merchant = actor.merchant
        serializer = MerchantRiderInviteSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        linked_partner = _match_existing_delivery_partner(
            serializer.validated_data.get('email', ''),
            serializer.validated_data.get('phone', ''),
        )
        invite = serializer.save(
            merchant=merchant,
            invited_by=request.user,
            linked_partner=linked_partner,
        )
        transaction.on_commit(lambda: _notify_existing_partner_invited(invite))
        return Response(
            MerchantRiderInviteSerializer(
                invite,
                context={'request': request},
            ).data,
            status=status.HTTP_201_CREATED,
        )


class MerchantRiderStatusView(APIView):
    @transaction.atomic
    def patch(self, request, rider_id):
        actor = require_merchant_actor(request.user, MANAGE_RIDERS)
        merchant = actor.merchant
        rider = MerchantRider.objects.select_for_update().select_related(
            'partner'
        ).filter(id=rider_id, merchant=merchant).first()
        if rider and not (
            actor.is_owner
            or actor.is_company_wide
            or rider.home_restaurant_id in permitted_branch_ids(actor)
        ):
            rider = None
        if not rider:
            return Response(
                {'detail': 'Merchant rider not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = MerchantRiderStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        requested_status = serializer.validated_data['status']
        if (
            requested_status == MerchantRider.STATUS_ACTIVE
            and not rider.partner.is_verified
        ):
            return Response(
                {'status': ['T-Food operations must verify this rider before activation.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        rider.status = requested_status
        rider.save(update_fields=['status', 'updated_at'])
        rider = MerchantRider.objects.select_related(
            'partner__user', 'home_restaurant'
        ).get(id=rider.id)
        return Response(MerchantRiderSerializer(rider).data)


class MerchantRiderAssignRestaurantView(APIView):
    @transaction.atomic
    def post(self, request, rider_id):
        actor = require_merchant_actor(request.user, MANAGE_RIDERS)
        merchant = actor.merchant
        rider = MerchantRider.objects.select_for_update().filter(
            id=rider_id,
            merchant=merchant,
        ).first()
        if rider and not (
            actor.is_owner
            or actor.is_company_wide
            or rider.home_restaurant_id in permitted_branch_ids(actor)
            or rider.home_restaurant_id is None
        ):
            rider = None
        if not rider:
            return Response(
                {'detail': 'Merchant rider not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = MerchantRiderAssignRestaurantSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        if rider.status == MerchantRider.STATUS_REMOVED:
            return Response(
                {'detail': 'Removed riders cannot be assigned to a branch.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        rider.home_restaurant = serializer.validated_data.get('home_restaurant')
        rider.save(update_fields=['home_restaurant', 'updated_at'])
        rider = MerchantRider.objects.select_related(
            'partner__user', 'home_restaurant'
        ).get(id=rider.id)
        return Response(MerchantRiderSerializer(rider).data)


class MerchantNetworkMerchantSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    distance_km = serializers.DecimalField(
        max_digits=7,
        decimal_places=2,
        read_only=True,
        required=False,
    )

    class Meta:
        model = MerchantProfile
        fields = (
            'id', 'user_id', 'username', 'business_name', 'phone',
            'is_verified', 'verification_status', 'distance_km',
        )


class MerchantNetworkRelationshipSerializer(serializers.ModelSerializer):
    from_merchant = MerchantNetworkMerchantSerializer(read_only=True)
    to_merchant = MerchantNetworkMerchantSerializer(read_only=True)
    direction = serializers.SerializerMethodField()

    class Meta:
        model = MerchantNetworkRelationship
        fields = (
            'id', 'from_merchant', 'to_merchant', 'status', 'direction',
            'notes', 'distance_km', 'requested_at', 'approved_at', 'updated_at',
        )

    def get_direction(self, obj):
        merchant = self.context.get('merchant')
        if merchant and obj.from_merchant_id == merchant.id:
            return 'outgoing'
        if merchant and obj.to_merchant_id == merchant.id:
            return 'incoming'
        return None


class MerchantNetworkRequestSerializer(serializers.Serializer):
    to_merchant = serializers.PrimaryKeyRelatedField(
        queryset=MerchantProfile.objects.all(),
    )
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_to_merchant(self, to_merchant):
        merchant = self.context['merchant']
        if to_merchant.id == merchant.id:
            raise serializers.ValidationError('You cannot request yourself.')
        return to_merchant


class MerchantNetworkActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=('ACCEPT', 'PAUSE', 'BLOCK'))


def relationship_for_merchants(from_merchant, to_merchant):
    return MerchantNetworkRelationship.objects.filter(
        Q(from_merchant=from_merchant, to_merchant=to_merchant)
        | Q(from_merchant=to_merchant, to_merchant=from_merchant)
    ).order_by('-requested_at').first()


class MerchantNetworkNearbyView(APIView):
    def get(self, request):
        merchant = require_merchant(request.user)
        try:
            radius_km = Decimal(str(request.query_params.get('radius_km', '5')))
        except Exception:
            return Response(
                {'radius_km': ['Radius must be a number.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if radius_km <= 0 or radius_km > 50:
            return Response(
                {'radius_km': ['Radius must be between 0 and 50 km.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        restaurant_id = request.query_params.get('restaurant_id')
        if restaurant_id:
            if not Restaurant.objects.filter(
                id=restaurant_id,
                owner=request.user,
            ).exists():
                return Response(
                    {'restaurant_id': ['Choose one of your restaurants.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        nearby_merchants = find_nearby_merchants(merchant, radius_km=radius_km)
        results = []
        for nearby in nearby_merchants:
            relationship = relationship_for_merchants(merchant, nearby)
            data = MerchantNetworkMerchantSerializer(nearby).data
            data['relationship'] = (
                MerchantNetworkRelationshipSerializer(
                    relationship,
                    context={'merchant': merchant},
                ).data
                if relationship else None
            )
            data['relationship_status'] = relationship.status if relationship else None
            results.append(data)
        return Response({
            'radius_km': radius_km,
            'count': len(results),
            'results': results,
        })


class MerchantNetworkRequestView(APIView):
    @transaction.atomic
    def post(self, request):
        merchant = require_merchant(request.user)
        serializer = MerchantNetworkRequestSerializer(
            data=request.data,
            context={'merchant': merchant},
        )
        serializer.is_valid(raise_exception=True)
        to_merchant = serializer.validated_data['to_merchant']
        notes = serializer.validated_data.get('notes', '')
        existing = MerchantNetworkRelationship.objects.filter(
            Q(from_merchant=merchant, to_merchant=to_merchant)
            | Q(from_merchant=to_merchant, to_merchant=merchant)
        ).first()
        if existing:
            return Response(
                {'detail': 'A relationship already exists with this merchant.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            relationship = MerchantNetworkRelationship.objects.create(
                from_merchant=merchant,
                to_merchant=to_merchant,
                requested_by=request.user,
                notes=notes,
            )
        except IntegrityError:
            return Response(
                {'detail': 'A relationship already exists with this merchant.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            MerchantNetworkRelationshipSerializer(
                relationship,
                context={'merchant': merchant},
            ).data,
            status=status.HTTP_201_CREATED,
        )


class MerchantNetworkListView(APIView):
    def get(self, request):
        merchant = require_merchant(request.user)
        relationships = (
            MerchantNetworkRelationship.objects
            .filter(Q(from_merchant=merchant) | Q(to_merchant=merchant))
            .select_related(
                'from_merchant__user',
                'to_merchant__user',
                'requested_by',
                'approved_by',
            )
            .order_by('-updated_at')
        )
        serializer_context = {'merchant': merchant}
        grouped = {
            'active': [],
            'requested': [],
            'paused': [],
            'blocked': [],
        }
        status_to_key = {
            MerchantNetworkRelationship.STATUS_ACTIVE: 'active',
            MerchantNetworkRelationship.STATUS_REQUESTED: 'requested',
            MerchantNetworkRelationship.STATUS_PAUSED: 'paused',
            MerchantNetworkRelationship.STATUS_BLOCKED: 'blocked',
        }
        for relationship in relationships:
            grouped[status_to_key[relationship.status]].append(
                MerchantNetworkRelationshipSerializer(
                    relationship,
                    context=serializer_context,
                ).data
            )
        grouped['count'] = relationships.count()
        return Response(grouped)


class MerchantNetworkRelationshipUpdateView(APIView):
    @transaction.atomic
    def patch(self, request, relationship_id):
        merchant = require_merchant(request.user)
        relationship = (
            MerchantNetworkRelationship.objects
            .select_for_update()
            .select_related('from_merchant__user', 'to_merchant__user')
            .filter(
                Q(from_merchant=merchant) | Q(to_merchant=merchant),
                id=relationship_id,
            )
            .first()
        )
        if not relationship:
            return Response(
                {'detail': 'Collaboration relationship not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = MerchantNetworkActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data['action']
        update_fields = ['status', 'updated_at']
        if action == 'ACCEPT':
            if relationship.to_merchant_id != merchant.id:
                return Response(
                    {'action': ['Only the receiving merchant can accept this request.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if relationship.status != MerchantNetworkRelationship.STATUS_REQUESTED:
                return Response(
                    {'action': ['Only requested relationships can be accepted.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            relationship.status = MerchantNetworkRelationship.STATUS_ACTIVE
            relationship.approved_by = request.user
            relationship.approved_at = timezone.now()
            update_fields += ['approved_by', 'approved_at']
        elif action == 'PAUSE':
            relationship.status = MerchantNetworkRelationship.STATUS_PAUSED
        elif action == 'BLOCK':
            relationship.status = MerchantNetworkRelationship.STATUS_BLOCKED
        relationship.save(update_fields=update_fields)
        relationship.refresh_from_db()
        return Response(
            MerchantNetworkRelationshipSerializer(
                relationship,
                context={'merchant': merchant},
            ).data
        )


class MerchantFulfillmentRequestSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(source='order.id', read_only=True)
    order_status = serializers.CharField(source='order.status', read_only=True)
    requesting_merchant = MerchantNetworkMerchantSerializer(read_only=True)
    fulfilling_merchant = MerchantNetworkMerchantSerializer(read_only=True)
    direction = serializers.SerializerMethodField()
    settlement_preview_label = serializers.SerializerMethodField()
    events = serializers.SerializerMethodField()

    class Meta:
        model = MerchantFulfillmentRequest
        fields = (
            'id', 'order_id', 'order_status', 'requesting_merchant',
            'fulfilling_merchant', 'relationship', 'status', 'direction',
            'internal_status', 'notes', 'operations_note', 'blocked_reason',
            'settlement_preview', 'settlement_preview_label',
            'preparation_started_at',
            'ready_for_handoff_at', 'resolved_at', 'cancelled_at',
            'requested_at', 'responded_at', 'events', 'created_at', 'updated_at',
        )

    def get_direction(self, obj):
        merchant = self.context.get('merchant')
        if merchant and obj.requesting_merchant_id == merchant.id:
            return 'outgoing'
        if merchant and obj.fulfilling_merchant_id == merchant.id:
            return 'incoming'
        return None

    def get_settlement_preview_label(self, obj):
        return SETTLEMENT_PREVIEW_LABEL if obj.settlement_preview else ''

    def get_events(self, obj):
        return [
            {
                'id': event.id,
                'event_type': event.event_type,
                'from_status': event.from_status,
                'to_status': event.to_status,
                'note': event.note,
                'actor': (
                    event.actor.get_full_name() or event.actor.username
                    if event.actor else None
                ),
                'created_at': event.created_at,
            }
            for event in obj.events.all()
        ]


class MerchantFulfillmentRequestCreateSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    fulfilling_merchant_id = serializers.IntegerField()
    notes = serializers.CharField(required=False, allow_blank=True)


class MerchantFulfillmentRequestActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=(
        'ACCEPT',
        'REJECT',
        'CANCEL',
        'START_PREPARATION',
        'READY_FOR_HANDOFF',
        'UNABLE_TO_FULFILL',
        'RESOLVE',
    ))
    note = serializers.CharField(required=False, allow_blank=True)


def active_relationship_between(merchant_a, merchant_b):
    return MerchantNetworkRelationship.objects.filter(
        (
            Q(from_merchant=merchant_a, to_merchant=merchant_b)
            | Q(from_merchant=merchant_b, to_merchant=merchant_a)
        ),
        status=MerchantNetworkRelationship.STATUS_ACTIVE,
    ).first()


def order_belongs_to_merchant(order, merchant):
    return order.items.filter(food__restaurant__owner=merchant.user).exists()


class MerchantFulfillmentRequestListCreateView(APIView):
    terminal_order_statuses = {'PREPARING', 'READY_FOR_PICKUP', 'ON_THE_WAY', 'DELIVERED', 'CANCELLED', 'EXPIRED'}
    active_request_statuses = (
        MerchantFulfillmentRequest.STATUS_REQUESTED,
        MerchantFulfillmentRequest.STATUS_ACCEPTED,
    )

    def get(self, request):
        actor = require_merchant_actor(request.user, VIEW_FULFILLMENT)
        merchant = actor.merchant
        requests = (
            MerchantFulfillmentRequest.objects
            .filter(Q(requesting_merchant=merchant) | Q(fulfilling_merchant=merchant))
            .select_related(
                'order',
                'requesting_merchant__user',
                'fulfilling_merchant__user',
                'relationship',
                'requested_by',
                'responded_by',
            )
            .prefetch_related('events__actor')
            .order_by('-created_at')
        )
        if not actor.is_owner and not actor.is_company_wide:
            branch_ids = permitted_branch_ids(actor)
            requests = requests.filter(
                Q(requesting_merchant=merchant, order__pickup_branch_id__in=branch_ids)
                | Q(
                    requesting_merchant=merchant,
                    order__pickup_branch__isnull=True,
                    order__items__food__restaurant_id__in=branch_ids,
                )
            ).distinct()
        context = {'merchant': merchant}
        incoming = [
            MerchantFulfillmentRequestSerializer(item, context=context).data
            for item in requests
            if item.fulfilling_merchant_id == merchant.id
        ]
        outgoing = [
            MerchantFulfillmentRequestSerializer(item, context=context).data
            for item in requests
            if item.requesting_merchant_id == merchant.id
        ]
        return Response({
            'incoming': incoming,
            'outgoing': outgoing,
            'count': len(incoming) + len(outgoing),
        })

    @transaction.atomic
    def post(self, request):
        actor = require_merchant_actor(request.user, MANAGE_FULFILLMENT)
        merchant = actor.merchant
        serializer = MerchantFulfillmentRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = Order.objects.select_for_update().filter(
            id=serializer.validated_data['order_id'],
        ).prefetch_related('items__food__restaurant').first()
        if (
            not order
            or not order_belongs_to_merchant(order, merchant)
            or not actor_can_access_order_branch(actor, order)
        ):
            return Response(
                {'order_id': ['Choose one of your own orders.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if order.status in self.terminal_order_statuses:
            return Response(
                {'order_id': ['Fulfillment help can only be requested before preparation starts.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        fulfilling_merchant = MerchantProfile.objects.filter(
            id=serializer.validated_data['fulfilling_merchant_id'],
        ).first()
        if not fulfilling_merchant or fulfilling_merchant.id == merchant.id:
            return Response(
                {'fulfilling_merchant_id': ['Choose a collaboration merchant.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        relationship = active_relationship_between(merchant, fulfilling_merchant)
        if not relationship:
            return Response(
                {'fulfilling_merchant_id': ['An active merchant collaboration is required.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if MerchantFulfillmentRequest.objects.filter(
            order=order,
            requesting_merchant=merchant,
            fulfilling_merchant=fulfilling_merchant,
            status__in=self.active_request_statuses,
        ).exists():
            return Response(
                {'detail': 'An active fulfillment request already exists for this order and merchant.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        fulfillment_request = MerchantFulfillmentRequest.objects.create(
            order=order,
            requesting_merchant=merchant,
            fulfilling_merchant=fulfilling_merchant,
            relationship=relationship,
            notes=serializer.validated_data.get('notes', ''),
            requested_by=request.user,
        )
        MerchantFulfillmentRequestEvent.objects.create(
            fulfillment_request=fulfillment_request,
            event_type=MerchantFulfillmentRequestEvent.EVENT_CREATED,
            to_status=MerchantFulfillmentRequest.STATUS_REQUESTED,
            actor=request.user,
            note='Fulfillment request created.',
            metadata={
                'customer_facing_merchant_id': merchant.id,
                'internal_fulfillment_partner_id': fulfilling_merchant.id,
                'customer_visible': False,
                'settlement_preview_only': True,
            },
        )
        return Response(
            MerchantFulfillmentRequestSerializer(
                fulfillment_request,
                context={'merchant': merchant},
            ).data,
            status=status.HTTP_201_CREATED,
        )


class MerchantFulfillmentRequestUpdateView(APIView):
    internal_actions = {
        'START_PREPARATION': {
            'from': {MerchantFulfillmentRequest.INTERNAL_STATUS_ACCEPTED},
            'to': MerchantFulfillmentRequest.INTERNAL_STATUS_IN_PROGRESS,
            'timestamp_field': 'preparation_started_at',
            'default_note': 'Internal preparation started.',
        },
        'READY_FOR_HANDOFF': {
            'from': {MerchantFulfillmentRequest.INTERNAL_STATUS_IN_PROGRESS},
            'to': MerchantFulfillmentRequest.INTERNAL_STATUS_READY_FOR_HANDOFF,
            'timestamp_field': 'ready_for_handoff_at',
            'default_note': 'Fulfillment marked ready for handoff.',
        },
        'UNABLE_TO_FULFILL': {
            'from': {MerchantFulfillmentRequest.INTERNAL_STATUS_IN_PROGRESS},
            'to': MerchantFulfillmentRequest.INTERNAL_STATUS_UNABLE_TO_FULFILL,
            'timestamp_field': None,
            'default_note': 'Fulfilling merchant reported unable to fulfill.',
        },
        'RESOLVE': {
            'from': {
                MerchantFulfillmentRequest.INTERNAL_STATUS_READY_FOR_HANDOFF,
                MerchantFulfillmentRequest.INTERNAL_STATUS_UNABLE_TO_FULFILL,
            },
            'to': MerchantFulfillmentRequest.INTERNAL_STATUS_RESOLVED,
            'timestamp_field': 'resolved_at',
            'default_note': 'Fulfillment request resolved internally.',
        },
    }
    terminal_internal_statuses = {
        MerchantFulfillmentRequest.INTERNAL_STATUS_REJECTED,
        MerchantFulfillmentRequest.INTERNAL_STATUS_CANCELLED,
        MerchantFulfillmentRequest.INTERNAL_STATUS_RESOLVED,
    }

    @transaction.atomic
    def patch(self, request, fulfillment_request_id):
        actor = require_merchant_actor(request.user, MANAGE_FULFILLMENT)
        merchant = actor.merchant
        fulfillment_request = (
            MerchantFulfillmentRequest.objects
            .select_for_update()
            .select_related(
                'order',
                'requesting_merchant__user',
                'fulfilling_merchant__user',
                'relationship',
            )
            .filter(
                Q(requesting_merchant=merchant) | Q(fulfilling_merchant=merchant),
                id=fulfillment_request_id,
            )
            .first()
        )
        if (
            fulfillment_request
            and fulfillment_request.requesting_merchant_id == merchant.id
            and not actor.is_owner
            and not actor.is_company_wide
        ):
            branch = getattr(fulfillment_request.order, 'pickup_branch', None)
            if branch and not can_access_branch(actor, branch):
                fulfillment_request = None
        if not fulfillment_request:
            return Response(
                {'detail': 'Fulfillment request not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = MerchantFulfillmentRequestActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data['action']
        note = serializer.validated_data.get('note', '').strip()
        if action in ('ACCEPT', 'REJECT'):
            if fulfillment_request.fulfilling_merchant_id != merchant.id:
                return Response(
                    {'action': ['Only the fulfilling merchant can accept or reject.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if fulfillment_request.status != MerchantFulfillmentRequest.STATUS_REQUESTED:
                return Response(
                    {'action': ['Only requested fulfillment requests can be answered.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            fulfillment_request.status = (
                MerchantFulfillmentRequest.STATUS_ACCEPTED
                if action == 'ACCEPT'
                else MerchantFulfillmentRequest.STATUS_REJECTED
            )
            fulfillment_request.internal_status = (
                MerchantFulfillmentRequest.INTERNAL_STATUS_ACCEPTED
                if action == 'ACCEPT'
                else MerchantFulfillmentRequest.INTERNAL_STATUS_REJECTED
            )
            fulfillment_request.responded_by = request.user
            fulfillment_request.responded_at = timezone.now()
            fulfillment_request.save(update_fields=[
                'status', 'internal_status', 'responded_by', 'responded_at',
                'updated_at',
            ])
            if action == 'ACCEPT':
                ensure_fulfillment_settlement_preview(
                    fulfillment_request,
                    actor=request.user,
                )
            MerchantFulfillmentRequestEvent.objects.create(
                fulfillment_request=fulfillment_request,
                event_type=MerchantFulfillmentRequestEvent.EVENT_STATUS_CHANGED,
                from_status=MerchantFulfillmentRequest.STATUS_REQUESTED,
                to_status=fulfillment_request.status,
                actor=request.user,
                note=note or f'Fulfillment request {action.lower()}ed.',
                metadata={
                    'customer_order_status_unchanged': True,
                    'payment_unchanged': True,
                    'payout_unchanged': True,
                    'dispatch_unchanged': True,
                },
            )
        elif action in self.internal_actions:
            if fulfillment_request.fulfilling_merchant_id != merchant.id:
                return Response(
                    {'action': ['Only the fulfilling merchant can perform internal fulfillment actions.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if fulfillment_request.status != MerchantFulfillmentRequest.STATUS_ACCEPTED:
                return Response(
                    {'action': ['Internal fulfillment actions require an accepted request.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            transition = self.internal_actions[action]
            previous_internal_status = fulfillment_request.internal_status
            if previous_internal_status not in transition['from']:
                expected = ', '.join(sorted(transition['from']))
                return Response(
                    {'action': [f'{action} requires internal status {expected}.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            fulfillment_request.internal_status = transition['to']
            update_fields = ['internal_status', 'updated_at']
            timestamp_field = transition['timestamp_field']
            now = timezone.now()
            if timestamp_field:
                setattr(fulfillment_request, timestamp_field, now)
                update_fields.append(timestamp_field)
            if action == 'UNABLE_TO_FULFILL' and note:
                fulfillment_request.blocked_reason = note
                update_fields.append('blocked_reason')
            if action == 'RESOLVE':
                fulfillment_request.resolved_by = request.user
                update_fields.append('resolved_by')
            fulfillment_request.save(update_fields=update_fields)
            MerchantFulfillmentRequestEvent.objects.create(
                fulfillment_request=fulfillment_request,
                event_type=(
                    MerchantFulfillmentRequestEvent.EVENT_INTERNAL_STATUS_CHANGED
                ),
                from_status=previous_internal_status,
                to_status=fulfillment_request.internal_status,
                actor=request.user,
                note=note or transition['default_note'],
                metadata={
                    'customer_order_status_unchanged': True,
                    'payment_unchanged': True,
                    'payout_unchanged': True,
                    'dispatch_unchanged': True,
                    'customer_visible': False,
                },
            )
        else:
            if fulfillment_request.requesting_merchant_id != merchant.id:
                return Response(
                    {'action': ['Only the requesting merchant can cancel.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if fulfillment_request.status not in (
                MerchantFulfillmentRequest.STATUS_REQUESTED,
                MerchantFulfillmentRequest.STATUS_ACCEPTED,
            ):
                return Response(
                    {'action': ['Only requested or accepted fulfillment requests can be cancelled.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if fulfillment_request.internal_status in self.terminal_internal_statuses:
                return Response(
                    {'action': ['Terminal fulfillment requests cannot be cancelled.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            previous_status = fulfillment_request.status
            fulfillment_request.status = MerchantFulfillmentRequest.STATUS_CANCELLED
            fulfillment_request.internal_status = (
                MerchantFulfillmentRequest.INTERNAL_STATUS_CANCELLED
            )
            fulfillment_request.responded_by = request.user
            fulfillment_request.responded_at = timezone.now()
            fulfillment_request.cancelled_by = request.user
            fulfillment_request.cancelled_at = timezone.now()
            fulfillment_request.save(update_fields=[
                'status', 'internal_status', 'responded_by', 'responded_at',
                'cancelled_by', 'cancelled_at', 'updated_at',
            ])
            MerchantFulfillmentRequestEvent.objects.create(
                fulfillment_request=fulfillment_request,
                event_type=MerchantFulfillmentRequestEvent.EVENT_STATUS_CHANGED,
                from_status=previous_status,
                to_status=MerchantFulfillmentRequest.STATUS_CANCELLED,
                actor=request.user,
                note=note or 'Fulfillment request cancelled by requesting merchant.',
                metadata={
                    'customer_order_status_unchanged': True,
                    'payment_unchanged': True,
                    'payout_unchanged': True,
                    'dispatch_unchanged': True,
                },
            )
        fulfillment_request.refresh_from_db()
        return Response(
            MerchantFulfillmentRequestSerializer(
                fulfillment_request,
                context={'merchant': merchant},
            ).data
        )


class MerchantRestaurantDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = MerchantRestaurantSerializer

    def get_queryset(self):
        permission = (
            VIEW_BRANCHES
            if self.request.method in ('GET', 'HEAD', 'OPTIONS')
            else MANAGE_BRANCHES
        )
        actor = require_merchant_actor(self.request.user, permission)
        return merchant_actor_branch_queryset(actor).select_related(
            'market', 'city_ref', 'area_ref', 'branch_manager',
        )


class MerchantOperatingHoursSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantOperatingHour
        fields = ('day_of_week', 'is_closed', 'opens_at', 'closes_at')


class MerchantOperatingHoursView(APIView):
    def get_restaurant(self, request, restaurant_id, permission):
        actor = require_merchant_actor(request.user, permission)
        return get_actor_branch_or_404(actor, restaurant_id)

    def get(self, request, restaurant_id):
        restaurant = self.get_restaurant(request, restaurant_id, VIEW_BRANCHES)
        return Response(MerchantOperatingHoursSerializer(
            restaurant.operating_hours.all(), many=True
        ).data)

    @transaction.atomic
    def put(self, request, restaurant_id):
        restaurant = self.get_restaurant(request, restaurant_id, MANAGE_BRANCHES)
        if not isinstance(request.data, list):
            return Response(
                {'detail': 'Send a list containing all seven weekdays.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = MerchantOperatingHoursSerializer(
            data=request.data, many=True
        )
        serializer.is_valid(raise_exception=True)
        days = [entry['day_of_week'] for entry in serializer.validated_data]
        if sorted(days) != list(range(7)):
            return Response(
                {'detail': 'Operating hours must contain each weekday exactly once.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        for entry in serializer.validated_data:
            RestaurantOperatingHour.objects.update_or_create(
                restaurant=restaurant,
                day_of_week=entry['day_of_week'],
                defaults={
                    'is_closed': entry.get('is_closed', False),
                    'opens_at': entry['opens_at'],
                    'closes_at': entry['closes_at'],
                },
            )
        return Response(MerchantOperatingHoursSerializer(
            restaurant.operating_hours.all(), many=True
        ).data)


class MerchantFoodItemCreateView(generics.CreateAPIView):
    serializer_class = MerchantFoodItemSerializer

    def perform_create(self, serializer):
        actor = require_merchant_actor(self.request.user, MANAGE_MENU)
        restaurant = get_actor_branch_or_404(actor, self.kwargs['restaurant_id'])
        serializer.save(restaurant=restaurant)


class MerchantFoodItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MerchantFoodItemSerializer

    def get_queryset(self):
        permission = (
            VIEW_MENU
            if self.request.method in ('GET', 'HEAD', 'OPTIONS')
            else MANAGE_MENU
        )
        actor = require_merchant_actor(self.request.user, permission)
        return FoodItem.objects.filter(
            restaurant_id=self.kwargs['restaurant_id'],
            restaurant__id__in=permitted_branch_ids(actor),
        )


class MerchantOptionSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    name = serializers.CharField(max_length=80)
    price_delta = serializers.DecimalField(
        max_digits=8, decimal_places=2, min_value=Decimal('0.00'), default=0
    )
    is_available = serializers.BooleanField(default=True)


class MerchantOptionGroupSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    name = serializers.CharField(max_length=80)
    min_select = serializers.IntegerField(min_value=0, max_value=20, default=0)
    max_select = serializers.IntegerField(min_value=1, max_value=20, default=1)
    options = MerchantOptionSerializer(many=True)

    def validate(self, attrs):
        if attrs['min_select'] > attrs['max_select']:
            raise serializers.ValidationError(
                'Minimum selections cannot exceed maximum selections.'
            )
        if attrs['min_select'] > len(attrs['options']):
            raise serializers.ValidationError(
                'Minimum selections cannot exceed the number of options.'
            )
        return attrs


class MerchantFoodOptionsView(APIView):
    def get_food(self, request, restaurant_id, item_id, permission):
        actor = require_merchant_actor(request.user, permission)
        return get_object_or_404(
            FoodItem,
            id=item_id,
            restaurant_id=restaurant_id,
            restaurant__id__in=permitted_branch_ids(actor),
        )

    @transaction.atomic
    def put(self, request, restaurant_id, item_id):
        food = self.get_food(request, restaurant_id, item_id, MANAGE_MENU)
        if not isinstance(request.data, list):
            return Response(
                {'detail': 'Send a list of option groups.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = MerchantOptionGroupSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        existing_groups = {
            group.id: group for group in food.option_groups.prefetch_related('options')
        }
        kept_group_ids = set()

        for group_order, group_data in enumerate(serializer.validated_data):
            group_id = group_data.get('id')
            if group_id:
                group = existing_groups.get(group_id)
                if not group:
                    raise serializers.ValidationError(
                        {'id': 'An option group does not belong to this item.'}
                    )
                group.name = group_data['name']
                group.min_select = group_data['min_select']
                group.max_select = group_data['max_select']
                group.ordering = group_order
                group.save()
            else:
                group = FoodOptionGroup.objects.create(
                    food=food,
                    name=group_data['name'],
                    min_select=group_data['min_select'],
                    max_select=group_data['max_select'],
                    ordering=group_order,
                )
            kept_group_ids.add(group.id)
            existing_options = {option.id: option for option in group.options.all()}
            kept_option_ids = set()

            for option_order, option_data in enumerate(group_data['options']):
                option_id = option_data.get('id')
                if option_id:
                    option = existing_options.get(option_id)
                    if not option:
                        raise serializers.ValidationError(
                            {'id': 'An option does not belong to this group.'}
                        )
                    option.name = option_data['name']
                    option.price_delta = option_data['price_delta']
                    option.is_available = option_data['is_available']
                    option.ordering = option_order
                    option.save()
                else:
                    option = FoodOption.objects.create(
                        group=group,
                        name=option_data['name'],
                        price_delta=option_data['price_delta'],
                        is_available=option_data['is_available'],
                        ordering=option_order,
                    )
                kept_option_ids.add(option.id)
            group.options.exclude(id__in=kept_option_ids).delete()

        food.option_groups.exclude(id__in=kept_group_ids).delete()
        groups = food.option_groups.prefetch_related('options')
        return Response({
            'option_groups': [
                {
                    'id': group.id,
                    'name': group.name,
                    'min_select': group.min_select,
                    'max_select': group.max_select,
                    'ordering': group.ordering,
                    'options': [
                        {
                            'id': option.id,
                            'name': option.name,
                            'price_delta': option.price_delta,
                            'is_available': option.is_available,
                            'ordering': option.ordering,
                        }
                        for option in group.options.all()
                    ],
                }
                for group in groups
            ],
        })


class MerchantOrderListView(generics.ListAPIView):
    serializer_class = MerchantOrderSerializer

    def get_queryset(self):
        actor = require_merchant_actor(self.request.user, VIEW_ORDERS)
        return (
            merchant_actor_order_queryset(actor, payment_statuses=('SUCCESS', 'PENDING'))
            .select_related('customer', 'payment', 'pickup_branch', 'delivery__delivery_partner')
            .prefetch_related('items__food')
            .distinct()
            .order_by('-created_at')
        )


class MerchantReviewListView(generics.ListAPIView):
    serializer_class = MerchantReviewSerializer

    def get_queryset(self):
        actor = require_merchant_actor(self.request.user, VIEW_ORDERS)
        return (
            RestaurantReview.objects.filter(
                restaurant__id__in=permitted_branch_ids(actor),
            )
            .select_related('customer', 'restaurant', 'order')
            .prefetch_related('photos')
            .order_by('-created_at')
        )


class MerchantOrderStatusView(APIView):
    transitions = {
        'CONFIRMED': 'PREPARING',
        'PREPARING': 'READY_FOR_PICKUP',
    }

    @transaction.atomic
    def patch(self, request, order_id):
        actor = require_merchant_actor(request.user, UPDATE_ORDER_STATUS)
        order = (
            Order.objects.select_for_update()
            .filter(
                id=order_id,
                items__food__restaurant__id__in=permitted_branch_ids(actor),
                payment__status__in=('SUCCESS', 'PENDING'),
            )
            .first()
        )
        if not order:
            return Response(
                {'detail': 'Order not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        next_status = self.transitions.get(order.status)
        requested_status = request.data.get('status')
        if requested_status == 'CANCELLED' and order.status == 'CONFIRMED':
            if actor.role not in (
                MerchantStaffMember.ROLE_OWNER,
                MerchantStaffMember.ROLE_ADMIN,
                MerchantStaffMember.ROLE_BRANCH_MANAGER,
            ):
                raise PermissionDenied(
                    'Only merchant owners, admins, or branch managers can cancel orders.'
                )
            order.status = 'CANCELLED'
            order.merchant_payout_status = 'CANCELLED'
            order.save(update_fields=[
                'status', 'merchant_payout_status', 'updated_at'
            ])
            if hasattr(order, 'payment') and order.payment.status == 'SUCCESS':
                order.payment.status = 'REFUNDED'
                order.payment.save(update_fields=['status'])
                notify_payment_event(order.payment, 'refund_completed', actor=request.user)
            elif hasattr(order, 'payment') and order.payment.status == 'PENDING':
                order.payment.status = 'CANCELLED'
                order.payment.save(update_fields=['status'])
            notify_order_event(
                order,
                'cancelled',
                actor=request.user,
                message='The merchant could not accept this order.',
            )
            order = Order.objects.select_related('customer').prefetch_related(
                'items__food'
            ).get(id=order.id)
            return Response(MerchantOrderSerializer(order).data)

        if requested_status != next_status:
            return Response(
                {'status': [f'Next status must be {next_status or "none"}.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        order.status = requested_status
        order.save(update_fields=['status', 'updated_at'])
        if requested_status == 'PREPARING':
            notify_order_event(order, 'accepted', actor=request.user)
            notify_order_event(order, 'preparing', actor=request.user)
        if requested_status == 'READY_FOR_PICKUP':
            auto_assign_delivery(order)
            notify_order_event(order, 'ready_for_pickup', actor=request.user)

        order = Order.objects.select_related('customer').prefetch_related(
            'items__food'
        ).get(id=order.id)
        return Response(MerchantOrderSerializer(order).data)


class MerchantSummaryView(APIView):
    def get(self, request):
        actor = require_merchant_actor(request.user, VIEW_ANALYTICS)
        orders = merchant_actor_order_queryset(actor)
        delivered = orders.filter(
            status='DELIVERED',
            payment__status='SUCCESS',
        )
        return Response({
            'total_orders': orders.count(),
            'open_orders': orders.exclude(
                status__in=('DELIVERED', 'CANCELLED')
            ).count(),
            'cancelled_orders': orders.filter(status='CANCELLED').count(),
            'gross_sales': delivered.aggregate(
                total=Sum('total_amount')
            )['total'] or 0,
            'merchant_earnings': delivered.aggregate(
                total=Sum('merchant_payout')
            )['total'] or 0,
            'platform_fees': delivered.aggregate(
                total=Sum('platform_fee')
            )['total'] or 0,
            'available_payout': orders.filter(
                merchant_payout_status='AVAILABLE'
            ).aggregate(total=Sum('merchant_payout'))['total'] or 0,
            'paid_payout': orders.filter(
                merchant_payout_status='PAID'
            ).aggregate(total=Sum('merchant_payout'))['total'] or 0,
        })


class MerchantAnalyticsView(APIView):
    allowed_ranges = {'today', 'yesterday', '7d', '30d', 'month', 'year'}

    def get(self, request):
        actor = require_merchant_actor(request.user, VIEW_ANALYTICS)
        range_key = request.query_params.get('range', '7d')
        if range_key not in self.allowed_ranges:
            return Response(
                {'range': ['Choose one of: today, yesterday, 7d, 30d, month, year.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        branch_id = request.query_params.get('branch_id') or request.query_params.get('branch')
        branch = None
        if branch_id not in (None, ''):
            branch = Restaurant.objects.filter(
                id=branch_id,
                owner=actor.merchant.user,
            ).first()
            if not branch or not can_access_branch(actor, branch):
                return Response(
                    {'branch_id': ['Choose a branch owned by this merchant.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif not actor.is_owner and not actor.is_company_wide:
            assigned_branch_ids = permitted_branch_ids(actor)
            if len(assigned_branch_ids) == 1:
                branch = Restaurant.objects.filter(id=assigned_branch_ids[0]).first()

        cached = get_cached_response_data(
            'merchant:analytics',
            request.user,
            request.query_params,
            extra={
                'merchant_id': actor.merchant_id,
                'role': actor.role,
                'branch_id': branch.id if branch else '',
                'company_wide': actor.is_company_wide,
                'branch_ids': permitted_branch_ids(actor),
            },
        )
        if cached is not None:
            return Response(cached)

        now = timezone.localtime()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start = analytics_start(range_key)
        end = today if range_key == 'yesterday' else None
        base_orders = (
            merchant_branch_order_queryset(actor.merchant.user, branch)
            if branch else merchant_actor_order_queryset(actor)
        )
        orders = base_orders.filter(created_at__gte=start)
        if end:
            orders = orders.filter(created_at__lt=end)
        delivered = orders.filter(status='DELIVERED', payment__status='SUCCESS')
        delivered_ids = list(delivered.values_list('id', flat=True))
        delivered_orders = Order.objects.filter(id__in=delivered_ids)
        gross_sales = delivered_orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        merchant_earnings = delivered_orders.aggregate(total=Sum('merchant_payout'))['total'] or Decimal('0.00')
        delivered_count = delivered_orders.count()
        cancelled_count = orders.filter(status='CANCELLED').count()
        completed_or_cancelled = delivered_count + cancelled_count
        cancellation_rate = (
            round((cancelled_count / completed_or_cancelled) * 100, 2)
            if completed_or_cancelled else 0
        )
        average_order_value = (
            (gross_sales / delivered_count).quantize(Decimal('0.01'))
            if delivered_count else Decimal('0.00')
        )

        order_volume = list(
            delivered_orders.annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(
                orders=Count('id', distinct=True),
                gross_sales=Sum('total_amount'),
            )
            .order_by('day')
        )
        for row in order_volume:
            row['date'] = row.pop('day').isoformat()
            row['gross_sales'] = row['gross_sales'] or Decimal('0.00')
        cancelled_volume = list(
            orders.filter(status='CANCELLED')
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(cancelled_orders=Count('id', distinct=True))
            .order_by('day')
        )
        for row in cancelled_volume:
            row['date'] = row.pop('day').isoformat()

        item_sales = OrderItem.objects.filter(
            order_id__in=delivered_ids,
        )
        item_sales = (
            item_sales.filter(food__restaurant=branch)
            if branch else item_sales.filter(food__restaurant__id__in=permitted_branch_ids(actor))
        )
        sold_by_item = {}
        for line in item_sales.select_related('food'):
            item = sold_by_item.setdefault(line.food_id, {
                'food_id': line.food_id,
                'food__food_name': line.food.food_name,
                'quantity': 0,
                'gross_sales': Decimal('0.00'),
            })
            item['quantity'] += line.quantity
            item['gross_sales'] += line.price * line.quantity
        sold_items = sorted(
            sold_by_item.values(),
            key=lambda row: (-row['quantity'], row['food__food_name']),
        )
        top_items = [
            {
                'item_id': row['food_id'],
                'name': row['food__food_name'],
                'quantity': row['quantity'] or 0,
                'gross_sales': row['gross_sales'] or Decimal('0.00'),
            }
            for row in sold_items[:5]
        ]
        sold_by_item = {
            row['food_id']: {
                'quantity': row['quantity'] or 0,
                'gross_sales': row['gross_sales'] or Decimal('0.00'),
            }
            for row in sold_items
        }
        low_items = []
        menu_items = (
            FoodItem.objects.filter(restaurant=branch)
            if branch else FoodItem.objects.filter(restaurant__id__in=permitted_branch_ids(actor))
        )
        for item in menu_items.order_by('food_name'):
            sold = sold_by_item.get(item.id, {
                'quantity': 0,
                'gross_sales': Decimal('0.00'),
            })
            low_items.append({
                'item_id': item.id,
                'name': item.food_name,
                'quantity': sold['quantity'],
                'gross_sales': sold['gross_sales'],
            })
        low_items = sorted(low_items, key=lambda row: (row['quantity'], row['name']))[:5]

        prep_orders = list(orders.prefetch_related('status_events'))
        accept_minutes = [
            prep_metric_minutes(order, 'CONFIRMED', 'PREPARING')
            for order in prep_orders
        ]
        ready_minutes_list = [
            prep_metric_minutes(order, 'PREPARING', 'READY_FOR_PICKUP')
            for order in prep_orders
        ]
        restaurants = (
            Restaurant.objects.filter(id=branch.id)
            if branch else merchant_actor_branch_queryset(actor)
        )
        estimated_total = restaurants.aggregate(
            total=Sum('estimated_prep_minutes')
        )['total']
        restaurant_count = restaurants.count()
        estimated_prep_minutes = (
            round(estimated_total / restaurant_count, 1)
            if estimated_total is not None and restaurant_count else None
        )
        reviews = (
            RestaurantReview.objects.filter(restaurant=branch)
            if branch else RestaurantReview.objects.filter(
                restaurant__id__in=permitted_branch_ids(actor)
            )
        )
        ratings = reviews.aggregate(
            rating_total=Sum('rating'),
            review_count=Count('id'),
        )
        average_rating = (
            round(ratings['rating_total'] / ratings['review_count'], 2)
            if ratings['review_count'] else None
        )
        rating_distribution = []
        review_counts = {
            row['rating']: row['count']
            for row in reviews.values('rating').annotate(count=Count('id'))
        }
        for rating in range(1, 6):
            rating_distribution.append({
                'rating': rating,
                'count': review_counts.get(rating, 0),
            })

        revenue_periods = [
            ('today', 'Today', today, None),
            ('yesterday', 'Yesterday', today - timedelta(days=1), today),
            ('last_7_days', 'Last 7 days', today - timedelta(days=6), None),
            ('last_30_days', 'Last 30 days', today - timedelta(days=29), None),
            ('current_month', 'Current month', today.replace(day=1), None),
            ('current_year', 'Current year', today.replace(month=1, day=1), None),
        ]
        revenue_trends = [
            {
                'key': key,
                'label': label,
                **period_stats(base_orders, period_start, period_end),
            }
            for key, label, period_start, period_end in revenue_periods
        ]

        this_week_start = today - timedelta(days=today.weekday())
        last_week_start = this_week_start - timedelta(days=7)
        this_month_start = today.replace(day=1)
        last_month_end = this_month_start
        last_month_start = (
            this_month_start - timedelta(days=1)
        ).replace(day=1)
        this_week = period_stats(base_orders, this_week_start)
        last_week = period_stats(base_orders, last_week_start, this_week_start)
        this_month = period_stats(base_orders, this_month_start)
        last_month = period_stats(base_orders, last_month_start, last_month_end)

        best_day = None
        worst_day = None
        if order_volume:
            best_day = max(order_volume, key=lambda row: row['gross_sales'])
            worst_day = min(order_volume, key=lambda row: row['gross_sales'])
        prep_durations = []
        for order in prep_orders:
            order_ready_minutes = prep_metric_minutes(order, 'PREPARING', 'READY_FOR_PICKUP')
            if order_ready_minutes is not None:
                prep_durations.append({
                    'order_id': order.id,
                    'minutes': round(order_ready_minutes, 1),
                })
        fastest_prep = min(prep_durations, key=lambda row: row['minutes']) if prep_durations else None
        slowest_prep = max(prep_durations, key=lambda row: row['minutes']) if prep_durations else None
        most_profitable_item = (
            max(top_items, key=lambda row: row['gross_sales']) if top_items else None
        )
        lowest_performing_item = low_items[0] if low_items else None
        repeat_customers = (
            delivered_orders.values('customer')
            .annotate(order_count=Count('id'))
            .filter(order_count__gt=1)
            .count()
        )
        rider_queryset = MerchantRider.objects.filter(merchant=actor.merchant)
        if branch:
            rider_queryset = rider_queryset.filter(home_restaurant=branch)
        elif not actor.is_owner and not actor.is_company_wide:
            rider_queryset = rider_queryset.filter(
                home_restaurant_id__in=permitted_branch_ids(actor)
            )
        total_riders = rider_queryset.count()
        active_riders = rider_queryset.filter(
            status=MerchantRider.STATUS_ACTIVE,
            partner__is_available=True,
            partner__is_verified=True,
        ).count()
        branch_payload = None
        if branch:
            branch_payload = {
                'id': branch.id,
                'name': branch.branch_name or branch.rest_name,
                'rest_name': branch.rest_name,
                'branch_type': branch.branch_type,
                'is_open': branch.is_open,
                'is_active': branch.is_active,
                'city': branch.city_ref.name if branch.city_ref_id else branch.rest_city,
                'area': branch.area_ref.name if branch.area_ref_id else '',
            }

        data = {
            'range': range_key,
            'scope': 'branch' if branch else 'company',
            'branch': branch_payload,
            'kpis': {
                'gross_sales': gross_sales,
                'net_earnings': merchant_earnings,
                'average_order_value': average_order_value,
                'delivered_orders': delivered_count,
                'cancellation_rate': cancellation_rate,
                'average_prep_time': average_minutes(ready_minutes_list),
                'average_acceptance_time': average_minutes(accept_minutes),
                'average_rating': average_rating,
                'delivery_count': delivered_count,
                'repeat_customers': repeat_customers,
                'rider_count': total_riders,
                'active_riders': active_riders,
            },
            'sales': {
                'gross_sales': gross_sales,
                'merchant_earnings': merchant_earnings,
                'average_order_value': average_order_value,
                'delivered_orders': delivered_count,
                'delivery_count': delivered_count,
                'cancelled_orders': cancelled_count,
                'cancellation_rate': cancellation_rate,
                'repeat_customers': repeat_customers,
            },
            'revenue_trends': revenue_trends,
            'order_volume': order_volume,
            'top_items': top_items,
            'low_items': low_items,
            'charts': {
                'revenue_line': order_volume,
                'order_volume': order_volume,
                'top_items': top_items,
                'cancellations': cancelled_volume,
                'rating_distribution': rating_distribution,
            },
            'prep': {
                'estimated_prep_minutes': estimated_prep_minutes,
                'average_accept_minutes': average_minutes(accept_minutes),
                'average_ready_minutes': average_minutes(ready_minutes_list),
            },
            'ratings': {
                'average_rating': average_rating,
                'review_count': ratings['review_count'],
                'distribution': rating_distribution,
            },
            'branch_status': {
                'is_open': branch.is_open if branch else None,
                'is_active': branch.is_active if branch else None,
                'rider_count': total_riders,
                'active_riders': active_riders,
            },
            'performance': {
                'best_day': best_day,
                'worst_day': worst_day,
                'fastest_prep_time': fastest_prep,
                'slowest_prep_time': slowest_prep,
                'most_profitable_item': most_profitable_item,
                'lowest_performing_item': lowest_performing_item,
            },
            'comparison': {
                'this_week_vs_last_week': {
                    'current': this_week,
                    'previous': last_week,
                    'gross_sales_change_percent': percent_change(
                        this_week['gross_sales'],
                        last_week['gross_sales'],
                    ),
                    'orders_change_percent': percent_change(
                        this_week['delivered_orders'],
                        last_week['delivered_orders'],
                    ),
                },
                'this_month_vs_last_month': {
                    'current': this_month,
                    'previous': last_month,
                    'gross_sales_change_percent': percent_change(
                        this_month['gross_sales'],
                        last_month['gross_sales'],
                    ),
                    'orders_change_percent': percent_change(
                        this_month['delivered_orders'],
                        last_month['delivered_orders'],
                    ),
                },
            },
        }
        set_cached_response_data(
            'merchant:analytics',
            data,
            timeout=60,
            actor_or_user=request.user,
            params=request.query_params,
            extra={
                'merchant_id': actor.merchant_id,
                'role': actor.role,
                'branch_id': branch.id if branch else '',
                'company_wide': actor.is_company_wide,
                'branch_ids': permitted_branch_ids(actor),
            },
        )
        return Response(data)


class MerchantPayoutListView(APIView):
    allowed_statuses = {'PENDING', 'AVAILABLE', 'PAID', 'CANCELLED'}

    def get(self, request):
        actor = require_merchant_actor(request.user, VIEW_FINANCE)
        requested_status = request.query_params.get('status')
        if requested_status and requested_status not in self.allowed_statuses:
            return Response(
                {'status': ['Choose one of: PENDING, AVAILABLE, PAID, CANCELLED.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        orders = merchant_actor_order_queryset(actor).select_related(
            'customer', 'payment'
        ).order_by('-created_at')
        if requested_status:
            orders = orders.filter(merchant_payout_status=requested_status)

        totals_source = merchant_actor_order_queryset(actor)
        totals = {
            payout_status: (
                totals_source.filter(
                    merchant_payout_status=payout_status
                ).aggregate(total=Sum('merchant_payout'))['total'] or Decimal('0.00')
            )
            for payout_status in self.allowed_statuses
        }
        totals['total'] = (
            totals_source.aggregate(total=Sum('merchant_payout'))['total']
            or Decimal('0.00')
        )

        return Response({
            'status': requested_status,
            'totals': totals,
            'count': orders.count(),
            'results': MerchantPayoutSerializer(orders, many=True).data,
        })


class MerchantNotificationListView(APIView):
    def get(self, request):
        require_merchant_actor(request.user, VIEW_SUPPORT)
        try:
            limit = min(max(int(request.query_params.get('limit', 10)), 1), 50)
        except (TypeError, ValueError):
            return Response(
                {'limit': ['Limit must be a number from 1 to 50.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        notifications = Notification.objects.filter(user=request.user)
        return Response({
            'unread_count': notifications.filter(is_read=False).count(),
            'results': MerchantNotificationSerializer(
                notifications.order_by('-created_at')[:limit],
                many=True,
            ).data,
        })

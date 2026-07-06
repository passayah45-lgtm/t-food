from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models, transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .notification_views import NotificationSerializer, parse_bound, sanitize_metadata, truthy
from customers.models import Customer
from delivery.models import Delivery, DeliveryPartner, MerchantRider
from fooddelivery.dashboard_cache import (
    get_cached_response_data,
    set_cached_response_data,
)
from ledger.models import LedgerTransaction
from markets.models import Market
from merchant_staff.models import MerchantStaffMember
from notifications.models import Notification
from notifications.events import (
    notify_branch_event,
    notify_order_event,
    notify_payment_event,
    notify_payout_event,
)
from orders.models import Offer, Order, SupportTicket
from payments.models import (
    MerchantPayoutAudit,
    PartnerPayoutAudit,
    Payment,
    PaymentProviderConfig,
    RefundAudit,
)
from payments.providers.resolver import (
    PROVIDER_REGISTRY,
    SUPPORTED_PAYMENT_METHODS,
    available_provider_capabilities,
)
from payments.services import (
    record_merchant_payout_audit,
    record_partner_payout_audit,
    record_refund_audit,
)
from operations_access.permissions import (
    MANAGE_BRANCHES,
    MANAGE_PROVIDER_CONFIG,
    MANAGE_DISPATCH,
    MANAGE_SUPPORT,
    MANAGE_VERIFICATIONS,
    VIEW_BRANCHES,
    VIEW_CUSTOMERS,
    VIEW_DISPATCH,
    VIEW_FINANCE,
    VIEW_GLOBAL_DASHBOARD,
    VIEW_LEDGER,
    VIEW_MERCHANTS,
    VIEW_ORDERS,
    VIEW_RIDERS,
    VIEW_SUPPORT,
    VIEW_VERIFICATIONS,
    can_access_area,
    can_access_city,
    can_access_country,
    can_access_market,
    filter_queryset_for_operations_actor,
    get_operations_actor,
    require_operations_permission,
)
from restaurants.models import (
    MerchantFulfillmentRequest,
    MerchantFulfillmentRequestEvent,
    MerchantProfile,
    Restaurant,
    ReviewPhoto,
)
from restaurants.notification_events import schedule_review_photo_moderation_notification
from restaurants.services import restaurant_accepting_orders
from restaurants.services import (
    SETTLEMENT_PREVIEW_LABEL,
    ensure_fulfillment_settlement_preview,
    restaurant_accepting_orders,
)
from verifications.services import (
    approve_merchant,
    approve_partner,
    merchant_document_summary,
    merchant_missing_requirements,
    partner_document_summary,
    partner_missing_requirements,
    reject_merchant,
    reject_partner,
)

RANGE_TODAY = 'today'
RANGE_YESTERDAY = 'yesterday'
RANGE_LAST_7_DAYS = 'last_7_days'
RANGE_LAST_30_DAYS = 'last_30_days'
RANGE_THIS_MONTH = 'this_month'
RANGE_THIS_YEAR = 'this_year'
SUPPORTED_OPERATION_RANGES = {
    RANGE_TODAY,
    RANGE_YESTERDAY,
    RANGE_LAST_7_DAYS,
    RANGE_LAST_30_DAYS,
    RANGE_THIS_MONTH,
    RANGE_THIS_YEAR,
}


BRANCH_SCOPE_FIELD_MAP = {
    'market': 'market',
    'country': 'country_code',
    'city': 'city_ref',
    'area': 'area_ref',
}


PAYMENT_PROVIDER_SCOPE_FIELD_MAP = {
    'market': 'market',
    'country': 'country_code',
}


def scoped_branch_queryset(actor):
    return filter_queryset_for_operations_actor(
        Restaurant.objects.all(),
        actor,
        BRANCH_SCOPE_FIELD_MAP,
    )


def branch_scope_q(actor, prefix=''):
    if actor.is_global_scope:
        return models.Q()
    if actor.assigned_area_ids:
        return models.Q(**{f'{prefix}area_ref_id__in': actor.assigned_area_ids})
    if actor.assigned_city_ids:
        return models.Q(**{f'{prefix}city_ref_id__in': actor.assigned_city_ids})
    q = models.Q()
    if actor.assigned_market_ids:
        q |= models.Q(**{f'{prefix}market_id__in': actor.assigned_market_ids})
    if actor.assigned_country_codes:
        q |= models.Q(**{f'{prefix}country_code__in': actor.assigned_country_codes})
    return q if q else models.Q(pk__in=[])


def order_scope_q(actor, prefix=''):
    if actor.is_global_scope:
        return models.Q()
    q = models.Q()
    if actor.assigned_area_ids:
        q |= models.Q(**{f'{prefix}pickup_branch__area_ref_id__in': actor.assigned_area_ids})
        q |= models.Q(**{f'{prefix}items__food__restaurant__area_ref_id__in': actor.assigned_area_ids})
    elif actor.assigned_city_ids:
        q |= models.Q(**{f'{prefix}pickup_branch__city_ref_id__in': actor.assigned_city_ids})
        q |= models.Q(**{f'{prefix}items__food__restaurant__city_ref_id__in': actor.assigned_city_ids})
    else:
        if actor.assigned_market_ids:
            q |= models.Q(**{f'{prefix}market_id__in': actor.assigned_market_ids})
            q |= models.Q(**{f'{prefix}pickup_branch__market_id__in': actor.assigned_market_ids})
            q |= models.Q(**{f'{prefix}items__food__restaurant__market_id__in': actor.assigned_market_ids})
        if actor.assigned_country_codes:
            q |= models.Q(**{f'{prefix}pickup_branch__country_code__in': actor.assigned_country_codes})
            q |= models.Q(**{f'{prefix}items__food__restaurant__country_code__in': actor.assigned_country_codes})
    return q if q else models.Q(pk__in=[])


def scoped_order_queryset(queryset, actor):
    if actor.is_global_scope:
        return queryset
    return queryset.filter(order_scope_q(actor)).distinct()


def scoped_delivery_queryset(queryset, actor):
    if actor.is_global_scope:
        return queryset
    return queryset.filter(order_scope_q(actor, prefix='order__')).distinct()


def scoped_customer_queryset(queryset, actor):
    if actor.is_global_scope:
        return queryset
    q = models.Q()
    if actor.assigned_area_ids:
        q |= models.Q(user__orders__pickup_branch__area_ref_id__in=actor.assigned_area_ids)
        q |= models.Q(user__orders__items__food__restaurant__area_ref_id__in=actor.assigned_area_ids)
    elif actor.assigned_city_ids:
        q |= models.Q(user__orders__pickup_branch__city_ref_id__in=actor.assigned_city_ids)
        q |= models.Q(user__orders__items__food__restaurant__city_ref_id__in=actor.assigned_city_ids)
    else:
        if actor.assigned_market_ids:
            q |= models.Q(market_id__in=actor.assigned_market_ids)
            q |= models.Q(user__delivery_addresses__market_id__in=actor.assigned_market_ids)
            q |= models.Q(user__orders__market_id__in=actor.assigned_market_ids)
            q |= models.Q(user__orders__pickup_branch__market_id__in=actor.assigned_market_ids)
            q |= models.Q(user__orders__items__food__restaurant__market_id__in=actor.assigned_market_ids)
        if actor.assigned_country_codes:
            q |= models.Q(market__country_code__in=actor.assigned_country_codes)
            q |= models.Q(user__delivery_addresses__market__country_code__in=actor.assigned_country_codes)
            q |= models.Q(user__orders__pickup_branch__country_code__in=actor.assigned_country_codes)
            q |= models.Q(user__orders__items__food__restaurant__country_code__in=actor.assigned_country_codes)
    return queryset.filter(q).distinct() if q else queryset.none()


def merchant_scope_q(actor):
    if actor.is_global_scope:
        return models.Q()
    scoped_owner_ids = scoped_branch_queryset(actor).values_list('owner_id', flat=True)
    q = models.Q(user_id__in=scoped_owner_ids)
    if not actor.assigned_city_ids and not actor.assigned_area_ids:
        if actor.assigned_market_ids:
            q |= models.Q(market_id__in=actor.assigned_market_ids)
        if actor.assigned_country_codes:
            q |= models.Q(market__country_code__in=actor.assigned_country_codes)
    return q


def scoped_merchant_queryset(queryset, actor):
    if actor.is_global_scope:
        return queryset
    return queryset.filter(merchant_scope_q(actor)).distinct()


def scoped_partner_queryset(queryset, actor):
    if actor.is_global_scope:
        return queryset
    q = models.Q(deliveries__in=scoped_delivery_queryset(Delivery.objects.all(), actor))
    if actor.assigned_market_ids:
        q |= models.Q(market_id__in=actor.assigned_market_ids)
    if actor.assigned_country_codes:
        q |= models.Q(market__country_code__in=actor.assigned_country_codes)
    q |= models.Q(merchant_rider_link__home_restaurant__in=scoped_branch_queryset(actor))
    return queryset.filter(q).distinct()


def scoped_staff_queryset(queryset, actor):
    if actor.is_global_scope:
        return queryset
    q = models.Q(merchant__in=scoped_merchant_queryset(MerchantProfile.objects.all(), actor))
    q |= models.Q(branch_access__branch__in=scoped_branch_queryset(actor))
    return queryset.filter(q).distinct()


def scoped_review_photo_queryset(queryset, actor):
    if actor.is_global_scope:
        return queryset
    branch_queryset = scoped_branch_queryset(actor)
    return queryset.filter(review__restaurant__in=branch_queryset).distinct()


def scoped_ledger_queryset(queryset, actor):
    if actor.is_global_scope:
        return queryset
    if actor.assigned_area_ids or actor.assigned_city_ids:
        scoped_orders = scoped_order_queryset(Order.objects.all(), actor)
        scoped_deliveries = scoped_delivery_queryset(Delivery.objects.all(), actor)
        scoped_fulfillment = MerchantFulfillmentRequest.objects.filter(
            order__in=scoped_orders
        )
        return queryset.filter(
            models.Q(order__in=scoped_orders)
            | models.Q(delivery__in=scoped_deliveries)
            | models.Q(payment__order__in=scoped_orders)
            | models.Q(fulfillment_request__in=scoped_fulfillment)
        ).distinct()
    return filter_queryset_for_operations_actor(
        queryset,
        actor,
        {'market': 'market', 'country': 'country_code'},
    )


def get_range_bounds(range_key):
    if range_key not in SUPPORTED_OPERATION_RANGES:
        return None
    today = timezone.localdate()
    if range_key == RANGE_TODAY:
        start = today
        end = today + timedelta(days=1)
    elif range_key == RANGE_YESTERDAY:
        start = today - timedelta(days=1)
        end = today
    elif range_key == RANGE_LAST_7_DAYS:
        start = today - timedelta(days=6)
        end = today + timedelta(days=1)
    elif range_key == RANGE_LAST_30_DAYS:
        start = today - timedelta(days=29)
        end = today + timedelta(days=1)
    elif range_key == RANGE_THIS_MONTH:
        start = today.replace(day=1)
        end = today + timedelta(days=1)
    else:
        start = today.replace(month=1, day=1)
        end = today + timedelta(days=1)
    return (
        timezone.make_aware(datetime.combine(start, datetime.min.time())),
        timezone.make_aware(datetime.combine(end, datetime.min.time())),
    )


def apply_range_filter(queryset, request, field_name):
    bounds = get_range_bounds(request.query_params.get('range'))
    if not bounds:
        return queryset
    start, end = bounds
    return queryset.filter(**{
        f'{field_name}__gte': start,
        f'{field_name}__lt': end,
    })


def _has_request_scope(request):
    return any(
        request.query_params.get(name)
        for name in ('market', 'country_code', 'city', 'area')
    )


def _market_q(value, field_name):
    if not value:
        return models.Q()
    if str(value).isdigit():
        return models.Q(**{f'{field_name}_id': value})
    return models.Q(**{f'{field_name}__slug__iexact': value})


def _city_q(value, relation_prefix=''):
    if not value:
        return models.Q()
    if str(value).isdigit():
        return models.Q(**{f'{relation_prefix}city_ref_id': value})
    return (
        models.Q(**{f'{relation_prefix}rest_city__icontains': value})
        | models.Q(**{f'{relation_prefix}city_ref__name__icontains': value})
        | models.Q(**{f'{relation_prefix}city_ref__slug__iexact': value})
    )


def _area_q(value, relation_prefix=''):
    if not value:
        return models.Q()
    if str(value).isdigit():
        return models.Q(**{f'{relation_prefix}area_ref_id': value})
    return (
        models.Q(**{f'{relation_prefix}area_ref__name__icontains': value})
        | models.Q(**{f'{relation_prefix}area_ref__slug__iexact': value})
    )


def request_branch_scope_q(request, relation_prefix=''):
    q = models.Q()
    market = request.query_params.get('market')
    country_code = request.query_params.get('country_code')
    city = request.query_params.get('city')
    area = request.query_params.get('area')
    if market:
        q &= _market_q(market, f'{relation_prefix}market')
    if country_code:
        q &= models.Q(**{f'{relation_prefix}country_code__iexact': country_code})
    if city:
        q &= _city_q(city, relation_prefix)
    if area:
        q &= _area_q(area, relation_prefix)
    return q


def request_order_scope_q(request, prefix=''):
    if not _has_request_scope(request):
        return models.Q()
    q = models.Q()
    market = request.query_params.get('market')
    country_code = request.query_params.get('country_code')
    city = request.query_params.get('city')
    area = request.query_params.get('area')
    if market:
        market_q = _market_q(market, f'{prefix}market')
        market_q |= _market_q(market, f'{prefix}pickup_branch__market')
        market_q |= _market_q(market, f'{prefix}items__food__restaurant__market')
        q &= market_q
    if country_code:
        q &= (
            models.Q(**{f'{prefix}pickup_branch__country_code__iexact': country_code})
            | models.Q(**{f'{prefix}items__food__restaurant__country_code__iexact': country_code})
        )
    if city:
        q &= (
            _city_q(city, f'{prefix}pickup_branch__')
            | _city_q(city, f'{prefix}items__food__restaurant__')
        )
    if area:
        q &= (
            _area_q(area, f'{prefix}pickup_branch__')
            | _area_q(area, f'{prefix}items__food__restaurant__')
        )
    return q


def apply_request_scope_filter(queryset, request, scope_type):
    if not _has_request_scope(request):
        return queryset
    if scope_type == 'branch':
        return queryset.filter(request_branch_scope_q(request)).distinct()
    if scope_type == 'order':
        return queryset.filter(request_order_scope_q(request)).distinct()
    if scope_type == 'delivery':
        return queryset.filter(request_order_scope_q(request, prefix='order__')).distinct()
    if scope_type == 'customer':
        order_q = request_order_scope_q(request, prefix='user__orders__')
        q = order_q
        market = request.query_params.get('market')
        country_code = request.query_params.get('country_code')
        if market:
            q |= _market_q(market, 'market')
            q |= _market_q(market, 'user__delivery_addresses__market')
        if country_code:
            q |= models.Q(market__country_code__iexact=country_code)
            q |= models.Q(user__delivery_addresses__market__country_code__iexact=country_code)
        return queryset.filter(q).distinct() if q else queryset.none()
    if scope_type == 'merchant':
        branch_q = request_branch_scope_q(request, relation_prefix='user__owned_restaurants__')
        q = branch_q
        market = request.query_params.get('market')
        country_code = request.query_params.get('country_code')
        if market:
            q |= _market_q(market, 'market')
        if country_code:
            q |= models.Q(market__country_code__iexact=country_code)
        return queryset.filter(q).distinct() if q else queryset.none()
    if scope_type == 'partner':
        q = request_order_scope_q(request, prefix='deliveries__order__')
        q |= request_branch_scope_q(request, relation_prefix='merchant_rider_link__home_restaurant__')
        market = request.query_params.get('market')
        country_code = request.query_params.get('country_code')
        if market:
            q |= _market_q(market, 'market')
        if country_code:
            q |= models.Q(market__country_code__iexact=country_code)
        return queryset.filter(q).distinct() if q else queryset.none()
    if scope_type == 'staff':
        q = request_branch_scope_q(request, relation_prefix='branch_access__branch__')
        market = request.query_params.get('market')
        country_code = request.query_params.get('country_code')
        if market:
            q |= _market_q(market, 'merchant__market')
        if country_code:
            q |= models.Q(merchant__market__country_code__iexact=country_code)
        return queryset.filter(q).distinct() if q else queryset.none()
    if scope_type == 'review_photo':
        q = request_branch_scope_q(request, relation_prefix='review__restaurant__')
        return queryset.filter(q).distinct() if q else queryset.none()
    if scope_type == 'ledger':
        q = models.Q()
        market = request.query_params.get('market')
        country_code = request.query_params.get('country_code')
        if market:
            q &= _market_q(market, 'market')
        if country_code:
            q &= models.Q(country_code__iexact=country_code)
        city_or_area_scope = request.query_params.get('city') or request.query_params.get('area')
        if city_or_area_scope:
            scoped_orders = apply_request_scope_filter(Order.objects.all(), request, 'order')
            scoped_deliveries = apply_request_scope_filter(Delivery.objects.all(), request, 'delivery')
            scoped_fulfillment = MerchantFulfillmentRequest.objects.filter(order__in=scoped_orders)
            q &= (
                models.Q(order__in=scoped_orders)
                | models.Q(delivery__in=scoped_deliveries)
                | models.Q(payment__order__in=scoped_orders)
                | models.Q(fulfillment_request__in=scoped_fulfillment)
            )
        return queryset.filter(q).distinct() if q else queryset
    return queryset


def decimal_sum(queryset, field='amount'):
    value = queryset.aggregate(total=Sum(field))['total']
    return value or Decimal('0.00')


def group_ledger_amounts(field_name, queryset=None):
    if queryset is None:
        queryset = LedgerTransaction.objects.all()
    rows = (
        queryset
        .values(field_name)
        .annotate(amount=Sum('amount'), count=Count('id'))
        .order_by(field_name)
    )
    return [
        {
            'key': row[field_name] or 'UNKNOWN',
            'amount': row['amount'] or Decimal('0.00'),
            'count': row['count'],
        }
        for row in rows
    ]


def ledger_transaction_payload(transaction):
    return {
        'id': transaction.id,
        'type': transaction.transaction_type,
        'amount': transaction.amount,
        'currency': transaction.currency,
        'provider': transaction.provider_code,
        'market': transaction.market.name,
        'country_code': transaction.country_code,
        'created_at': transaction.created_at,
        'source_type': transaction.source_type,
        'source_id': transaction.source_id,
        'idempotency_key': transaction.idempotency_key,
    }


def refund_audit_payload(audit):
    return {
        'id': audit.id,
        'order_id': audit.order_id,
        'amount': audit.amount,
        'currency': audit.currency,
        'status': audit.status,
        'provider_code': audit.provider_code,
        'reason': audit.reason,
        'created_at': audit.created_at,
        'ledger_transaction_id': audit.ledger_transaction_id,
    }


def merchant_payout_audit_payload(audit):
    return {
        'id': audit.id,
        'order_id': audit.order_id,
        'merchant': audit.merchant.business_name,
        'amount': audit.amount,
        'currency': audit.currency,
        'status': audit.status,
        'country_code': audit.country_code,
        'market': audit.market.name,
        'paid_at': audit.paid_at,
        'created_at': audit.created_at,
        'ledger_transaction_id': audit.ledger_transaction_id,
    }


def partner_payout_audit_payload(audit):
    return {
        'id': audit.id,
        'delivery_id': audit.delivery_id,
        'order_id': audit.delivery.order_id,
        'partner': audit.partner.partner_name,
        'amount': audit.amount,
        'currency': audit.currency,
        'status': audit.status,
        'country_code': audit.country_code,
        'market': audit.market.name,
        'paid_at': audit.paid_at,
        'created_at': audit.created_at,
        'ledger_transaction_id': audit.ledger_transaction_id,
    }


SENSITIVE_CONFIG_KEYS = (
    'secret', 'password', 'token', 'key', 'credential', 'private',
)


def provider_capability_payload(capability):
    return {
        'code': capability.code,
        'display_name': capability.display_name,
        'supported_countries': capability.countries,
        'supported_currencies': capability.currencies,
        'supported_payment_methods': capability.payment_methods,
        'capabilities': capability.capabilities,
    }


class PaymentProviderConfigSerializer(serializers.ModelSerializer):
    market_name = serializers.CharField(source='market.name', read_only=True)
    provider_display_name = serializers.SerializerMethodField()
    supported_countries = serializers.SerializerMethodField()
    supported_currencies = serializers.SerializerMethodField()
    supported_payment_methods = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = PaymentProviderConfig
        fields = (
            'id', 'market', 'market_name', 'country_code', 'currency',
            'provider_code', 'provider_display_name', 'payment_method',
            'is_active', 'is_preferred', 'priority', 'supports_refund',
            'supports_webhook', 'supports_partial_refund', 'credentials_present',
            'config_metadata', 'supported_countries', 'supported_currencies',
            'supported_payment_methods', 'created_at', 'updated_at',
            'updated_by_name',
        )
        read_only_fields = (
            'id', 'market_name', 'provider_display_name', 'supported_countries',
            'supported_currencies', 'supported_payment_methods', 'created_at',
            'updated_at', 'updated_by_name',
        )

    def get_provider(self, obj):
        provider_class = PROVIDER_REGISTRY.get((obj.provider_code or '').lower())
        return provider_class() if provider_class else None

    def get_provider_display_name(self, obj):
        provider = self.get_provider(obj)
        return provider.display_name if provider else obj.provider_code

    def get_supported_countries(self, obj):
        provider = self.get_provider(obj)
        return provider.supported_countries() if provider else ()

    def get_supported_currencies(self, obj):
        provider = self.get_provider(obj)
        return provider.supported_currencies() if provider else ()

    def get_supported_payment_methods(self, obj):
        provider = self.get_provider(obj)
        return provider.supported_payment_methods() if provider else ()

    def get_updated_by_name(self, obj):
        if not obj.updated_by_id:
            return ''
        return obj.updated_by.get_full_name() or obj.updated_by.username

    def validate_config_metadata(self, value):
        value = value or {}
        for key in value.keys():
            normalized = str(key).lower()
            if any(marker in normalized for marker in SENSITIVE_CONFIG_KEYS):
                raise serializers.ValidationError(
                    'Do not store secrets, tokens, passwords, or raw credentials here.'
                )
        return value

    def validate(self, attrs):
        instance = self.instance
        market = attrs.get('market') or (instance.market if instance else None)
        provider_code = (attrs.get('provider_code') or (instance.provider_code if instance else '')).lower()
        payment_method = (attrs.get('payment_method') or (instance.payment_method if instance else '')).upper()
        country_code = (attrs.get('country_code') or (instance.country_code if instance else '')).upper()
        currency = (attrs.get('currency') or (instance.currency if instance else '')).upper()

        if not provider_code or provider_code not in PROVIDER_REGISTRY:
            raise serializers.ValidationError({'provider_code': 'Unknown payment provider.'})
        if payment_method not in SUPPORTED_PAYMENT_METHODS:
            raise serializers.ValidationError({'payment_method': 'Unsupported payment method.'})
        if market:
            country_code = country_code or market.country_code
            currency = currency or market.default_currency.code
        provider = PROVIDER_REGISTRY[provider_code]()
        if not provider.supports(
            country=country_code,
            currency=currency,
            payment_method=payment_method,
        ):
            raise serializers.ValidationError(
                'Provider does not support this country, currency, and payment method combination.'
            )
        attrs['provider_code'] = provider_code
        attrs['payment_method'] = payment_method
        attrs['country_code'] = country_code
        attrs['currency'] = currency
        return attrs


class OperationsOfferSerializer(serializers.ModelSerializer):
    market_name = serializers.CharField(source='market.name', read_only=True)
    market_country_code = serializers.CharField(source='market.country_code', read_only=True)
    market_currency = serializers.CharField(source='market.default_currency.code', read_only=True)

    class Meta:
        model = Offer
        fields = (
            'id', 'market', 'market_name', 'market_country_code', 'market_currency',
            'code', 'discount_percent', 'min_order_amount', 'is_active',
            'valid_until', 'max_uses_total', 'max_uses_per_customer',
            'first_order_only',
        )
        read_only_fields = (
            'id', 'market_name', 'market_country_code', 'market_currency',
        )

    def validate_code(self, value):
        return str(value).strip().upper()

    def validate_discount_percent(self, value):
        if value < 1 or value > 100:
            raise serializers.ValidationError('Discount percent must be between 1 and 100.')
        return value


class OperationsMerchantSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    owner_name = serializers.SerializerMethodField()
    date_joined = serializers.DateTimeField(source='user.date_joined', read_only=True)
    restaurants = serializers.SerializerMethodField()
    document_summary = serializers.SerializerMethodField()

    class Meta:
        model = MerchantProfile
        fields = (
            'id', 'username', 'email', 'owner_name', 'business_name', 'phone',
            'is_verified', 'verification_status',
            'verification_rejection_reason', 'verification_submitted_at',
            'verification_reviewed_at', 'date_joined', 'restaurants',
            'document_summary',
        )

    def get_owner_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    def get_restaurants(self, obj):
        return [
            {
                'id': restaurant.id,
                'name': restaurant.rest_name,
                'city': restaurant.rest_city,
                'is_active': restaurant.is_active,
                'is_open': restaurant_accepting_orders(restaurant),
            }
            for restaurant in obj.user.owned_restaurants.all()
        ]

    def get_document_summary(self, obj):
        return merchant_document_summary(obj.user)


class OperationsPartnerSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    owner_name = serializers.SerializerMethodField()
    date_joined = serializers.DateTimeField(source='user.date_joined', read_only=True)
    delivery_count = serializers.IntegerField(read_only=True)
    document_summary = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryPartner
        fields = (
            'id', 'username', 'email', 'owner_name', 'partner_name',
            'partner_phone', 'transport_details', 'is_available',
            'is_verified', 'verification_status',
            'verification_rejection_reason', 'verification_submitted_at',
            'verification_reviewed_at', 'date_joined', 'delivery_count',
            'document_summary',
        )

    def get_owner_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    def get_document_summary(self, obj):
        return partner_document_summary(obj.user)


class OperationsStaffSerializer(serializers.ModelSerializer):
    merchant_company = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    email = serializers.EmailField(source='user.email', read_only=True)
    phone = serializers.SerializerMethodField()
    assigned_branches = serializers.SerializerMethodField()
    submitted_at = serializers.DateTimeField(
        source='verification_submitted_at',
        read_only=True,
    )
    reviewed_at = serializers.DateTimeField(
        source='verification_reviewed_at',
        read_only=True,
    )
    reviewed_by = serializers.SerializerMethodField()

    class Meta:
        model = MerchantStaffMember
        fields = (
            'id', 'merchant_company', 'user', 'name', 'email', 'phone', 'role',
            'membership_status', 'verification_status',
            'verification_rejection_reason', 'assigned_branches',
            'is_company_wide', 'submitted_at', 'reviewed_at', 'reviewed_by',
            'created_at', 'updated_at',
        )

    def get_merchant_company(self, obj):
        market = obj.merchant.market
        return {
            'id': obj.merchant_id,
            'business_name': obj.merchant.business_name,
            'is_verified': obj.merchant.is_verified,
            'verification_status': obj.merchant.verification_status,
            'market': {
                'id': market.id,
                'name': market.name,
                'slug': market.slug,
                'country_code': market.country_code,
            } if market else None,
        }

    def get_user(self, obj):
        return {
            'id': obj.user_id,
            'username': obj.user.username,
            'email': obj.user.email,
            'is_active': obj.user.is_active,
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
        return [
            {
                'id': branch.id,
                'name': branch.rest_name,
                'branch_name': branch.branch_name or branch.rest_name,
                'branch_type': branch.branch_type,
                'is_active': branch.is_active,
                'is_open': branch.is_open,
                'country_code': branch.country_code,
                'market': branch.market.slug if branch.market_id else None,
                'city': branch.city_ref.name if branch.city_ref_id else branch.rest_city,
                'area': branch.area_ref.name if branch.area_ref_id else '',
            }
            for branch in branches
        ]

    def get_reviewed_by(self, obj):
        if not obj.verification_reviewed_by_id:
            return None
        return {
            'id': obj.verification_reviewed_by_id,
            'username': obj.verification_reviewed_by.username,
        }


class OperationsMerchantRiderSerializer(serializers.ModelSerializer):
    merchant = serializers.SerializerMethodField()
    rider = serializers.SerializerMethodField()
    verification = serializers.SerializerMethodField()
    home_restaurant = serializers.SerializerMethodField()

    class Meta:
        model = MerchantRider
        fields = (
            'id', 'merchant', 'rider', 'verification', 'status',
            'home_restaurant', 'approved_at', 'created_at', 'updated_at',
        )

    def get_merchant(self, obj):
        return {
            'id': obj.merchant_id,
            'business_name': obj.merchant.business_name,
            'username': obj.merchant.user.username,
            'email': obj.merchant.user.email,
        }

    def get_rider(self, obj):
        return {
            'id': obj.partner_id,
            'name': obj.partner.partner_name,
            'phone': obj.partner.partner_phone,
            'transport_type': obj.partner.transport_details,
            'username': obj.partner.user.username,
            'email': obj.partner.user.email,
            'is_available': obj.partner.is_available,
        }

    def get_verification(self, obj):
        return {
            'is_verified': obj.partner.is_verified,
            'status': obj.partner.verification_status,
            'rejection_reason': obj.partner.verification_rejection_reason,
        }

    def get_home_restaurant(self, obj):
        if not obj.home_restaurant:
            return None
        return {
            'id': obj.home_restaurant_id,
            'name': obj.home_restaurant.rest_name,
        }


class OperationsSupportTicketSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()
    customer_email = serializers.EmailField(source='customer.email', read_only=True)
    order_total = serializers.DecimalField(
        source='order.total_amount', max_digits=10, decimal_places=2, read_only=True
    )
    payment_status = serializers.CharField(source='order.payment.status', read_only=True)
    payment_method = serializers.CharField(source='order.payment.method', read_only=True)
    pickup_branch = serializers.IntegerField(source='order.pickup_branch_id', read_only=True)
    pickup_branch_name = serializers.SerializerMethodField()
    branch_type = serializers.SerializerMethodField()
    fulfillment_context = serializers.SerializerMethodField()

    class Meta:
        model = SupportTicket
        fields = (
            'id', 'order_id', 'customer_name', 'customer_email', 'order_total',
            'category', 'description', 'status', 'refund_status',
            'refunded_amount', 'resolution', 'payment_status', 'payment_method',
            'pickup_branch', 'pickup_branch_name', 'branch_type',
            'fulfillment_context', 'created_at', 'updated_at',
        )

    def get_customer_name(self, obj):
        return obj.customer.get_full_name() or obj.customer.username

    def get_pickup_branch(self, obj):
        if hasattr(obj, '_cached_pickup_branch_for_serializer'):
            return obj._cached_pickup_branch_for_serializer
        branch = obj.order.pickup_branch
        if branch:
            obj._cached_pickup_branch_for_serializer = branch
            return branch
        first_item = obj.order.items.first()
        branch = first_item.food.restaurant if first_item else None
        obj._cached_pickup_branch_for_serializer = branch
        return branch

    def get_pickup_branch_name(self, obj):
        branch = self.get_pickup_branch(obj)
        return branch.branch_name or branch.rest_name if branch else ''

    def get_branch_type(self, obj):
        branch = self.get_pickup_branch(obj)
        return branch.branch_type if branch else ''

    def get_fulfillment_context(self, obj):
        prefetched_requests = getattr(obj.order, 'prefetched_fulfillment_requests', None)
        if prefetched_requests is not None:
            fulfillment_request = prefetched_requests[0] if prefetched_requests else None
        else:
            fulfillment_request = (
                MerchantFulfillmentRequest.objects
                .filter(order_id=obj.order_id)
                .select_related(
                    'requesting_merchant__user',
                    'fulfilling_merchant__user',
                )
                .order_by('-created_at', '-id')
                .first()
            )
        if not fulfillment_request:
            return {'has_fulfillment_request': False}
        return {
            'has_fulfillment_request': True,
            'fulfillment_request_id': fulfillment_request.id,
            'requesting_merchant': {
                'id': fulfillment_request.requesting_merchant_id,
                'business_name': fulfillment_request.requesting_merchant.business_name,
                'username': fulfillment_request.requesting_merchant.user.username,
            },
            'fulfilling_merchant': {
                'id': fulfillment_request.fulfilling_merchant_id,
                'business_name': fulfillment_request.fulfilling_merchant.business_name,
                'username': fulfillment_request.fulfilling_merchant.user.username,
            },
            'fulfillment_status': fulfillment_request.status,
            'internal_status': fulfillment_request.internal_status,
            'operations_note': fulfillment_request.operations_note,
            'settlement_preview_status': (
                'AVAILABLE' if fulfillment_request.settlement_preview else 'NOT_AVAILABLE'
            ),
        }


class OperationsDispatchSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(source='order.id', read_only=True)
    customer_name = serializers.SerializerMethodField()
    restaurant_name = serializers.SerializerMethodField()
    pickup_branch = serializers.IntegerField(source='order.pickup_branch_id', read_only=True)
    pickup_branch_name = serializers.SerializerMethodField()
    branch_type = serializers.SerializerMethodField()
    delivery_address = serializers.CharField(source='order.delivery_address', read_only=True)
    delivery_instructions = serializers.CharField(
        source='order.delivery_instructions', read_only=True
    )
    total_amount = serializers.DecimalField(
        source='order.total_amount', max_digits=10, decimal_places=2, read_only=True
    )
    partner_id = serializers.IntegerField(source='delivery_partner.id', read_only=True)
    partner_name = serializers.CharField(
        source='delivery_partner.partner_name', read_only=True, allow_null=True
    )
    partner_username = serializers.CharField(
        source='delivery_partner.user.username', read_only=True, allow_null=True
    )

    class Meta:
        model = Delivery
        fields = (
            'id', 'order_id', 'customer_name', 'restaurant_name',
            'pickup_branch', 'pickup_branch_name', 'branch_type',
            'delivery_address', 'delivery_instructions', 'total_amount',
            'status', 'partner_id',
            'partner_name', 'partner_username', 'assigned_at', 'delivery_date',
        )

    def get_customer_name(self, obj):
        return obj.order.customer.get_full_name() or obj.order.customer.username

    def get_restaurant_name(self, obj):
        branch = self.get_pickup_branch(obj)
        return branch.rest_name if branch else ''

    def get_pickup_branch(self, obj):
        if hasattr(obj, '_cached_pickup_branch_for_serializer'):
            return obj._cached_pickup_branch_for_serializer
        branch = obj.order.pickup_branch
        if branch:
            obj._cached_pickup_branch_for_serializer = branch
            return branch
        first_item = obj.order.items.first()
        branch = first_item.food.restaurant if first_item else None
        obj._cached_pickup_branch_for_serializer = branch
        return branch

    def get_pickup_branch_name(self, obj):
        branch = self.get_pickup_branch(obj)
        return branch.branch_name or branch.rest_name if branch else ''

    def get_branch_type(self, obj):
        branch = self.get_pickup_branch(obj)
        return branch.branch_type if branch else ''


class OperationsPartnerPayoutSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(source='order.id', read_only=True)
    partner_id = serializers.IntegerField(source='delivery_partner.id', read_only=True)
    partner_name = serializers.CharField(source='delivery_partner.partner_name', read_only=True)
    partner_username = serializers.CharField(
        source='delivery_partner.user.username', read_only=True
    )

    class Meta:
        model = Delivery
        fields = (
            'id', 'order_id', 'partner_id', 'partner_name', 'partner_username',
            'partner_fee', 'payout_status', 'paid_at', 'assigned_at',
        )


class OperationsMerchantPayoutSerializer(serializers.ModelSerializer):
    merchant_name = serializers.SerializerMethodField()
    merchant_username = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            'id', 'merchant_name', 'merchant_username', 'merchant_payout',
            'merchant_payout_status', 'merchant_paid_at', 'created_at',
        )

    def get_merchant(self, obj):
        first_item = obj.items.first()
        return first_item.food.restaurant.owner if first_item else None

    def get_merchant_name(self, obj):
        merchant = self.get_merchant(obj)
        if not merchant:
            return ''
        profile = getattr(merchant, 'merchant_profile', None)
        return profile.business_name if profile else merchant.get_full_name() or merchant.username

    def get_merchant_username(self, obj):
        merchant = self.get_merchant(obj)
        return merchant.username if merchant else ''


class OperationsFulfillmentRequestSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(source='order.id', read_only=True)
    requesting_merchant = serializers.SerializerMethodField()
    fulfilling_merchant = serializers.SerializerMethodField()
    requested_by = serializers.SerializerMethodField()
    responded_by = serializers.SerializerMethodField()
    resolved_by = serializers.SerializerMethodField()
    cancelled_by = serializers.SerializerMethodField()
    events = serializers.SerializerMethodField()
    settlement_preview_label = serializers.SerializerMethodField()

    class Meta:
        model = MerchantFulfillmentRequest
        fields = (
            'id', 'order_id', 'requesting_merchant', 'fulfilling_merchant',
            'status', 'internal_status', 'notes', 'operations_note',
            'blocked_reason', 'settlement_preview',
            'settlement_preview_label', 'preparation_started_at',
            'ready_for_handoff_at', 'resolved_at', 'cancelled_at',
            'requested_at', 'responded_at', 'requested_by', 'responded_by',
            'resolved_by', 'cancelled_by', 'events', 'created_at',
            'updated_at',
        )

    def merchant_payload(self, merchant):
        return {
            'id': merchant.id,
            'business_name': merchant.business_name,
            'username': merchant.user.username,
            'email': merchant.user.email,
            'is_verified': merchant.is_verified,
            'verification_status': merchant.verification_status,
        }

    def user_payload(self, user):
        if not user:
            return None
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'name': user.get_full_name() or user.username,
        }

    def get_requesting_merchant(self, obj):
        return self.merchant_payload(obj.requesting_merchant)

    def get_fulfilling_merchant(self, obj):
        return self.merchant_payload(obj.fulfilling_merchant)

    def get_requested_by(self, obj):
        return self.user_payload(obj.requested_by)

    def get_responded_by(self, obj):
        return self.user_payload(obj.responded_by)

    def get_resolved_by(self, obj):
        return self.user_payload(obj.resolved_by)

    def get_cancelled_by(self, obj):
        return self.user_payload(obj.cancelled_by)

    def get_events(self, obj):
        return [
            {
                'id': event.id,
                'event_type': event.event_type,
                'from_status': event.from_status,
                'to_status': event.to_status,
                'actor': self.user_payload(event.actor),
                'note': event.note,
                'metadata': event.metadata,
                'created_at': event.created_at,
            }
            for event in obj.events.all()
        ]

    def get_settlement_preview_label(self, obj):
        return SETTLEMENT_PREVIEW_LABEL if obj.settlement_preview else ''


class OperationsCustomerSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='user.id', read_only=True)
    name = serializers.SerializerMethodField()
    email = serializers.EmailField(source='user.email', read_only=True)
    phone = serializers.CharField(read_only=True)
    avatar = serializers.SerializerMethodField()
    total_orders = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(source='user.date_joined', read_only=True)
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)

    class Meta:
        model = Customer
        fields = (
            'id', 'name', 'email', 'phone', 'avatar', 'total_orders',
            'created_at', 'is_active',
        )

    def get_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    def get_avatar(self, obj):
        if not obj.avatar:
            return None
        request = self.context.get('request')
        url = obj.avatar.url
        return request.build_absolute_uri(url) if request else url


class OperationsRestaurantSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='rest_name', read_only=True)
    merchant_business_name = serializers.SerializerMethodField()
    is_open = serializers.SerializerMethodField()
    merchant_verified = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    area = serializers.SerializerMethodField()
    location = serializers.CharField(source='rest_address', read_only=True)
    branch_manager_name = serializers.SerializerMethodField()

    class Meta:
        model = Restaurant
        fields = (
            'id', 'name', 'merchant_business_name', 'is_open', 'is_active',
            'merchant_verified', 'delivery_radius_km', 'city', 'area',
            'location', 'branch_name', 'branch_code', 'branch_type',
            'country_code', 'city_ref', 'area_ref', 'branch_manager_name',
        )

    def get_merchant_profile(self, obj):
        return getattr(obj.owner, 'merchant_profile', None) if obj.owner else None

    def get_merchant_business_name(self, obj):
        profile = self.get_merchant_profile(obj)
        if profile and profile.business_name:
            return profile.business_name
        return obj.owner.get_full_name() or obj.owner.username if obj.owner else ''

    def get_is_open(self, obj):
        return restaurant_accepting_orders(obj)

    def get_merchant_verified(self, obj):
        profile = self.get_merchant_profile(obj)
        return bool(profile and profile.is_verified)

    def get_city(self, obj):
        return obj.city_ref.name if obj.city_ref_id else obj.rest_city

    def get_area(self, obj):
        return obj.area_ref.name if obj.area_ref_id else ''

    def get_branch_manager_name(self, obj):
        manager = obj.branch_manager
        if not manager:
            return ''
        return manager.get_full_name() or manager.username


class OperationsBranchSerializer(serializers.ModelSerializer):
    branch_id = serializers.IntegerField(source='id', read_only=True)
    merchant_company = serializers.SerializerMethodField()
    merchant_verification_status = serializers.SerializerMethodField()
    market = serializers.SerializerMethodField()
    country = serializers.CharField(source='country_code', read_only=True)
    city = serializers.SerializerMethodField()
    area = serializers.SerializerMethodField()
    address = serializers.CharField(source='rest_address', read_only=True)
    location = serializers.SerializerMethodField()
    accepting_orders = serializers.SerializerMethodField()
    menu_count = serializers.IntegerField(read_only=True, default=0)
    rider_count = serializers.IntegerField(read_only=True, default=0)
    available_rider_count = serializers.IntegerField(read_only=True, default=0)
    verified_rider_count = serializers.IntegerField(read_only=True, default=0)
    order_count = serializers.IntegerField(read_only=True, default=0)
    revenue_summary = serializers.SerializerMethodField()
    analytics = serializers.SerializerMethodField()
    branch_riders = serializers.SerializerMethodField()

    class Meta:
        model = Restaurant
        fields = (
            'branch_id', 'branch_name', 'rest_name', 'branch_type',
            'merchant_company', 'merchant_verification_status', 'market',
            'country', 'city', 'area', 'address', 'location', 'is_open',
            'accepting_orders', 'is_active', 'delivery_radius_km', 'menu_count', 'rider_count',
            'available_rider_count', 'verified_rider_count', 'branch_riders',
            'order_count', 'revenue_summary', 'analytics', 'created_at', 'updated_at',
        )

    def get_merchant_profile(self, obj):
        return getattr(obj.owner, 'merchant_profile', None) if obj.owner else None

    def get_merchant_company(self, obj):
        profile = self.get_merchant_profile(obj)
        return {
            'id': profile.id if profile else None,
            'business_name': (
                profile.business_name if profile and profile.business_name
                else obj.owner.get_full_name() or obj.owner.username
                if obj.owner else ''
            ),
            'username': obj.owner.username if obj.owner else '',
            'email': obj.owner.email if obj.owner else '',
        }

    def get_merchant_verification_status(self, obj):
        profile = self.get_merchant_profile(obj)
        return {
            'is_verified': bool(profile and profile.is_verified),
            'status': (
                profile.verification_status if profile else 'PENDING'
            ),
        }

    def get_market(self, obj):
        if not obj.market_id:
            return None
        return {
            'id': obj.market_id,
            'name': obj.market.name,
            'slug': obj.market.slug,
            'country_code': obj.market.country_code,
            'currency': obj.market.default_currency.code,
        }

    def get_city(self, obj):
        return {
            'id': obj.city_ref_id,
            'name': obj.city_ref.name if obj.city_ref_id else obj.rest_city,
            'slug': obj.city_ref.slug if obj.city_ref_id else '',
        }

    def get_area(self, obj):
        return {
            'id': obj.area_ref_id,
            'name': obj.area_ref.name if obj.area_ref_id else '',
            'slug': obj.area_ref.slug if obj.area_ref_id else '',
        }

    def get_location(self, obj):
        return {
            'latitude': obj.pickup_latitude,
            'longitude': obj.pickup_longitude,
        }

    def get_accepting_orders(self, obj):
        return restaurant_accepting_orders(obj)

    def get_revenue_summary(self, obj):
        return {
            'gross_sales': getattr(obj, 'gross_sales', Decimal('0.00')) or Decimal('0.00'),
            'platform_fee': getattr(obj, 'platform_fee_total', Decimal('0.00')) or Decimal('0.00'),
            'merchant_payout': getattr(obj, 'merchant_payout_total', Decimal('0.00')) or Decimal('0.00'),
        }

    def get_analytics(self, obj):
        order_count = getattr(obj, 'order_count', 0) or 0
        gross_sales = getattr(obj, 'gross_sales', Decimal('0.00')) or Decimal('0.00')
        rider_count = getattr(obj, 'rider_count', 0) or 0
        available_rider_count = getattr(obj, 'available_rider_count', 0) or 0
        verified_rider_count = getattr(obj, 'verified_rider_count', 0) or 0
        return {
            'orders': order_count,
            'revenue': gross_sales,
            'average_order_value': (
                (gross_sales / order_count).quantize(Decimal('0.01'))
                if order_count else Decimal('0.00')
            ),
            'rider_count': rider_count,
            'available_riders': available_rider_count,
            'verified_riders': verified_rider_count,
            'rider_utilization_percent': (
                round((available_rider_count / rider_count) * 100, 2)
                if rider_count else 0
            ),
            'performance_label': (
                'Top branch' if gross_sales > 0 and order_count > 0 else 'Needs attention'
            ),
        }

    def get_branch_riders(self, obj):
        riders = getattr(obj, 'merchant_riders_cache', None)
        if riders is None:
            riders = obj.merchant_riders.select_related('partner__user').all()[:10]
        else:
            riders = riders[:10]
        return [
            {
                'id': rider.id,
                'name': rider.partner.partner_name,
                'phone': rider.partner.partner_phone,
                'status': rider.status,
                'is_available': rider.partner.is_available,
                'is_verified': rider.partner.is_verified,
                'transport_type': rider.partner.transport_details,
                'username': rider.partner.user.username,
            }
            for rider in riders
        ]


class OperationsBranchStatusSerializer(serializers.Serializer):
    is_active = serializers.BooleanField(required=False)
    is_open = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if 'is_active' not in attrs and 'is_open' not in attrs:
            raise serializers.ValidationError(
                'Provide is_active or is_open.'
            )
        return attrs


class OperationsOrderSerializer(serializers.ModelSerializer):
    customer = serializers.SerializerMethodField()
    restaurant = serializers.SerializerMethodField()
    pickup_branch = serializers.IntegerField(source='pickup_branch_id', read_only=True)
    pickup_branch_name = serializers.SerializerMethodField()
    branch_type = serializers.SerializerMethodField()
    payment_status = serializers.CharField(source='payment.status', read_only=True)
    delivery_status = serializers.CharField(source='delivery.status', read_only=True)

    class Meta:
        model = Order
        fields = (
            'id', 'customer', 'restaurant', 'status', 'total_amount',
            'pickup_branch', 'pickup_branch_name', 'branch_type',
            'created_at', 'payment_status', 'delivery_status',
        )

    def get_customer(self, obj):
        return obj.customer.get_full_name() or obj.customer.username

    def get_restaurant(self, obj):
        branch = self.get_pickup_branch(obj)
        return branch.rest_name if branch else ''

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


class OperationsReviewPhotoSerializer(serializers.ModelSerializer):
    review_id = serializers.IntegerField(source='review.id', read_only=True)
    rating = serializers.IntegerField(source='review.rating', read_only=True)
    comment = serializers.CharField(source='review.comment', read_only=True)
    customer = serializers.SerializerMethodField()
    branch = serializers.SerializerMethodField()
    merchant_company = serializers.SerializerMethodField()
    order_id = serializers.IntegerField(source='review.order_id', read_only=True)
    image_preview_url = serializers.SerializerMethodField()
    reviewed_by = serializers.SerializerMethodField()

    class Meta:
        model = ReviewPhoto
        fields = (
            'id', 'review_id', 'rating', 'comment', 'customer', 'branch',
            'merchant_company', 'order_id', 'status', 'caption',
            'image_preview_url', 'created_at', 'updated_at', 'reviewed_by',
            'reviewed_at', 'moderation_reason',
        )

    def get_customer(self, obj):
        user = obj.review.customer
        return {
            'id': user.id,
            'name': user.get_full_name() or user.username,
            'username': user.username,
            'email': user.email,
        }

    def get_branch(self, obj):
        branch = obj.review.restaurant
        if not branch:
            return None
        return {
            'id': branch.id,
            'name': branch.branch_name or branch.rest_name,
            'rest_name': branch.rest_name,
            'branch_type': branch.branch_type,
            'market': branch.market_id,
            'country_code': branch.country_code,
            'city': branch.city_ref.name if branch.city_ref_id else branch.rest_city,
            'area': branch.area_ref.name if branch.area_ref_id else '',
        }

    def get_merchant_company(self, obj):
        branch = obj.review.restaurant
        owner = branch.owner if branch else None
        profile = getattr(owner, 'merchant_profile', None) if owner else None
        return {
            'id': profile.id if profile else None,
            'business_name': (
                profile.business_name if profile and profile.business_name
                else owner.get_full_name() or owner.username
                if owner else ''
            ),
            'username': owner.username if owner else '',
        }

    def get_image_preview_url(self, obj):
        if not obj.image:
            return None
        request = self.context.get('request')
        path = f'/api/v1/restaurants/review-photos/{obj.id}/preview/'
        return request.build_absolute_uri(path) if request else path

    def get_reviewed_by(self, obj):
        if not obj.reviewed_by:
            return None
        return {
            'id': obj.reviewed_by_id,
            'username': obj.reviewed_by.username,
            'name': obj.reviewed_by.get_full_name() or obj.reviewed_by.username,
        }


class OperationsReviewPhotoModerationSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=('APPROVE', 'REJECT', 'HIDE'))
    reason = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)

    def validate(self, attrs):
        action = attrs['action']
        reason = attrs.get('reason', '')
        if action in ('REJECT', 'HIDE') and not reason:
            raise serializers.ValidationError({
                'reason': 'Reason is required for reject and hide actions.'
            })
        return attrs


OPERATIONS_NOTIFICATION_RECIPIENT_TYPES = {
    Notification.RECIPIENT_OPERATIONS,
    Notification.RECIPIENT_GLOBAL_ADMIN,
    Notification.RECIPIENT_COUNTRY_ADMIN,
    Notification.RECIPIENT_CITY_ADMIN,
    Notification.RECIPIENT_AREA_ADMIN,
}


def _operations_notification_scope_q(actor):
    if actor.is_global_scope:
        return Q()
    scope_q = Q(pk__in=[])
    if actor.assigned_area_ids:
        scope_q |= Q(area_id__in=actor.assigned_area_ids)
        scope_q |= Q(branch__area_ref_id__in=actor.assigned_area_ids)
        return scope_q
    if actor.assigned_city_ids:
        scope_q |= Q(city_id__in=actor.assigned_city_ids)
        scope_q |= Q(area__city_id__in=actor.assigned_city_ids)
        scope_q |= Q(branch__city_ref_id__in=actor.assigned_city_ids)
        scope_q |= Q(branch__area_ref__city_id__in=actor.assigned_city_ids)
        return scope_q
    if actor.assigned_market_ids:
        scope_q |= Q(market_id__in=actor.assigned_market_ids)
        scope_q |= Q(city__market_id__in=actor.assigned_market_ids)
        scope_q |= Q(area__market_id__in=actor.assigned_market_ids)
        scope_q |= Q(branch__market_id__in=actor.assigned_market_ids)
        scope_q |= Q(branch__city_ref__market_id__in=actor.assigned_market_ids)
        scope_q |= Q(branch__area_ref__market_id__in=actor.assigned_market_ids)
    if actor.assigned_country_codes:
        scope_q |= Q(country_code__in=actor.assigned_country_codes)
        scope_q |= Q(market__country_code__in=actor.assigned_country_codes)
        scope_q |= Q(city__market__country_code__in=actor.assigned_country_codes)
        scope_q |= Q(area__market__country_code__in=actor.assigned_country_codes)
        scope_q |= Q(branch__country_code__in=actor.assigned_country_codes)
        scope_q |= Q(branch__market__country_code__in=actor.assigned_country_codes)
    return scope_q


def _actor_can_access_notification(actor, notification):
    if not actor or not actor.permissions:
        return False
    if actor.is_global_scope:
        return True
    if actor.assigned_area_ids:
        if notification.area_id and notification.area_id in actor.assigned_area_ids:
            return True
        branch = notification.branch
        return bool(branch and getattr(branch, 'area_ref_id', None) in actor.assigned_area_ids)
    if actor.assigned_city_ids:
        if notification.city_id and notification.city_id in actor.assigned_city_ids:
            return True
        if notification.area_id and notification.area.city_id in actor.assigned_city_ids:
            return True
        branch = notification.branch
        return bool(branch and (
            getattr(branch, 'city_ref_id', None) in actor.assigned_city_ids
            or getattr(getattr(branch, 'area_ref', None), 'city_id', None) in actor.assigned_city_ids
        ))
    if notification.area_id and can_access_area(actor, notification.area):
        return True
    if notification.city_id and can_access_city(actor, notification.city):
        return True
    if notification.market_id and can_access_market(actor, notification.market):
        return True
    if notification.country_code and can_access_country(actor, notification.country_code):
        return True
    branch = notification.branch
    if branch:
        if getattr(branch, 'area_ref_id', None) and can_access_area(actor, branch.area_ref):
            return True
        if getattr(branch, 'city_ref_id', None) and can_access_city(actor, branch.city_ref):
            return True
        if getattr(branch, 'market_id', None) and can_access_market(actor, branch.market):
            return True
        if getattr(branch, 'country_code', None) and can_access_country(actor, branch.country_code):
            return True
    return False


def _operations_notification_queryset(request):
    actor = get_operations_actor(request.user)
    if not actor.permissions:
        return Notification.objects.none(), actor
    queryset = (
        Notification.objects
        .filter(
            user=request.user,
            recipient_type__in=OPERATIONS_NOTIFICATION_RECIPIENT_TYPES,
        )
        .select_related('order', 'market', 'city', 'area', 'branch')
    )
    queryset = queryset.filter(_operations_notification_scope_q(actor)).distinct()
    params = request.query_params
    status_filter = params.get('status')
    if status_filter:
        statuses = [
            value.strip().upper()
            for value in status_filter.split(',')
            if value.strip()
        ]
        queryset = queryset.filter(status__in=statuses)
    else:
        queryset = queryset.exclude(status__in=[
            Notification.STATUS_ARCHIVED,
            Notification.STATUS_DISMISSED,
        ])
    if not truthy(params.get('include_expired')):
        now = timezone.now()
        queryset = queryset.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    if params.get('category'):
        queryset = queryset.filter(category=params['category'].upper())
    if params.get('priority'):
        queryset = queryset.filter(priority=params['priority'].upper())
    if params.get('event_type'):
        queryset = queryset.filter(event_type=params['event_type'])
    if params.get('market'):
        queryset = queryset.filter(market_id=params['market'])
    if params.get('country_code'):
        queryset = queryset.filter(country_code=str(params['country_code']).upper())
    if params.get('city'):
        queryset = queryset.filter(city_id=params['city'])
    if params.get('area'):
        queryset = queryset.filter(area_id=params['area'])
    if params.get('branch'):
        queryset = queryset.filter(branch_id=params['branch'])
    if params.get('unread') is not None:
        unread_q = Q(status=Notification.STATUS_UNREAD) | Q(is_read=False)
        queryset = queryset.filter(unread_q) if truthy(params.get('unread')) else queryset.exclude(unread_q)
    date_from = parse_bound(params.get('date_from'))
    date_to = parse_bound(params.get('date_to'), end=True)
    if date_from:
        queryset = queryset.filter(created_at__gte=date_from)
    if date_to:
        queryset = queryset.filter(created_at__lte=date_to)
    return queryset, actor


class OperationsNotificationListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        queryset, actor = _operations_notification_queryset(request)
        if not actor.permissions:
            return Response(
                {'detail': 'Operations access required.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        unread_count = queryset.filter(
            Q(status=Notification.STATUS_UNREAD) | Q(is_read=False),
        ).count()
        return Response({
            'unread_count': unread_count,
            'results': NotificationSerializer(queryset, many=True).data,
        })


class OperationsNotificationActionView(APIView):
    permission_classes = [IsAdminUser]
    action_status = None

    def patch(self, request, notification_id):
        queryset, actor = _operations_notification_queryset(request)
        if not actor.permissions:
            return Response(
                {'detail': 'Operations access required.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            notification = queryset.get(id=notification_id)
        except Notification.DoesNotExist:
            return Response(
                {'detail': 'Notification not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not _actor_can_access_notification(actor, notification):
            return Response(
                {'detail': 'Notification not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        notification.status = self.action_status
        if self.action_status in {
            Notification.STATUS_READ,
            Notification.STATUS_ARCHIVED,
            Notification.STATUS_DISMISSED,
        }:
            notification.is_read = True
        notification.metadata = sanitize_metadata(notification.metadata or {})
        notification.save(update_fields=('status', 'is_read', 'metadata'))
        return Response(NotificationSerializer(notification).data)


class OperationsNotificationReadView(OperationsNotificationActionView):
    action_status = Notification.STATUS_READ


class OperationsNotificationArchiveView(OperationsNotificationActionView):
    action_status = Notification.STATUS_ARCHIVED


class OperationsNotificationDismissView(OperationsNotificationActionView):
    action_status = Notification.STATUS_DISMISSED


class OperationsNotificationReadAllView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        queryset, actor = _operations_notification_queryset(request)
        if not actor.permissions:
            return Response(
                {'detail': 'Operations access required.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        updated = queryset.filter(
            Q(status=Notification.STATUS_UNREAD) | Q(is_read=False),
        ).update(is_read=True, status=Notification.STATUS_READ)
        return Response({'updated': updated})


class OperationsSummaryView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, VIEW_GLOBAL_DASHBOARD)
        cached = get_cached_response_data(
            'operations:summary',
            actor,
            request.query_params,
        )
        if cached is not None:
            return Response(cached)
        completed = scoped_order_queryset(Order.objects.filter(
            status='DELIVERED',
            payment__status='SUCCESS',
        ), actor)
        completed = apply_request_scope_filter(completed, request, 'order')
        open_orders = scoped_order_queryset(
            Order.objects.exclude(status__in=('DELIVERED', 'CANCELLED')),
            actor,
        )
        open_orders = apply_request_scope_filter(open_orders, request, 'order')
        customers = scoped_customer_queryset(Customer.objects.all(), actor)
        customers = apply_request_scope_filter(customers, request, 'customer')
        partners = scoped_partner_queryset(DeliveryPartner.objects.all(), actor)
        partners = apply_request_scope_filter(partners, request, 'partner')
        merchants = scoped_merchant_queryset(MerchantProfile.objects.all(), actor)
        merchants = apply_request_scope_filter(merchants, request, 'merchant')
        branches = scoped_branch_queryset(actor)
        branches = apply_request_scope_filter(branches, request, 'branch')
        scoped_orders = apply_request_scope_filter(scoped_order_queryset(Order.objects.all(), actor), request, 'order')
        support_tickets = SupportTicket.objects.filter(order__in=scoped_orders)
        deliveries = scoped_delivery_queryset(Delivery.objects.all(), actor)
        deliveries = apply_request_scope_filter(deliveries, request, 'delivery')
        data = {
            'customers': customers.count(),
            'partners': partners.count(),
            'pending_partners': partners.filter(
                is_verified=False,
                verification_status__in=('PENDING', 'SUBMITTED'),
            ).count(),
            'merchants': merchants.count(),
            'pending_merchants': merchants.filter(
                is_verified=False,
                verification_status__in=('PENDING', 'SUBMITTED'),
            ).count(),
            'open_support_tickets': support_tickets.filter(
                status__in=('OPEN', 'IN_REVIEW')
            ).count(),
            'unassigned_deliveries': deliveries.filter(
                delivery_partner__isnull=True,
                order__status='READY_FOR_PICKUP',
            ).count(),
            'partner_payouts_available': deliveries.filter(
                payout_status='AVAILABLE'
            ).aggregate(total=Sum('partner_fee'))['total'] or 0,
            'merchant_payouts_available': scoped_order_queryset(Order.objects.filter(
                merchant_payout_status='AVAILABLE'
            ), actor).aggregate(total=Sum('merchant_payout'))['total'] or 0,
            'active_restaurants': branches.filter(is_active=True).count(),
            'open_orders': open_orders.count(),
            'delivered_orders': completed.count(),
            'gross_marketplace_value': completed.aggregate(
                total=Sum('total_amount')
            )['total'] or 0,
            'platform_revenue': completed.aggregate(
                total=Sum('platform_fee')
            )['total'] or 0,
            'registered_users': customers.filter(user__is_active=True).count(),
        }
        set_cached_response_data(
            'operations:summary',
            data,
            timeout=45,
            actor_or_user=actor,
            params=request.query_params,
        )
        return Response(data)


class OperationsCustomerListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, VIEW_CUSTOMERS)
        customers = Customer.objects.select_related('user').annotate(
            total_orders=Count('user__orders')
        ).order_by('-user__date_joined')
        customers = scoped_customer_queryset(customers, actor)
        customers = apply_request_scope_filter(customers, request, 'customer')
        customers = apply_range_filter(customers, request, 'user__date_joined')
        return Response(
            OperationsCustomerSerializer(
                customers,
                many=True,
                context={'request': request},
            ).data
        )


class OperationsRestaurantListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, VIEW_BRANCHES)
        restaurants = Restaurant.objects.select_related(
            'owner__merchant_profile', 'city_ref', 'area_ref', 'branch_manager'
        ).order_by('rest_name')
        restaurants = filter_queryset_for_operations_actor(
            restaurants,
            actor,
            BRANCH_SCOPE_FIELD_MAP,
        )
        restaurants = apply_request_scope_filter(restaurants, request, 'branch')
        filter_status = request.query_params.get('status')
        if filter_status == 'active':
            restaurants = restaurants.filter(is_active=True)
        elif filter_status == 'inactive':
            restaurants = restaurants.filter(is_active=False)
        market = request.query_params.get('market')
        country_code = request.query_params.get('country_code')
        city = request.query_params.get('city')
        area = request.query_params.get('area')
        branch_type = request.query_params.get('branch_type')
        if market:
            restaurants = (
                restaurants.filter(market_id=market)
                if str(market).isdigit()
                else restaurants.filter(market__slug__iexact=market)
            )
        if country_code:
            restaurants = restaurants.filter(country_code__iexact=country_code)
        if city:
            restaurants = (
                restaurants.filter(city_ref_id=city)
                if str(city).isdigit()
                else restaurants.filter(
                    models.Q(rest_city__icontains=city) |
                    models.Q(city_ref__name__icontains=city) |
                    models.Q(city_ref__slug__iexact=city)
                )
            )
        if area:
            restaurants = (
                restaurants.filter(area_ref_id=area)
                if str(area).isdigit()
                else restaurants.filter(
                    models.Q(area_ref__name__icontains=area) |
                    models.Q(area_ref__slug__iexact=area)
                )
            )
        if branch_type:
            restaurants = restaurants.filter(branch_type__iexact=branch_type)
        return Response(OperationsRestaurantSerializer(restaurants, many=True).data)


class OperationsBranchListView(APIView):
    permission_classes = [IsAdminUser]

    def get_queryset(self, request):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, VIEW_BRANCHES)
        branches = (
            Restaurant.objects
            .select_related(
                'owner__merchant_profile',
                'market__default_currency',
                'city_ref',
                'area_ref',
            )
            .prefetch_related(models.Prefetch(
                'merchant_riders',
                queryset=MerchantRider.objects.select_related('partner__user').order_by(
                    'status', 'partner__partner_name'
                ),
                to_attr='merchant_riders_cache',
            ))
            .annotate(
                menu_count=Count('food_items', distinct=True),
                rider_count=Count('merchant_riders', distinct=True),
                available_rider_count=Count(
                    'merchant_riders',
                    filter=models.Q(merchant_riders__partner__is_available=True),
                    distinct=True,
                ),
                verified_rider_count=Count(
                    'merchant_riders',
                    filter=models.Q(merchant_riders__partner__is_verified=True),
                    distinct=True,
                ),
                order_count=Count('food_items__orderitem__order', distinct=True),
                gross_sales=Sum(
                    'food_items__orderitem__order__total_amount',
                    filter=models.Q(
                        food_items__orderitem__order__status='DELIVERED',
                        food_items__orderitem__order__payment__status='SUCCESS',
                    ),
                    distinct=True,
                ),
                platform_fee_total=Sum(
                    'food_items__orderitem__order__platform_fee',
                    filter=models.Q(
                        food_items__orderitem__order__status='DELIVERED',
                        food_items__orderitem__order__payment__status='SUCCESS',
                    ),
                    distinct=True,
                ),
                merchant_payout_total=Sum(
                    'food_items__orderitem__order__merchant_payout',
                    filter=models.Q(
                        food_items__orderitem__order__status='DELIVERED',
                        food_items__orderitem__order__payment__status='SUCCESS',
                    ),
                    distinct=True,
                ),
            )
            .order_by('country_code', 'rest_city', 'branch_name', 'rest_name')
        )
        branches = filter_queryset_for_operations_actor(
            branches,
            actor,
            BRANCH_SCOPE_FIELD_MAP,
        )
        branches = apply_request_scope_filter(branches, request, 'branch')
        filters = {
            'id': request.query_params.get('branch') or request.query_params.get('branch_id'),
            'country_code__iexact': request.query_params.get('country_code'),
            'branch_type__iexact': request.query_params.get('branch_type'),
            'owner__merchant_profile__id': request.query_params.get('merchant_id'),
        }
        for field, value in filters.items():
            if value not in (None, ''):
                branches = branches.filter(**{field: value})
        market = request.query_params.get('market')
        city = request.query_params.get('city')
        area = request.query_params.get('area')
        is_active = request.query_params.get('is_active')
        is_open = request.query_params.get('is_open')
        if market:
            branches = (
                branches.filter(market_id=market)
                if str(market).isdigit()
                else branches.filter(market__slug__iexact=market)
            )
        if city:
            branches = (
                branches.filter(city_ref_id=city)
                if str(city).isdigit()
                else branches.filter(
                    models.Q(rest_city__icontains=city)
                    | models.Q(city_ref__name__icontains=city)
                    | models.Q(city_ref__slug__iexact=city)
                )
            )
        if area:
            branches = (
                branches.filter(area_ref_id=area)
                if str(area).isdigit()
                else branches.filter(
                    models.Q(area_ref__name__icontains=area)
                    | models.Q(area_ref__slug__iexact=area)
                )
            )
        if is_active in ('true', 'false'):
            branches = branches.filter(is_active=(is_active == 'true'))
        if is_open in ('true', 'false'):
            branches = branches.filter(is_open=(is_open == 'true'))
        return branches

    def get(self, request):
        return Response(
            OperationsBranchSerializer(self.get_queryset(request), many=True).data
        )


class OperationsBranchStatusView(APIView):
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def patch(self, request, branch_id):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, MANAGE_BRANCHES)
        branch = (
            Restaurant.objects
            .select_for_update()
            .filter(id=branch_id)
            .first()
        )
        if not branch:
            return Response(
                {'detail': 'Branch not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        scoped_branch_exists = filter_queryset_for_operations_actor(
            Restaurant.objects.filter(id=branch.id),
            actor,
            BRANCH_SCOPE_FIELD_MAP,
        ).exists()
        if not scoped_branch_exists:
            return Response(
                {'detail': 'Branch not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = OperationsBranchStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        merchant = getattr(branch.owner, 'merchant_profile', None) if branch.owner else None
        if (
            serializer.validated_data.get('is_active') is True
            and not (merchant and merchant.is_verified)
        ):
            return Response(
                {'is_active': ['Verify the merchant company before activating this branch.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        update_fields = []
        for field in ('is_active', 'is_open'):
            if field in serializer.validated_data:
                setattr(branch, field, serializer.validated_data[field])
                update_fields.append(field)
        branch.save(update_fields=update_fields + ['updated_at'])
        for field in update_fields:
            if field == 'is_active':
                notify_branch_event(
                    branch,
                    'activated' if branch.is_active else 'deactivated',
                    actor=request.user,
                )
            if field == 'is_open':
                notify_branch_event(
                    branch,
                    'opened' if branch.is_open else 'closed',
                    actor=request.user,
                )
        branch = self.get_serialized_branch(branch.id)
        return Response(OperationsBranchSerializer(branch).data)

    def get_serialized_branch(self, branch_id):
        return (
            Restaurant.objects
            .select_related(
                'owner__merchant_profile',
                'market__default_currency',
                'city_ref',
                'area_ref',
            )
            .prefetch_related(models.Prefetch(
                'merchant_riders',
                queryset=MerchantRider.objects.select_related('partner__user').order_by(
                    'status', 'partner__partner_name'
                ),
                to_attr='merchant_riders_cache',
            ))
            .annotate(
                menu_count=Count('food_items', distinct=True),
                rider_count=Count('merchant_riders', distinct=True),
                available_rider_count=Count(
                    'merchant_riders',
                    filter=models.Q(merchant_riders__partner__is_available=True),
                    distinct=True,
                ),
                verified_rider_count=Count(
                    'merchant_riders',
                    filter=models.Q(merchant_riders__partner__is_verified=True),
                    distinct=True,
                ),
                order_count=Count('food_items__orderitem__order', distinct=True),
                gross_sales=Sum(
                    'food_items__orderitem__order__total_amount',
                    filter=models.Q(
                        food_items__orderitem__order__status='DELIVERED',
                        food_items__orderitem__order__payment__status='SUCCESS',
                    ),
                    distinct=True,
                ),
                platform_fee_total=Sum(
                    'food_items__orderitem__order__platform_fee',
                    filter=models.Q(
                        food_items__orderitem__order__status='DELIVERED',
                        food_items__orderitem__order__payment__status='SUCCESS',
                    ),
                    distinct=True,
                ),
                merchant_payout_total=Sum(
                    'food_items__orderitem__order__merchant_payout',
                    filter=models.Q(
                        food_items__orderitem__order__status='DELIVERED',
                        food_items__orderitem__order__payment__status='SUCCESS',
                    ),
                    distinct=True,
                ),
            )
            .get(id=branch_id)
        )


class OperationsOrderListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, VIEW_ORDERS)
        orders = Order.objects.select_related(
            'customer', 'payment', 'delivery', 'pickup_branch'
        ).prefetch_related('items__food__restaurant').order_by('-created_at')
        orders = scoped_order_queryset(orders, actor)
        orders = apply_request_scope_filter(orders, request, 'order')
        filter_status = request.query_params.get('status')
        if filter_status == 'open':
            orders = orders.exclude(status__in=('DELIVERED', 'CANCELLED', 'EXPIRED'))
        elif filter_status in dict(Order.STATUS_CHOICES):
            orders = orders.filter(status=filter_status)
        orders = apply_range_filter(orders, request, 'created_at')
        return Response(OperationsOrderSerializer(orders, many=True).data)


class OperationsRevenueView(APIView):
    permission_classes = [IsAdminUser]

    def _order_totals(self, orders):
        return {
            'gross_sales': orders.aggregate(total=Sum('total_amount'))['total'] or 0,
            'merchant_earnings': orders.aggregate(total=Sum('merchant_payout'))['total'] or 0,
            'platform_revenue': orders.aggregate(total=Sum('platform_fee'))['total'] or 0,
            'delivery_fees': orders.aggregate(total=Sum('delivery_fee'))['total'] or 0,
        }

    def get(self, request):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, VIEW_FINANCE)
        now = timezone.now()
        completed_orders = scoped_order_queryset(Order.objects.filter(
            status='DELIVERED',
            payment__status='SUCCESS',
        ), actor)
        completed_orders = apply_request_scope_filter(completed_orders, request, 'order')
        completed_orders = apply_range_filter(completed_orders, request, 'created_at')
        pending_merchant_payouts = scoped_order_queryset(Order.objects.filter(
            merchant_payout_status='AVAILABLE',
        ), actor)
        pending_merchant_payouts = apply_request_scope_filter(pending_merchant_payouts, request, 'order')
        pending_merchant_payouts = apply_range_filter(
            pending_merchant_payouts, request, 'created_at'
        ).aggregate(total=Sum('merchant_payout'))['total'] or 0
        paid_merchant_payouts = scoped_order_queryset(Order.objects.filter(
            merchant_payout_status='PAID',
        ), actor)
        paid_merchant_payouts = apply_request_scope_filter(paid_merchant_payouts, request, 'order')
        paid_merchant_payouts = apply_range_filter(
            paid_merchant_payouts, request, 'merchant_paid_at'
        ).aggregate(total=Sum('merchant_payout'))['total'] or 0
        pending_partner_payouts = scoped_delivery_queryset(Delivery.objects.filter(
            payout_status='AVAILABLE',
        ), actor)
        pending_partner_payouts = apply_request_scope_filter(pending_partner_payouts, request, 'delivery')
        pending_partner_payouts = apply_range_filter(
            pending_partner_payouts, request, 'delivery_date'
        ).aggregate(total=Sum('partner_fee'))['total'] or 0
        paid_partner_payouts = scoped_delivery_queryset(Delivery.objects.filter(
            payout_status='PAID',
        ), actor)
        paid_partner_payouts = apply_request_scope_filter(paid_partner_payouts, request, 'delivery')
        paid_partner_payouts = apply_range_filter(
            paid_partner_payouts, request, 'paid_at'
        ).aggregate(total=Sum('partner_fee'))['total'] or 0

        return Response({
            **self._order_totals(completed_orders),
            'pending_payouts': pending_merchant_payouts + pending_partner_payouts,
            'paid_payouts': paid_merchant_payouts + paid_partner_payouts,
            'today': self._order_totals(completed_orders.filter(created_at__date=now.date())),
            'week': self._order_totals(completed_orders.filter(
                created_at__date__gte=(now - timedelta(days=7)).date()
            )),
            'month': self._order_totals(completed_orders.filter(
                created_at__year=now.year,
                created_at__month=now.month,
            )),
            'year': self._order_totals(completed_orders.filter(created_at__year=now.year)),
        })


class OperationsMerchantListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, VIEW_MERCHANTS)
        merchants = MerchantProfile.objects.select_related('user').prefetch_related(
            'user__owned_restaurants'
        ).order_by('is_verified', '-user__date_joined')
        merchants = scoped_merchant_queryset(merchants, actor)
        merchants = apply_request_scope_filter(merchants, request, 'merchant')
        filter_status = request.query_params.get('status')
        if filter_status == 'pending':
            merchants = merchants.filter(
                is_verified=False,
                verification_status__in=('PENDING', 'SUBMITTED'),
            )
        elif filter_status == 'verified':
            merchants = merchants.filter(is_verified=True)
        elif filter_status in ('rejected', 'suspended'):
            merchants = merchants.filter(verification_status=filter_status.upper())
        merchants = apply_range_filter(merchants, request, 'user__date_joined')
        return Response(OperationsMerchantSerializer(merchants, many=True).data)


class OperationsMerchantStatusView(APIView):
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def patch(self, request, merchant_id):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, MANAGE_VERIFICATIONS)
        if not isinstance(request.data.get('is_verified'), bool):
            return Response(
                {'is_verified': ['Enter true to approve or false to suspend.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        merchant = MerchantProfile.objects.select_for_update().select_related(
            'user'
        ).filter(id=merchant_id).first()
        if not merchant:
            return Response(
                {'detail': 'Merchant not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not scoped_merchant_queryset(
            MerchantProfile.objects.filter(id=merchant.id),
            actor,
        ).exists():
            return Response(
                {'detail': 'Merchant not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        is_verified = request.data['is_verified']
        if is_verified:
            missing = merchant_missing_requirements(merchant.user)
            if missing:
                return Response(
                    {'documents': missing},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            approve_merchant(merchant, request.user)
        else:
            reason = request.data.get('rejection_reason', '').strip()
            reject_merchant(merchant, request.user, reason)
        merchant = MerchantProfile.objects.select_related('user').prefetch_related(
            'user__owned_restaurants'
        ).get(id=merchant.id)
        return Response(OperationsMerchantSerializer(merchant).data)


class OperationsPartnerListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, VIEW_RIDERS)
        partners = DeliveryPartner.objects.select_related('user').annotate(
            delivery_count=Count('deliveries')
        ).order_by('is_verified', '-user__date_joined')
        partners = scoped_partner_queryset(partners, actor)
        partners = apply_request_scope_filter(partners, request, 'partner')
        filter_status = request.query_params.get('status')
        if filter_status == 'pending':
            partners = partners.filter(
                is_verified=False,
                verification_status__in=('PENDING', 'SUBMITTED'),
            )
        elif filter_status == 'verified':
            partners = partners.filter(is_verified=True)
        elif filter_status in ('rejected', 'suspended'):
            partners = partners.filter(verification_status=filter_status.upper())
        partners = apply_range_filter(partners, request, 'user__date_joined')
        return Response(OperationsPartnerSerializer(partners, many=True).data)


class OperationsStaffListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, VIEW_VERIFICATIONS)
        staff = (
            MerchantStaffMember.objects
            .select_related(
                'merchant',
                'merchant__market',
                'user',
                'verification_reviewed_by',
            )
            .prefetch_related(
                'branch_access__branch__market',
                'branch_access__branch__city_ref',
                'branch_access__branch__area_ref',
            )
            .order_by('verification_status', 'membership_status', '-created_at')
        )
        staff = scoped_staff_queryset(staff, actor)
        staff = apply_request_scope_filter(staff, request, 'staff')
        merchant_id = request.query_params.get('merchant_id')
        if merchant_id:
            staff = staff.filter(merchant_id=merchant_id)
        role = request.query_params.get('role')
        if role:
            staff = staff.filter(role=role)
        membership_status = request.query_params.get('membership_status')
        if membership_status:
            staff = staff.filter(membership_status=membership_status)
        verification_status = request.query_params.get('verification_status')
        if verification_status:
            staff = staff.filter(verification_status=verification_status)
        branch_id = request.query_params.get('branch_id')
        if branch_id:
            staff = staff.filter(branch_access__branch_id=branch_id)
        country_code = request.query_params.get('country_code')
        if country_code:
            country_code = country_code.upper()
            staff = staff.filter(
                Q(merchant__market__country_code=country_code)
                | Q(branch_access__branch__country_code=country_code)
                | Q(branch_access__branch__market__country_code=country_code)
            )
        market = request.query_params.get('market')
        if market:
            market_filter = (
                Q(merchant__market__slug=market)
                | Q(branch_access__branch__market__slug=market)
            )
            if str(market).isdigit():
                market_filter |= (
                    Q(merchant__market_id=market)
                    | Q(branch_access__branch__market_id=market)
                )
            staff = staff.filter(market_filter)
        staff = apply_range_filter(staff.distinct(), request, 'created_at')
        return Response(OperationsStaffSerializer(staff, many=True).data)


class OperationsMerchantRiderListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, VIEW_RIDERS)
        riders = MerchantRider.objects.select_related(
            'merchant__user',
            'partner__user',
            'home_restaurant',
        ).order_by('status', 'merchant__business_name', 'partner__partner_name')
        if not actor.is_global_scope:
            riders = riders.filter(
                models.Q(merchant__in=scoped_merchant_queryset(MerchantProfile.objects.all(), actor))
                | models.Q(home_restaurant__in=scoped_branch_queryset(actor))
            ).distinct()
        riders = apply_request_scope_filter(riders, request, 'partner')
        return Response(OperationsMerchantRiderSerializer(riders, many=True).data)


class OperationsFulfillmentRequestListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, VIEW_SUPPORT)
        requests = (
            MerchantFulfillmentRequest.objects
            .select_related(
                'order',
                'requesting_merchant__user',
                'fulfilling_merchant__user',
                'requested_by',
                'responded_by',
                'resolved_by',
                'cancelled_by',
            )
            .prefetch_related('events__actor')
            .order_by('-created_at')
        )
        if not actor.is_global_scope:
            requests = requests.filter(order__in=scoped_order_queryset(Order.objects.all(), actor))
        requests = requests.filter(
            order__in=apply_request_scope_filter(scoped_order_queryset(Order.objects.all(), actor), request, 'order')
        ) if _has_request_scope(request) else requests
        status_filter = request.query_params.get('status')
        if status_filter in dict(MerchantFulfillmentRequest.STATUS_CHOICES):
            requests = requests.filter(status=status_filter)
        requests = apply_range_filter(requests, request, 'created_at')
        return Response(
            OperationsFulfillmentRequestSerializer(requests, many=True).data
        )


class OperationsFulfillmentRequestActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=(
        'CANCEL',
        'RESOLVE',
        'OVERRIDE_STATUS',
        'ADD_NOTE',
    ))
    internal_status = serializers.ChoiceField(
        choices=(
            'REQUESTED',
            MerchantFulfillmentRequest.INTERNAL_STATUS_ACCEPTED,
            MerchantFulfillmentRequest.INTERNAL_STATUS_IN_PROGRESS,
            MerchantFulfillmentRequest.INTERNAL_STATUS_READY_FOR_HANDOFF,
            MerchantFulfillmentRequest.INTERNAL_STATUS_UNABLE_TO_FULFILL,
            MerchantFulfillmentRequest.INTERNAL_STATUS_RESOLVED,
            MerchantFulfillmentRequest.INTERNAL_STATUS_CANCELLED,
        ),
        required=False,
    )
    note = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs['action'] == 'OVERRIDE_STATUS' and not attrs.get('internal_status'):
            raise serializers.ValidationError({
                'internal_status': ['This field is required for OVERRIDE_STATUS.'],
            })
        if attrs['action'] == 'ADD_NOTE' and not attrs.get('note', '').strip():
            raise serializers.ValidationError({
                'note': ['This field is required for ADD_NOTE.'],
            })
        return attrs


class OperationsFulfillmentRequestDetailView(APIView):
    permission_classes = [IsAdminUser]

    resolvable_statuses = {
        MerchantFulfillmentRequest.INTERNAL_STATUS_READY_FOR_HANDOFF,
        MerchantFulfillmentRequest.INTERNAL_STATUS_UNABLE_TO_FULFILL,
    }
    terminal_statuses = {
        MerchantFulfillmentRequest.INTERNAL_STATUS_RESOLVED,
        MerchantFulfillmentRequest.INTERNAL_STATUS_CANCELLED,
        MerchantFulfillmentRequest.INTERNAL_STATUS_REJECTED,
    }
    override_status_map = {
        'REQUESTED': MerchantFulfillmentRequest.INTERNAL_STATUS_PENDING,
        MerchantFulfillmentRequest.INTERNAL_STATUS_ACCEPTED: (
            MerchantFulfillmentRequest.INTERNAL_STATUS_ACCEPTED
        ),
        MerchantFulfillmentRequest.INTERNAL_STATUS_IN_PROGRESS: (
            MerchantFulfillmentRequest.INTERNAL_STATUS_IN_PROGRESS
        ),
        MerchantFulfillmentRequest.INTERNAL_STATUS_READY_FOR_HANDOFF: (
            MerchantFulfillmentRequest.INTERNAL_STATUS_READY_FOR_HANDOFF
        ),
        MerchantFulfillmentRequest.INTERNAL_STATUS_UNABLE_TO_FULFILL: (
            MerchantFulfillmentRequest.INTERNAL_STATUS_UNABLE_TO_FULFILL
        ),
        MerchantFulfillmentRequest.INTERNAL_STATUS_RESOLVED: (
            MerchantFulfillmentRequest.INTERNAL_STATUS_RESOLVED
        ),
        MerchantFulfillmentRequest.INTERNAL_STATUS_CANCELLED: (
            MerchantFulfillmentRequest.INTERNAL_STATUS_CANCELLED
        ),
    }

    def append_operations_note(self, fulfillment_request, user, note):
        if not note:
            return
        timestamp = timezone.now().isoformat()
        entry = f'[{timestamp}] {user.username}: {note}'
        if fulfillment_request.operations_note:
            fulfillment_request.operations_note = (
                f'{fulfillment_request.operations_note}\n{entry}'
            )
        else:
            fulfillment_request.operations_note = entry

    def create_event(self, fulfillment_request, user, event_type, from_status, to_status, note):
        MerchantFulfillmentRequestEvent.objects.create(
            fulfillment_request=fulfillment_request,
            event_type=event_type,
            from_status=from_status or '',
            to_status=to_status or '',
            actor=user,
            note=note,
            metadata={
                'operations_action': True,
                'customer_order_status_unchanged': True,
                'payment_unchanged': True,
                'payout_unchanged': True,
                'dispatch_unchanged': True,
                'customer_visible': False,
            },
        )

    @transaction.atomic
    def patch(self, request, fulfillment_request_id):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, MANAGE_SUPPORT)
        serializer = OperationsFulfillmentRequestActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data['action']
        note = serializer.validated_data.get('note', '').strip()
        fulfillment_request = (
            MerchantFulfillmentRequest.objects
            .select_for_update(of=('self',))
            .select_related(
                'order',
                'requesting_merchant__user',
                'fulfilling_merchant__user',
                'requested_by',
                'responded_by',
                'resolved_by',
                'cancelled_by',
            )
            .prefetch_related('events__actor')
            .filter(id=fulfillment_request_id)
            .first()
        )
        if not fulfillment_request:
            return Response(
                {'detail': 'Fulfillment request not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not scoped_order_queryset(
            Order.objects.filter(id=fulfillment_request.order_id),
            actor,
        ).exists():
            return Response(
                {'detail': 'Fulfillment request not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        previous_internal_status = fulfillment_request.internal_status
        update_fields = ['updated_at']

        if action == 'ADD_NOTE':
            self.append_operations_note(fulfillment_request, request.user, note)
            update_fields.append('operations_note')
            fulfillment_request.save(update_fields=update_fields)
            self.create_event(
                fulfillment_request,
                request.user,
                MerchantFulfillmentRequestEvent.EVENT_NOTE_ADDED,
                previous_internal_status,
                previous_internal_status,
                note,
            )
            return Response(
                OperationsFulfillmentRequestSerializer(fulfillment_request).data
            )

        if action == 'CANCEL':
            if previous_internal_status in self.terminal_statuses:
                return Response(
                    {'action': ['Terminal fulfillment requests cannot be cancelled.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            fulfillment_request.status = MerchantFulfillmentRequest.STATUS_CANCELLED
            fulfillment_request.internal_status = (
                MerchantFulfillmentRequest.INTERNAL_STATUS_CANCELLED
            )
            fulfillment_request.cancelled_by = request.user
            fulfillment_request.cancelled_at = timezone.now()
            self.append_operations_note(fulfillment_request, request.user, note)
            update_fields.extend([
                'status', 'internal_status', 'cancelled_by', 'cancelled_at',
                'operations_note',
            ])
            fulfillment_request.save(update_fields=update_fields)
            self.create_event(
                fulfillment_request,
                request.user,
                MerchantFulfillmentRequestEvent.EVENT_INTERNAL_STATUS_CHANGED,
                previous_internal_status,
                fulfillment_request.internal_status,
                note or 'Fulfillment request cancelled by operations.',
            )
            return Response(
                OperationsFulfillmentRequestSerializer(fulfillment_request).data
            )

        if action == 'RESOLVE':
            if previous_internal_status not in self.resolvable_statuses:
                return Response(
                    {
                        'action': [
                            'Operations can resolve only READY_FOR_HANDOFF or '
                            'UNABLE_TO_FULFILL requests unless using OVERRIDE_STATUS.'
                        ],
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not fulfillment_request.settlement_preview:
                ensure_fulfillment_settlement_preview(
                    fulfillment_request,
                    actor=request.user,
                )
            fulfillment_request.internal_status = (
                MerchantFulfillmentRequest.INTERNAL_STATUS_RESOLVED
            )
            fulfillment_request.resolved_by = request.user
            fulfillment_request.resolved_at = timezone.now()
            self.append_operations_note(fulfillment_request, request.user, note)
            update_fields.extend([
                'internal_status', 'resolved_by', 'resolved_at',
                'operations_note',
            ])
            fulfillment_request.save(update_fields=update_fields)
            self.create_event(
                fulfillment_request,
                request.user,
                MerchantFulfillmentRequestEvent.EVENT_INTERNAL_STATUS_CHANGED,
                previous_internal_status,
                fulfillment_request.internal_status,
                note or 'Fulfillment request resolved by operations.',
            )
            return Response(
                OperationsFulfillmentRequestSerializer(fulfillment_request).data
            )

        override_value = serializer.validated_data['internal_status']
        next_internal_status = self.override_status_map[override_value]
        fulfillment_request.internal_status = next_internal_status
        if next_internal_status == MerchantFulfillmentRequest.INTERNAL_STATUS_CANCELLED:
            fulfillment_request.status = MerchantFulfillmentRequest.STATUS_CANCELLED
            fulfillment_request.cancelled_by = request.user
            fulfillment_request.cancelled_at = timezone.now()
            update_fields.extend(['status', 'cancelled_by', 'cancelled_at'])
        elif next_internal_status == MerchantFulfillmentRequest.INTERNAL_STATUS_RESOLVED:
            fulfillment_request.resolved_by = request.user
            fulfillment_request.resolved_at = timezone.now()
            update_fields.extend(['resolved_by', 'resolved_at'])
        self.append_operations_note(fulfillment_request, request.user, note)
        update_fields.extend(['internal_status', 'operations_note'])
        fulfillment_request.save(update_fields=update_fields)
        self.create_event(
            fulfillment_request,
            request.user,
            MerchantFulfillmentRequestEvent.EVENT_INTERNAL_STATUS_CHANGED,
            previous_internal_status,
            next_internal_status,
            note or f'Operations override to {override_value}.',
        )
        return Response(
            OperationsFulfillmentRequestSerializer(fulfillment_request).data
        )


class OperationsPartnerStatusView(APIView):
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def patch(self, request, partner_id):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, MANAGE_VERIFICATIONS)
        if not isinstance(request.data.get('is_verified'), bool):
            return Response(
                {'is_verified': ['Enter true to approve or false to suspend.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        partner = DeliveryPartner.objects.select_for_update().select_related(
            'user'
        ).filter(id=partner_id).first()
        if not partner:
            return Response(
                {'detail': 'Delivery partner not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not scoped_partner_queryset(
            DeliveryPartner.objects.filter(id=partner.id),
            actor,
        ).exists():
            return Response(
                {'detail': 'Delivery partner not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        is_verified = request.data['is_verified']
        if is_verified:
            missing = partner_missing_requirements(partner.user)
            if missing:
                return Response(
                    {'documents': missing},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            approve_partner(partner, request.user)
        else:
            reason = request.data.get('rejection_reason', '').strip()
            reject_partner(partner, request.user, reason)
        partner = DeliveryPartner.objects.select_related('user').annotate(
            delivery_count=Count('deliveries')
        ).get(id=partner.id)
        return Response(OperationsPartnerSerializer(partner).data)


class OperationsSupportTicketListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, VIEW_SUPPORT)
        tickets = SupportTicket.objects.select_related(
            'customer', 'order', 'order__payment'
        ).prefetch_related(
            models.Prefetch(
                'order__merchant_fulfillment_requests',
                queryset=MerchantFulfillmentRequest.objects.select_related(
                    'requesting_merchant__user',
                    'fulfilling_merchant__user',
                ).order_by('-created_at', '-id'),
                to_attr='prefetched_fulfillment_requests',
            )
        ).order_by('status', '-created_at')
        tickets = tickets.filter(order__in=scoped_order_queryset(Order.objects.all(), actor))
        tickets = tickets.filter(
            order__in=apply_request_scope_filter(scoped_order_queryset(Order.objects.all(), actor), request, 'order')
        ) if _has_request_scope(request) else tickets
        filter_status = request.query_params.get('status')
        if filter_status == 'open':
            tickets = tickets.filter(status__in=('OPEN', 'IN_REVIEW'))
        elif filter_status in dict(SupportTicket.STATUS_CHOICES):
            tickets = tickets.filter(status=filter_status)
        tickets = apply_range_filter(tickets, request, 'created_at')
        return Response(OperationsSupportTicketSerializer(tickets, many=True).data)


class OperationsSupportTicketStatusView(APIView):
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def patch(self, request, ticket_id):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, MANAGE_SUPPORT)
        new_status = request.data.get('status')
        resolution = request.data.get('resolution', '').strip()
        issue_refund = request.data.get('issue_refund', False)
        if new_status not in ('IN_REVIEW', 'RESOLVED', 'REJECTED'):
            return Response(
                {'status': ['Choose IN_REVIEW, RESOLVED, or REJECTED.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if new_status in ('RESOLVED', 'REJECTED') and not resolution:
            return Response(
                {'resolution': ['Explain the resolution to the customer.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if issue_refund and new_status != 'RESOLVED':
            return Response(
                {'issue_refund': ['Refunds require a resolved ticket.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ticket = SupportTicket.objects.select_for_update().select_related(
            'customer', 'order'
        ).filter(id=ticket_id).first()
        if not ticket:
            return Response(
                {'detail': 'Support ticket not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not scoped_order_queryset(
            Order.objects.filter(id=ticket.order_id),
            actor,
        ).exists():
            return Response(
                {'detail': 'Support ticket not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if issue_refund:
            order = Order.objects.select_for_update().get(id=ticket.order_id)
            if order.merchant_payout_status == 'PAID':
                return Response(
                    {'issue_refund': [
                        'Merchant settlement is already paid. Recover or reverse it before refunding.'
                    ]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            payment = Payment.objects.select_for_update().filter(
                order=order
            ).first()
            if not payment or payment.status not in ('SUCCESS', 'REFUNDED'):
                return Response(
                    {'issue_refund': ['Only a successful payment can be refunded.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if payment.status == 'SUCCESS':
                payment.status = 'REFUNDED'
                payment.save(update_fields=['status'])
            ticket.refund_status = 'APPROVED'
            ticket.refunded_amount = order.total_amount
            order.merchant_payout_status = 'CANCELLED'
            order.save(update_fields=['merchant_payout_status', 'updated_at'])
            record_refund_audit(
                order=order,
                payment=payment,
                amount=order.total_amount,
                reason=resolution,
                actor=request.user,
                support_ticket=ticket,
            )
            notify_payment_event(
                payment,
                'refund_completed',
                actor=request.user,
                support_ticket=ticket,
            )
        elif (
            new_status in ('RESOLVED', 'REJECTED')
            and ticket.refund_status == 'REQUESTED'
        ):
            ticket.refund_status = 'REJECTED'

        ticket.status = new_status
        ticket.resolution = resolution
        ticket.save(update_fields=(
            'status', 'resolution', 'refund_status', 'refunded_amount', 'updated_at'
        ))
        from notifications.events import notify_support_event
        notify_support_event(
            ticket,
            'resolved' if new_status == 'RESOLVED' else 'updated',
            actor=request.user,
        )
        ticket = SupportTicket.objects.select_related(
            'customer', 'order', 'order__payment'
        ).get(id=ticket.id)
        return Response(OperationsSupportTicketSerializer(ticket).data)


class OperationsReviewPhotoListView(APIView):
    permission_classes = [IsAdminUser]

    def get_queryset(self, request):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, VIEW_SUPPORT)
        photos = (
            ReviewPhoto.objects
            .select_related(
                'review__customer',
                'review__order',
                'review__restaurant',
                'review__restaurant__owner__merchant_profile',
                'review__restaurant__market',
                'review__restaurant__city_ref',
                'review__restaurant__area_ref',
                'uploaded_by',
                'reviewed_by',
            )
            .order_by('-created_at', '-id')
        )
        photos = scoped_review_photo_queryset(photos, actor)
        photos = apply_request_scope_filter(photos, request, 'review_photo')
        status_filter = request.query_params.get('status')
        if status_filter:
            photos = photos.filter(status__iexact=status_filter)
        restaurant = request.query_params.get('restaurant') or request.query_params.get('branch')
        customer = request.query_params.get('customer')
        date_from = parse_bound(request.query_params.get('date_from'), end=False)
        date_to = parse_bound(request.query_params.get('date_to'), end=True)
        if restaurant:
            photos = photos.filter(review__restaurant_id=restaurant)
        if customer:
            photos = photos.filter(review__customer_id=customer)
        if date_from:
            photos = photos.filter(created_at__gte=date_from)
        if date_to:
            photos = photos.filter(created_at__lte=date_to)
        return photos

    def get(self, request):
        return Response(
            OperationsReviewPhotoSerializer(
                self.get_queryset(request),
                many=True,
                context={'request': request},
            ).data
        )


class OperationsReviewPhotoDetailView(APIView):
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def patch(self, request, photo_id):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, MANAGE_SUPPORT)
        photo = (
            ReviewPhoto.objects
            .select_for_update()
            .filter(id=photo_id)
            .first()
        )
        if not photo or not scoped_review_photo_queryset(
            ReviewPhoto.objects.filter(id=photo_id),
            actor,
        ).exists():
            return Response({'detail': 'Review photo not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = OperationsReviewPhotoModerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data['action']
        reason = serializer.validated_data.get('reason', '')
        if action == 'APPROVE':
            photo.status = ReviewPhoto.STATUS_APPROVED
            photo.moderation_reason = ''
        elif action == 'REJECT':
            photo.status = ReviewPhoto.STATUS_REJECTED
            photo.moderation_reason = reason
        else:
            photo.status = ReviewPhoto.STATUS_HIDDEN
            photo.moderation_reason = reason
        photo.reviewed_by = request.user
        photo.reviewed_at = timezone.now()
        photo.save(update_fields=[
            'status',
            'moderation_reason',
            'reviewed_by',
            'reviewed_at',
            'updated_at',
        ])
        photo = (
            ReviewPhoto.objects
            .select_related(
                'review__customer',
                'review__order',
                'review__restaurant',
                'review__restaurant__owner__merchant_profile',
                'review__restaurant__market',
                'review__restaurant__city_ref',
                'review__restaurant__area_ref',
                'uploaded_by',
                'reviewed_by',
            )
            .get(id=photo.id)
        )
        schedule_review_photo_moderation_notification(
            photo,
            action,
            actor=request.user,
        )
        return Response(
            OperationsReviewPhotoSerializer(
                photo,
                context={'request': request},
            ).data
        )


class OperationsPaymentProviderConfigListView(APIView):
    permission_classes = [IsAdminUser]

    def get_queryset(self, request):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, MANAGE_PROVIDER_CONFIG)
        queryset = (
            PaymentProviderConfig.objects
            .select_related('market', 'market__default_currency', 'updated_by')
            .order_by('country_code', 'payment_method', 'priority', 'provider_code')
        )
        queryset = filter_queryset_for_operations_actor(
            queryset,
            actor,
            PAYMENT_PROVIDER_SCOPE_FIELD_MAP,
        )
        filters = {
            'market_id': request.query_params.get('market'),
            'country_code': request.query_params.get('country_code'),
            'currency': request.query_params.get('currency'),
            'payment_method': request.query_params.get('payment_method'),
            'provider_code': request.query_params.get('provider_code'),
        }
        for field, value in filters.items():
            if value:
                queryset = queryset.filter(**{field: str(value).upper() if field != 'provider_code' else str(value).lower()})
        return queryset

    def get(self, request):
        actor = get_operations_actor(request.user)
        configs = self.get_queryset(request)
        markets = Market.objects.select_related('default_currency').filter(is_active=True).order_by('name')
        markets = filter_queryset_for_operations_actor(
            markets,
            actor,
            {'market': 'self', 'country': 'country_code'},
        ) if not actor.is_global_scope else markets
        return Response({
            'results': PaymentProviderConfigSerializer(configs, many=True).data,
            'markets': [
                {
                    'id': market.id,
                    'name': market.name,
                    'slug': market.slug,
                    'country_code': market.country_code,
                    'currency': market.default_currency.code,
                }
                for market in markets
            ],
            'providers': [
                provider_capability_payload(capability)
                for capability in available_provider_capabilities()
            ],
            'payment_methods': sorted(SUPPORTED_PAYMENT_METHODS),
        })

    @transaction.atomic
    def post(self, request):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, MANAGE_PROVIDER_CONFIG)
        serializer = PaymentProviderConfigSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        market = serializer.validated_data['market']
        if not filter_queryset_for_operations_actor(
            Market.objects.filter(id=market.id),
            actor,
            {'market': 'self', 'country': 'country_code'},
        ).exists():
            return Response(
                {'market': ['You do not have access to this market.']},
                status=status.HTTP_403_FORBIDDEN,
            )
        config = serializer.save(updated_by=request.user)
        if config.is_preferred:
            PaymentProviderConfig.objects.filter(
                market=config.market,
                payment_method=config.payment_method,
                is_preferred=True,
            ).exclude(id=config.id).update(is_preferred=False)
        return Response(
            PaymentProviderConfigSerializer(config).data,
            status=status.HTTP_201_CREATED,
        )


class OperationsOfferListView(APIView):
    permission_classes = [IsAdminUser]

    def get_queryset(self, request):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, MANAGE_PROVIDER_CONFIG)
        offers = Offer.objects.select_related(
            'market', 'market__default_currency',
        ).order_by('-is_active', 'code')
        if actor.is_global_scope:
            return offers
        scoped_markets = filter_queryset_for_operations_actor(
            Market.objects.all(),
            actor,
            {'market': 'self', 'country': 'country_code'},
        )
        return offers.filter(market__in=scoped_markets)

    def get_markets(self, request):
        actor = get_operations_actor(request.user)
        markets = Market.objects.select_related('default_currency').filter(
            is_active=True,
        ).order_by('name')
        if actor.is_global_scope:
            return markets
        return filter_queryset_for_operations_actor(
            markets,
            actor,
            {'market': 'self', 'country': 'country_code'},
        )

    def get(self, request):
        markets = self.get_markets(request)
        return Response({
            'results': OperationsOfferSerializer(self.get_queryset(request), many=True).data,
            'markets': [
                {
                    'id': market.id,
                    'name': market.name,
                    'slug': market.slug,
                    'country_code': market.country_code,
                    'currency': market.default_currency.code,
                }
                for market in markets
            ],
        })

    @transaction.atomic
    def post(self, request):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, MANAGE_PROVIDER_CONFIG)
        serializer = OperationsOfferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        market = serializer.validated_data.get('market')
        if not actor.is_global_scope and not market:
            return Response(
                {'market': ['Choose a market for scoped operations users.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if market and not filter_queryset_for_operations_actor(
            Market.objects.filter(id=market.id),
            actor,
            {'market': 'self', 'country': 'country_code'},
        ).exists():
            return Response(
                {'market': ['You do not have access to this market.']},
                status=status.HTTP_403_FORBIDDEN,
            )
        offer = serializer.save()
        return Response(
            OperationsOfferSerializer(offer).data,
            status=status.HTTP_201_CREATED,
        )


class OperationsOfferDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get_object(self, request, offer_id):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, MANAGE_PROVIDER_CONFIG)
        offers = Offer.objects.select_related('market', 'market__default_currency')
        if actor.is_global_scope:
            return offers.get(id=offer_id)
        scoped_markets = filter_queryset_for_operations_actor(
            Market.objects.all(),
            actor,
            {'market': 'self', 'country': 'country_code'},
        )
        return offers.filter(market__in=scoped_markets).get(id=offer_id)

    @transaction.atomic
    def patch(self, request, offer_id):
        try:
            offer = self.get_object(request, offer_id)
        except Offer.DoesNotExist:
            return Response({'detail': 'Promo code not found.'}, status=status.HTTP_404_NOT_FOUND)
        actor = get_operations_actor(request.user)
        serializer = OperationsOfferSerializer(offer, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        market = serializer.validated_data.get('market', offer.market)
        if market and not filter_queryset_for_operations_actor(
            Market.objects.filter(id=market.id),
            actor,
            {'market': 'self', 'country': 'country_code'},
        ).exists():
            return Response(
                {'market': ['You do not have access to this market.']},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not actor.is_global_scope and not market:
            return Response(
                {'market': ['Choose a market for scoped operations users.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        offer = serializer.save()
        return Response(OperationsOfferSerializer(offer).data)


class OperationsPaymentProviderConfigDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get_object(self, config_id):
        return PaymentProviderConfig.objects.select_related(
            'market', 'market__default_currency', 'updated_by',
        ).get(id=config_id)

    @transaction.atomic
    def patch(self, request, config_id):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, MANAGE_PROVIDER_CONFIG)
        try:
            config = self.get_object(config_id)
        except PaymentProviderConfig.DoesNotExist:
            return Response({'detail': 'Payment provider config not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not filter_queryset_for_operations_actor(
            PaymentProviderConfig.objects.filter(id=config.id),
            actor,
            PAYMENT_PROVIDER_SCOPE_FIELD_MAP,
        ).exists():
            return Response(
                {'detail': 'Payment provider config not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = PaymentProviderConfigSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        market = serializer.validated_data.get('market') or config.market
        if not filter_queryset_for_operations_actor(
            Market.objects.filter(id=market.id),
            actor,
            {'market': 'self', 'country': 'country_code'},
        ).exists():
            return Response(
                {'market': ['You do not have access to this market.']},
                status=status.HTTP_403_FORBIDDEN,
            )
        config = serializer.save(updated_by=request.user)
        if config.is_preferred:
            PaymentProviderConfig.objects.filter(
                market=config.market,
                payment_method=config.payment_method,
                is_preferred=True,
            ).exclude(id=config.id).update(is_preferred=False)
        return Response(PaymentProviderConfigSerializer(config).data)


class OperationsLedgerView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, VIEW_LEDGER)
        transactions = LedgerTransaction.objects.select_related('market')
        transactions = scoped_ledger_queryset(transactions, actor)
        transactions = apply_request_scope_filter(transactions, request, 'ledger')
        total_transactions = transactions.count()
        unbalanced_transactions = transactions.exclude(
            debit_total=models.F('credit_total')
        ).count()
        duplicate_idempotency_keys = (
            transactions
            .values('idempotency_key')
            .annotate(count=Count('id'))
            .filter(count__gt=1)
            .count()
        )

        platform_fee_total = decimal_sum(
            transactions.filter(transaction_type=LedgerTransaction.TYPE_PLATFORM_FEE)
        )
        if platform_fee_total == Decimal('0.00'):
            for metadata in transactions.filter(
                transaction_type=LedgerTransaction.TYPE_ORDER_GROSS,
                source_type='order',
            ).values_list('metadata', flat=True):
                platform_fee_total += Decimal(
                    str(metadata.get('platform_fee') or '0.00')
                )

        failed_financial_events = (
            RefundAudit.objects.filter(
                ledger_transaction__in=transactions,
                status=RefundAudit.STATUS_FAILED,
            ).count()
            + MerchantPayoutAudit.objects.filter(
                ledger_transaction__in=transactions,
                status=MerchantPayoutAudit.STATUS_FAILED,
            ).count()
            + PartnerPayoutAudit.objects.filter(
                ledger_transaction__in=transactions,
                status=PartnerPayoutAudit.STATUS_FAILED,
            ).count()
        )

        return Response({
            'platform_summary': {
                'total_gross_revenue': decimal_sum(
                    transactions.filter(transaction_type=LedgerTransaction.TYPE_ORDER_GROSS)
                ),
                'total_platform_fees': platform_fee_total,
                'total_merchant_payouts': decimal_sum(
                    transactions.filter(transaction_type=LedgerTransaction.TYPE_MERCHANT_PAYOUT)
                ),
                'total_partner_payouts': decimal_sum(
                    transactions.filter(transaction_type=LedgerTransaction.TYPE_PARTNER_DELIVERY_FEE)
                ),
                'total_refunds': decimal_sum(
                    transactions.filter(transaction_type=LedgerTransaction.TYPE_REFUND)
                ),
                'total_settlement_preview_amount': decimal_sum(
                    transactions.filter(transaction_type=LedgerTransaction.TYPE_FULFILLMENT_PREVIEW)
                ),
                'ledger_transaction_count': total_transactions,
                'ledger_entry_count': sum(
                    transaction_item.entries.count()
                    for transaction_item in transactions.prefetch_related('entries')
                ),
            },
            'financial_health': {
                'balanced_transactions': total_transactions - unbalanced_transactions,
                'unbalanced_transactions': unbalanced_transactions,
                'failed_financial_events': failed_financial_events,
                'duplicate_idempotency_attempts_prevented': duplicate_idempotency_keys,
                'idempotency_unique_keys_enforced': True,
                'status': (
                    'LEDGER_VERIFIED'
                    if unbalanced_transactions == 0
                    else 'FINANCIAL_INTEGRITY_WARNING'
                ),
            },
            'breakdowns': {
                'by_country': group_ledger_amounts('country_code', transactions),
                'by_market': group_ledger_amounts('market__name', transactions),
                'by_currency': group_ledger_amounts('currency', transactions),
                'by_provider': group_ledger_amounts('provider_code', transactions),
                'by_transaction_type': group_ledger_amounts('transaction_type', transactions),
            },
            'recent_activity': {
                'ledger_transactions': [
                    ledger_transaction_payload(transaction_item)
                    for transaction_item in transactions.order_by('-created_at', '-id')[:15]
                ],
                'refund_audits': [
                    refund_audit_payload(audit)
                    for audit in RefundAudit.objects.select_related(
                        'ledger_transaction'
                    ).filter(ledger_transaction__in=transactions).order_by('-created_at', '-id')[:10]
                ],
                'merchant_payout_audits': [
                    merchant_payout_audit_payload(audit)
                    for audit in MerchantPayoutAudit.objects.select_related(
                        'merchant', 'market', 'ledger_transaction'
                    ).filter(ledger_transaction__in=transactions).order_by('-created_at', '-id')[:10]
                ],
                'partner_payout_audits': [
                    partner_payout_audit_payload(audit)
                    for audit in PartnerPayoutAudit.objects.select_related(
                        'delivery', 'partner', 'market', 'ledger_transaction'
                    ).filter(ledger_transaction__in=transactions).order_by('-created_at', '-id')[:10]
                ],
                'fulfillment_preview_ledger_entries': [
                    ledger_transaction_payload(transaction_item)
                    for transaction_item in transactions.filter(
                        transaction_type=LedgerTransaction.TYPE_FULFILLMENT_PREVIEW,
                    ).order_by('-created_at', '-id')[:10]
                ],
            },
        })


class OperationsDispatchListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, VIEW_DISPATCH)
        deliveries = Delivery.objects.filter(
            order__status='READY_FOR_PICKUP',
        ).select_related(
            'order__customer', 'order__pickup_branch', 'delivery_partner__user'
        ).prefetch_related('order__items__food__restaurant').order_by('delivery_date')
        deliveries = scoped_delivery_queryset(deliveries, actor)
        deliveries = apply_request_scope_filter(deliveries, request, 'delivery')
        deliveries = apply_range_filter(deliveries, request, 'delivery_date')
        return Response(OperationsDispatchSerializer(deliveries, many=True).data)


class OperationsDispatchAssignView(APIView):
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def patch(self, request, delivery_id):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, MANAGE_DISPATCH)
        partner_id = request.data.get('partner_id')
        delivery = Delivery.objects.select_for_update().select_related(
            'order__customer'
        ).filter(
            id=delivery_id,
            order__status='READY_FOR_PICKUP',
            status='ASSIGNED',
        ).first()
        if not delivery:
            return Response(
                {'detail': 'Only orders waiting for pickup can be assigned.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not scoped_delivery_queryset(
            Delivery.objects.filter(id=delivery.id),
            actor,
        ).exists():
            return Response(
                {'detail': 'Only orders waiting for pickup can be assigned.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        partner = DeliveryPartner.objects.select_for_update().select_related(
            'user'
        ).filter(
            id=partner_id,
            is_verified=True,
            is_available=True,
        ).first()
        if not partner:
            return Response(
                {'partner_id': ['Choose a verified, available partner.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not scoped_partner_queryset(
            DeliveryPartner.objects.filter(id=partner.id),
            actor,
        ).exists():
            return Response(
                {'partner_id': ['Choose a verified, available partner.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        previous_partner = delivery.delivery_partner
        if previous_partner_id := delivery.delivery_partner_id:
            if previous_partner_id == partner.id:
                return Response(
                    {'partner_id': ['This partner is already assigned.']},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            previous_partner = DeliveryPartner.objects.select_for_update().get(
                id=previous_partner_id
            )
            previous_partner.is_available = previous_partner.is_verified
            previous_partner.save(update_fields=['is_available'])

        delivery.delivery_partner = partner
        delivery.assigned_at = timezone.now()
        delivery.partner_fee = delivery.order.delivery_fee
        delivery.payout_status = 'PENDING'
        delivery.paid_at = None
        delivery.save(update_fields=(
            'delivery_partner', 'assigned_at', 'partner_fee',
            'payout_status', 'paid_at',
        ))
        partner.is_available = False
        partner.save(update_fields=['is_available'])
        notify_order_event(
            delivery.order,
            'rider_assigned',
            actor=request.user,
            delivery=delivery,
        )
        delivery = Delivery.objects.select_related(
            'order__customer', 'delivery_partner__user'
        ).prefetch_related('order__items__food__restaurant').get(id=delivery.id)
        return Response(OperationsDispatchSerializer(delivery).data)


class OperationsPartnerPayoutListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, VIEW_FINANCE)
        payouts = Delivery.objects.filter(
            delivery_partner__isnull=False,
            status='DELIVERED',
        ).select_related(
            'order', 'delivery_partner__user'
        ).order_by('payout_status', '-delivery_date')
        payouts = scoped_delivery_queryset(payouts, actor)
        payouts = apply_request_scope_filter(payouts, request, 'delivery')
        payout_status = request.query_params.get('status')
        if payout_status in dict(Delivery.PAYOUT_STATUS_CHOICES):
            payouts = payouts.filter(payout_status=payout_status)
        payouts = apply_range_filter(payouts, request, 'delivery_date')
        return Response(OperationsPartnerPayoutSerializer(payouts, many=True).data)


class OperationsPartnerPayoutPayView(APIView):
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def post(self, request, delivery_id):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, VIEW_FINANCE)
        delivery = Delivery.objects.select_for_update().select_related(
            'order'
        ).filter(
            id=delivery_id,
            status='DELIVERED',
            payout_status='AVAILABLE',
            delivery_partner__isnull=False,
        ).first()
        if not delivery:
            return Response(
                {'detail': 'This delivery has no available payout.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not scoped_delivery_queryset(
            Delivery.objects.filter(id=delivery.id),
            actor,
        ).exists():
            return Response(
                {'detail': 'This delivery has no available payout.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        delivery.payout_status = 'PAID'
        delivery.paid_at = timezone.now()
        delivery.save(update_fields=['payout_status', 'paid_at'])
        record_partner_payout_audit(
            delivery=delivery,
            status='PAID',
            actor=request.user,
        )
        notify_payout_event(delivery, 'partner_paid', actor=request.user)
        return Response(OperationsPartnerPayoutSerializer(delivery).data)


class OperationsMerchantPayoutListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, VIEW_FINANCE)
        payouts = Order.objects.filter(
            status='DELIVERED',
            merchant_payout_status__in=('AVAILABLE', 'PAID'),
        ).prefetch_related(
            'items__food__restaurant__owner__merchant_profile'
        ).order_by('merchant_payout_status', '-updated_at')
        payouts = scoped_order_queryset(payouts, actor)
        payouts = apply_request_scope_filter(payouts, request, 'order')
        payout_status = request.query_params.get('status')
        if payout_status in dict(Order.MERCHANT_PAYOUT_STATUS_CHOICES):
            payouts = payouts.filter(merchant_payout_status=payout_status)
        payouts = apply_range_filter(payouts, request, 'created_at')
        return Response(OperationsMerchantPayoutSerializer(payouts, many=True).data)


class OperationsMerchantPayoutPayView(APIView):
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def post(self, request, order_id):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, VIEW_FINANCE)
        order = Order.objects.select_for_update().filter(
            id=order_id,
            status='DELIVERED',
            payment__status='SUCCESS',
            merchant_payout_status='AVAILABLE',
        ).first()
        if not order:
            return Response(
                {'detail': 'This order has no available merchant payout.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not scoped_order_queryset(
            Order.objects.filter(id=order.id),
            actor,
        ).exists():
            return Response(
                {'detail': 'This order has no available merchant payout.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        first_item = order.items.select_related(
            'food__restaurant__owner'
        ).first()
        merchant = first_item.food.restaurant.owner if first_item else None
        if not merchant:
            return Response(
                {'detail': 'This order has no merchant owner.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        order.merchant_payout_status = 'PAID'
        order.merchant_paid_at = timezone.now()
        order.save(update_fields=[
            'merchant_payout_status', 'merchant_paid_at', 'updated_at'
        ])
        record_merchant_payout_audit(
            order=order,
            status='PAID',
            actor=request.user,
        )
        notify_payout_event(order, 'merchant_paid', actor=request.user)
        order = Order.objects.prefetch_related(
            'items__food__restaurant__owner__merchant_profile'
        ).get(id=order.id)
        return Response(OperationsMerchantPayoutSerializer(order).data)

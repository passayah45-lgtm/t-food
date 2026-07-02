from decimal import Decimal, ROUND_HALF_UP
from math import asin, cos, radians, sin, sqrt
from django.conf import settings
from django.utils import timezone


FALLBACK_DISTANCE_KM = Decimal('999999')
SETTLEMENT_PREVIEW_LABEL = 'Preview Only — No Financial Settlement Has Been Applied'
SETTLEMENT_PREVIEW_METHOD = 'merchant_payout_70_30_v1'


def quantize_money(value):
    return Decimal(value or 0).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def money_string(value):
    return str(quantize_money(value))


def quantize_distance(value):
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def distance_km(latitude_a, longitude_a, latitude_b, longitude_b):
    coordinates = (latitude_a, longitude_a, latitude_b, longitude_b)
    if any(value is None for value in coordinates):
        return None
    lat1, lon1, lat2, lon2 = map(lambda value: radians(float(value)), coordinates)
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1
    haversine = (
        sin(delta_lat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    )
    distance = 6371 * 2 * asin(sqrt(haversine))
    return quantize_distance(distance)


def _distance_annotation_km(restaurant):
    distance = getattr(restaurant, 'gis_distance', None)
    if distance is None:
        return None
    if hasattr(distance, 'km'):
        return quantize_distance(distance.km)
    return quantize_distance(float(distance) / 1000)


def restaurant_delivery_distance(restaurant, latitude, longitude):
    annotated_distance = _distance_annotation_km(restaurant)
    if annotated_distance is not None:
        return annotated_distance
    return distance_km(
        restaurant.pickup_latitude,
        restaurant.pickup_longitude,
        latitude,
        longitude,
    )


def _can_use_postgis():
    return (
        settings.GEODJANGO_AVAILABLE
        and settings.DATABASES['default']['ENGINE']
        == 'django.contrib.gis.db.backends.postgis'
    )


def _annotate_gis_distance(queryset, latitude, longitude):
    if not _can_use_postgis():
        return queryset

    from django.contrib.gis.db.models.functions import Distance
    from django.contrib.gis.geos import Point

    user_point = Point(float(longitude), float(latitude), srid=4326)
    return queryset.annotate(gis_distance=Distance('pickup_point', user_point))


def restaurants_sorted_for_location(queryset, latitude, longitude):
    if _can_use_postgis():
        queryset = _annotate_gis_distance(queryset, latitude, longitude)

    restaurants = list(queryset)
    for restaurant in restaurants:
        restaurant.distance_km = restaurant_delivery_distance(
            restaurant,
            latitude,
            longitude,
        )
        if restaurant.distance_km is None:
            restaurant.is_serviceable = None
        else:
            restaurant.is_serviceable = restaurant.distance_km <= restaurant.delivery_radius_km

    restaurants.sort(
        key=lambda restaurant: (
            restaurant.distance_km is None,
            restaurant.distance_km
            if restaurant.distance_km is not None
            else FALLBACK_DISTANCE_KM,
            restaurant.rest_name.lower(),
        )
    )
    return restaurants


def _merchant_anchor_restaurant(merchant):
    restaurants = (
        merchant.user.owned_restaurants
        .filter(is_active=True)
        .order_by('id')
    )
    return (
        restaurants.filter(pickup_point__isnull=False).first()
        or restaurants.filter(
            pickup_latitude__isnull=False,
            pickup_longitude__isnull=False,
        ).first()
    )


def _restaurant_distance_to_anchor(restaurant, anchor):
    annotated_distance = _distance_annotation_km(restaurant)
    if annotated_distance is not None:
        return annotated_distance
    return distance_km(
        anchor.pickup_latitude,
        anchor.pickup_longitude,
        restaurant.pickup_latitude,
        restaurant.pickup_longitude,
    )


def find_nearby_merchants(merchant, radius_km=5):
    from restaurants.models import MerchantProfile, Restaurant

    anchor = _merchant_anchor_restaurant(merchant)
    if not anchor:
        return []

    restaurants = Restaurant.objects.filter(
        is_active=True,
        owner__merchant_profile__isnull=False,
    ).exclude(owner=merchant.user).select_related('owner__merchant_profile')
    if _can_use_postgis() and anchor.pickup_point:
        from django.contrib.gis.db.models.functions import Distance

        restaurants = restaurants.filter(
            pickup_point__isnull=False,
        ).annotate(gis_distance=Distance('pickup_point', anchor.pickup_point))
    else:
        restaurants = restaurants.filter(
            pickup_latitude__isnull=False,
            pickup_longitude__isnull=False,
        )

    closest_by_merchant = {}
    radius = Decimal(str(radius_km))
    for restaurant in restaurants:
        nearby_merchant = restaurant.owner.merchant_profile
        distance = _restaurant_distance_to_anchor(restaurant, anchor)
        if distance is None or distance > radius:
            continue
        current = closest_by_merchant.get(nearby_merchant.id)
        if current is None or distance < current[1]:
            closest_by_merchant[nearby_merchant.id] = (nearby_merchant, distance)

    merchants = [
        merchant_distance[0]
        for merchant_distance in sorted(
            closest_by_merchant.values(),
            key=lambda item: (item[1], str(item[0]).lower(), item[0].id),
        )
    ]
    for nearby_merchant in merchants:
        nearby_merchant.distance_km = closest_by_merchant[nearby_merchant.id][1]
    return merchants


def calculate_fulfillment_settlement_preview(fulfillment_request):
    order = fulfillment_request.order
    original_payout = quantize_money(order.merchant_payout)
    fulfilling_share = (original_payout * Decimal('0.70')).quantize(
        Decimal('0.01'),
        rounding=ROUND_HALF_UP,
    )
    requesting_share = original_payout - fulfilling_share
    delivery_partner_fee = Decimal('0.00')
    try:
        delivery_partner_fee = quantize_money(order.delivery.partner_fee)
    except Exception:
        delivery_partner_fee = Decimal('0.00')

    return {
        'order_total': money_string(order.total_amount),
        'food_subtotal': money_string(order.subtotal_amount),
        'platform_fee': money_string(order.platform_fee),
        'original_merchant_payout': money_string(original_payout),
        'suggested_fulfilling_merchant_share': money_string(fulfilling_share),
        'suggested_requesting_merchant_share': money_string(requesting_share),
        'delivery_fee': money_string(order.delivery_fee),
        'delivery_partner_fee': money_string(delivery_partner_fee),
        'calculation_method': SETTLEMENT_PREVIEW_METHOD,
        'is_preview_only': True,
        'preview_label': SETTLEMENT_PREVIEW_LABEL,
        'calculated_at': timezone.now().isoformat(),
    }


def ensure_fulfillment_settlement_preview(fulfillment_request, actor=None, force=False):
    if fulfillment_request.settlement_preview and not force:
        from ledger.services import record_fulfillment_preview

        record_fulfillment_preview(fulfillment_request)
        return fulfillment_request.settlement_preview

    preview = calculate_fulfillment_settlement_preview(fulfillment_request)
    fulfillment_request.settlement_preview = preview
    fulfillment_request.save(update_fields=['settlement_preview', 'updated_at'])

    from ledger.services import record_fulfillment_preview

    record_fulfillment_preview(fulfillment_request)

    from restaurants.models import MerchantFulfillmentRequestEvent

    MerchantFulfillmentRequestEvent.objects.create(
        fulfillment_request=fulfillment_request,
        event_type=MerchantFulfillmentRequestEvent.EVENT_SETTLEMENT_PREVIEWED,
        from_status=fulfillment_request.internal_status,
        to_status=fulfillment_request.internal_status,
        actor=actor,
        note=SETTLEMENT_PREVIEW_LABEL,
        metadata={
            'calculation_method': SETTLEMENT_PREVIEW_METHOD,
            'preview_only': True,
            'customer_visible': False,
            'payment_unchanged': True,
            'payout_unchanged': True,
            'delivery_partner_fee_unchanged': True,
        },
    )
    return preview


def restaurant_accepting_orders(restaurant, at=None):
    if not restaurant.is_active or not restaurant.is_open:
        return False
    hours = list(restaurant.operating_hours.all())
    if not hours:
        return True

    local_now = timezone.localtime(at or timezone.now())
    current_time = local_now.time().replace(tzinfo=None)
    by_day = {entry.day_of_week: entry for entry in hours}
    today = by_day.get(local_now.weekday())
    if today and not today.is_closed:
        if today.opens_at == today.closes_at:
            return True
        if today.opens_at < today.closes_at:
            if today.opens_at <= current_time < today.closes_at:
                return True
        elif current_time >= today.opens_at:
            return True

    previous = by_day.get((local_now.weekday() - 1) % 7)
    return bool(
        previous
        and not previous.is_closed
        and previous.opens_at > previous.closes_at
        and current_time < previous.closes_at
    )

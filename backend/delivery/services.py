from django.db import transaction
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from math import asin, cos, radians, sin, sqrt
from .models import DeliveryPartner, Delivery, MerchantRider
from orders.models import Order
from .notifications import notify_partner_assigned
from notifications.models import Notification
from notifications.events import notify_order_event, schedule_notification_event

MERCHANT_RIDER_EXCLUSIVE_SECONDS = 120
DELIVERY_MODE_T_FOOD = 'T_FOOD_DELIVERY'
DELIVERY_MODE_MERCHANT = 'MERCHANT_DELIVERY'
DELIVERY_MODE_HYBRID = 'HYBRID'


def _delivery_scope(delivery):
    restaurant = pickup_restaurant(delivery)
    market = delivery.market or delivery.order.market or getattr(restaurant, 'market', None)
    return {
        'order': delivery.order,
        'branch': restaurant,
        'market': market,
        'country_code': (
            getattr(restaurant, 'country_code', None)
            or getattr(market, 'country_code', None)
        ),
        'city': getattr(restaurant, 'city_ref', None),
        'area': getattr(restaurant, 'area_ref', None),
    }


def _schedule_delivery_notification(user, delivery, event_type, title, message, *, idempotency_key):
    restaurant = pickup_restaurant(delivery)
    schedule_notification_event(
        event_type=event_type,
        recipients={'users': [user]},
        subject=delivery.order,
        scope=_delivery_scope(delivery),
        payload={
            'title': title,
            'message': message,
            'intent': 'dispatch',
            'metadata': {
                'delivery_id': delivery.id,
                'order_id': delivery.order_id,
                'pickup_branch_id': getattr(restaurant, 'id', None),
                'pickup_branch_name': (
                    getattr(restaurant, 'branch_name', None)
                    or getattr(restaurant, 'rest_name', '')
                ) if restaurant else '',
                'pickup_phone': getattr(restaurant, 'rest_contact', '') if restaurant else '',
            },
        },
        category=Notification.CATEGORY_DELIVERY,
        priority=Notification.PRIORITY_HIGH,
        action_url='/partner/dashboard',
        idempotency_key=idempotency_key,
    )


def _can_use_postgis():
    return (
        settings.GEODJANGO_AVAILABLE
        and settings.DATABASES['default']['ENGINE']
        == 'django.contrib.gis.db.backends.postgis'
    )


def _distance_to_km(distance):
    if distance is None:
        return None
    if hasattr(distance, 'km'):
        return distance.km
    return float(distance) / 1000


def annotate_partner_pickup_distance(partners, restaurant):
    if not _can_use_postgis() or not restaurant or not restaurant.pickup_point:
        return partners

    from django.contrib.gis.db.models.functions import Distance

    return partners.annotate(
        gis_pickup_distance=Distance('current_point', restaurant.pickup_point)
    )


def pickup_restaurant(delivery):
    return pickup_restaurant_for_order(delivery.order)


def pickup_restaurant_for_order(order):
    pickup_branch = getattr(order, 'pickup_branch', None)
    if pickup_branch:
        return pickup_branch
    first_item = order.items.select_related('food__restaurant').first()
    return first_item.food.restaurant if first_item else None


def get_order_pickup_branch(order):
    return pickup_restaurant_for_order(order)


def merchant_profile_for_order(order):
    restaurant = pickup_restaurant_for_order(order)
    owner = getattr(restaurant, 'owner', None)
    return getattr(owner, 'merchant_profile', None) if owner else None


def partner_distance_km(partner, restaurant):
    if not restaurant:
        return None

    annotated_distance = _distance_to_km(
        getattr(partner, 'gis_pickup_distance', None)
    )
    if annotated_distance is not None:
        return annotated_distance

    if (
        _can_use_postgis()
        and restaurant
        and partner.current_point
        and restaurant.pickup_point
    ):
        from django.contrib.gis.db.models.functions import Distance

        partner_with_distance = (
            DeliveryPartner.objects
            .filter(id=partner.id)
            .annotate(gis_pickup_distance=Distance(
                'current_point',
                restaurant.pickup_point,
            ))
            .first()
        )
        distance = _distance_to_km(
            getattr(partner_with_distance, 'gis_pickup_distance', None)
        )
        if distance is not None:
            return distance

    coordinates = (
        partner.current_latitude,
        partner.current_longitude,
        restaurant.pickup_latitude,
        restaurant.pickup_longitude,
    )
    if any(value is None for value in coordinates):
        return None
    lat1, lon1, lat2, lon2 = map(lambda value: radians(float(value)), coordinates)
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1
    value = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    return 6371 * 2 * asin(sqrt(value))


def offer_radius_km(delivery, now=None):
    elapsed = ((now or timezone.now()) - delivery.delivery_date).total_seconds()
    if elapsed < 120:
        return 5
    if elapsed < 300:
        return 10
    if elapsed < 600:
        return 20
    return None


def _merchant_rider_partners(order):
    merchant = merchant_profile_for_order(order)
    if not merchant:
        return DeliveryPartner.objects.none()
    return DeliveryPartner.objects.filter(
        merchant_rider_link__merchant=merchant,
        merchant_rider_link__status=MerchantRider.STATUS_ACTIVE,
        is_available=True,
        is_verified=True,
    ).select_related('user')


def get_branch_preferred_riders(order):
    branch = get_order_pickup_branch(order)
    if not branch:
        return DeliveryPartner.objects.none()
    return _merchant_rider_partners(order).filter(
        merchant_rider_link__home_restaurant=branch,
    )


def get_merchant_preferred_riders(order):
    return _merchant_rider_partners(order)


def get_preferred_merchant_riders(order):
    branch_riders = get_branch_preferred_riders(order)
    return branch_riders if branch_riders.exists() else get_merchant_preferred_riders(order)


def get_global_candidate_partners(order):
    return DeliveryPartner.objects.filter(
        is_available=True,
        is_verified=True,
    ).exclude(
        merchant_rider_link__status=MerchantRider.STATUS_ACTIVE,
    ).select_related('user')


def _branch_delivery_mode(restaurant):
    return getattr(restaurant, 'delivery_mode', DELIVERY_MODE_HYBRID) or DELIVERY_MODE_HYBRID


def _active_merchant_rider_link(partner):
    link = getattr(partner, 'merchant_rider_link', None)
    if link and link.status == MerchantRider.STATUS_ACTIVE:
        return link
    return None


def _merchant_rider_matches_order(delivery, partner):
    link = _active_merchant_rider_link(partner)
    if not link:
        return False
    merchant = merchant_profile_for_order(delivery.order)
    if not merchant or link.merchant_id != merchant.id:
        return False
    branch = pickup_restaurant(delivery)
    return not link.home_restaurant_id or (
        branch is not None and link.home_restaurant_id == branch.id
    )


def _delivery_mode_allows_partner(delivery, partner, now):
    restaurant = pickup_restaurant(delivery)
    mode = _branch_delivery_mode(restaurant)
    if _active_merchant_rider_link(partner):
        if mode not in (DELIVERY_MODE_MERCHANT, DELIVERY_MODE_HYBRID):
            return False
        if not _merchant_rider_matches_order(delivery, partner):
            return False
        preferred_ids = _preferred_candidate_ids(delivery, now)
        if preferred_ids and merchant_preference_is_active(delivery, now):
            return partner.id in preferred_ids
        return True
    if mode == DELIVERY_MODE_MERCHANT:
        return False
    if mode == DELIVERY_MODE_T_FOOD:
        return True
    preferred_ids = _preferred_candidate_ids(delivery, now)
    return not (preferred_ids and merchant_preference_is_active(delivery, now))


def _base_partner_is_eligible(delivery, partner, now=None):
    if not partner.is_verified or not partner.is_available:
        return False
    restaurant = pickup_restaurant(delivery)
    if not restaurant or restaurant.pickup_latitude is None:
        return True
    radius = offer_radius_km(delivery, now)
    if radius is None:
        return True
    if (
        not partner.location_updated_at
        or partner.location_updated_at < (now or timezone.now()) - timedelta(minutes=15)
    ):
        return False
    distance = partner_distance_km(partner, restaurant)
    return distance is not None and distance <= radius


def _preferred_candidate_ids(delivery, now=None):
    restaurant = pickup_restaurant(delivery)
    partners = get_branch_preferred_riders(delivery.order)
    if restaurant:
        partners = annotate_partner_pickup_distance(partners, restaurant)
    branch_ids = {
        partner.id
        for partner in partners
        if _base_partner_is_eligible(delivery, partner, now)
    }
    if branch_ids:
        return branch_ids

    partners = get_merchant_preferred_riders(delivery.order)
    if restaurant:
        partners = annotate_partner_pickup_distance(partners, restaurant)
    return {
        partner.id
        for partner in partners
        if _base_partner_is_eligible(delivery, partner, now)
    }


def merchant_preference_is_active(delivery, now=None):
    elapsed = ((now or timezone.now()) - delivery.delivery_date).total_seconds()
    return elapsed < MERCHANT_RIDER_EXCLUSIVE_SECONDS


def partner_is_eligible(delivery, partner, now=None):
    now = now or timezone.now()
    if not _base_partner_is_eligible(delivery, partner, now):
        return False
    return _delivery_mode_allows_partner(delivery, partner, now)


def notify_delivery_candidates(delivery):
    now = timezone.now()
    preferred_ids = _preferred_candidate_ids(delivery, now)
    if preferred_ids and merchant_preference_is_active(delivery, now):
        partners = DeliveryPartner.objects.filter(id__in=preferred_ids).select_related('user')
    else:
        partners = get_global_candidate_partners(delivery.order)
    title = f'Pickup available for order #{delivery.order_id}'
    radius = offer_radius_km(delivery, now)
    restaurant = pickup_restaurant(delivery)
    if restaurant:
        partners = annotate_partner_pickup_distance(partners, restaurant)
    notified = 0
    for partner in partners:
        if not partner_is_eligible(delivery, partner, now):
            continue
        if Notification.objects.filter(
            user=partner.user,
            order=delivery.order,
            kind='DELIVERY',
            title=title,
        ).exists():
            continue
        distance = partner_distance_km(partner, restaurant) if restaurant else None
        distance_text = f' It is {distance:.1f} km from your location.' if distance is not None else ''
        wave_text = f' Current offer radius: {radius} km.' if radius is not None else ''
        _schedule_delivery_notification(
            partner.user,
            delivery,
            'delivery.offer_available',
            title,
            f'A ready pickup is available.{distance_text}{wave_text}',
            idempotency_key=f'delivery-offer:{delivery.id}:{partner.id}',
        )
        notified += 1
    return notified


def sort_deliveries_for_partner(deliveries, partner):
    decorated = []
    for delivery in deliveries:
        restaurant = pickup_restaurant(delivery)
        distance = partner_distance_km(partner, restaurant) if restaurant else None
        delivery.pickup_distance_km = distance
        decorated.append((delivery, distance))

    decorated.sort(key=lambda item: (
        item[1] is None,
        item[1] if item[1] is not None else float('inf'),
        item[0].delivery_date,
        item[0].id,
    ))
    return [delivery for delivery, _distance in decorated]


def _assign(delivery, partner):
    delivery.delivery_partner = partner
    delivery.status = 'ASSIGNED'
    delivery.assigned_at = timezone.now()
    delivery.partner_fee = delivery.order.delivery_fee
    delivery.payout_status = 'PENDING'
    delivery.paid_at = None
    delivery.save()

    partner.is_available = False
    partner.save(update_fields=['is_available'])
    Notification.objects.filter(
        order=delivery.order,
        kind='DELIVERY',
        title=f'Pickup available for order #{delivery.order_id}',
    ).exclude(user=partner.user).delete()
    notify_partner_assigned(delivery)
    restaurant = pickup_restaurant(delivery)
    pickup_name = (
        (restaurant.branch_name or restaurant.rest_name)
        if restaurant else 'the pickup branch'
    )
    pickup_phone = (
        f' Call {restaurant.rest_contact} if needed.'
        if restaurant and restaurant.rest_contact else ''
    )
    _schedule_delivery_notification(
        partner.user,
        delivery,
        'delivery.assigned',
        f'New delivery for order #{delivery.order_id}',
        f'You accepted this pickup from {pickup_name}.{pickup_phone} '
        'Open the partner dashboard for pickup address and route details.',
        idempotency_key=f'delivery-assigned-partner:{delivery.id}:{partner.id}',
    )
    notify_order_event(
        delivery.order,
        'rider_assigned',
        delivery=delivery,
        message=(
            f'{partner.partner_name} will deliver your order. '
            f'Your handoff code is {delivery.confirmation_code}. '
            'Share it only after receiving the order.'
        ),
    )
    return delivery


@transaction.atomic
def auto_assign_delivery(order: Order):
    delivery, _ = Delivery.objects.select_for_update().get_or_create(order=order)
    if delivery.delivery_partner:
        return delivery
    notify_delivery_candidates(delivery)
    notify_order_event(
        order,
        'ready_for_pickup',
        message='Your order is ready and has been offered to available delivery partners.',
    )
    return delivery


@transaction.atomic
def notify_partner_of_pending_deliveries(partner):
    partner = DeliveryPartner.objects.select_for_update().get(id=partner.id)
    if not partner.is_verified or not partner.is_available:
        return None
    deliveries = Delivery.objects.filter(
        delivery_partner__isnull=True,
        order__status='READY_FOR_PICKUP',
    ).select_related('order').order_by('delivery_date')[:10]
    for delivery in deliveries:
        if not partner_is_eligible(delivery, partner):
            continue
        title = f'Pickup available for order #{delivery.order_id}'
        if not Notification.objects.filter(
            user=partner.user,
            order=delivery.order,
            kind='DELIVERY',
            title=title,
        ).exists():
            _schedule_delivery_notification(
                partner.user,
                delivery,
                'delivery.offer_available',
                title,
                'A ready pickup is waiting. Open the partner dashboard to review and accept it.',
                idempotency_key=f'delivery-offer:{delivery.id}:{partner.id}',
            )
    return len(deliveries)


@transaction.atomic
def claim_pending_delivery(delivery_id, partner):
    partner = DeliveryPartner.objects.select_for_update().get(id=partner.id)
    if not partner.is_verified or not partner.is_available:
        return None
    delivery = Delivery.objects.select_for_update().filter(
        id=delivery_id,
        delivery_partner__isnull=True,
        order__status='READY_FOR_PICKUP',
    ).select_related('order__customer').first()
    if not delivery:
        return None
    if not partner_is_eligible(delivery, partner):
        return None
    return _assign(delivery, partner)

from collections import defaultdict
from decimal import Decimal

from django.db.models import Avg, Count, Q, Sum

from api.restaurant_views import restaurant_catalog_queryset
from api.serializers import RestaurantSerializer
from customers.models import FavoriteRestaurant
from orders.models import OrderItem
from restaurants.services import restaurants_sorted_for_location

from .scoring import RecommendationCandidate


SECTION_LIMIT = 8


def _safe_decimal(value, default='0'):
    if value is None:
        return Decimal(default)
    return Decimal(str(value))


def _candidate_sort_key(candidate):
    distance = candidate.distance_km
    if distance is None:
        distance = Decimal('999999')
    return (-candidate.score, distance, candidate.restaurant.rest_name.lower())


def _restaurant_queryset():
    return restaurant_catalog_queryset().annotate(
        delivered_order_count=Count(
            'food_items__orderitem__order',
            filter=Q(food_items__orderitem__order__status='DELIVERED'),
            distinct=True,
        ),
        recommendation_average_rating=Avg('reviews__rating'),
    )


def _customer_signal_maps(user):
    if not user or not user.is_authenticated:
        return {
            'favorite_ids': set(),
            'ordered_counts': {},
            'category_affinity': {},
        }

    favorite_ids = set(
        FavoriteRestaurant.objects.filter(user=user).values_list(
            'restaurant_id', flat=True
        )
    )
    ordered_counts = {
        row['food__restaurant_id']: row['total'] or 0
        for row in OrderItem.objects.filter(
            order__customer=user,
            order__status='DELIVERED',
        ).values('food__restaurant_id').annotate(total=Sum('quantity'))
    }
    category_affinity = {
        row['food__food_categ']: row['total'] or 0
        for row in OrderItem.objects.filter(
            order__customer=user,
            order__status='DELIVERED',
        ).values('food__food_categ').annotate(total=Sum('quantity'))
    }
    return {
        'favorite_ids': favorite_ids,
        'ordered_counts': ordered_counts,
        'category_affinity': category_affinity,
    }


def _score_restaurant(restaurant, signals, has_location):
    candidate = RecommendationCandidate(restaurant=restaurant, score=Decimal('50'))

    if candidate.is_accepting_orders:
        candidate.add_score(12, 'open_now')
    else:
        candidate.add_score(-100)

    if restaurant.id in signals['favorite_ids']:
        candidate.add_score(35, 'favorite')

    ordered_count = signals['ordered_counts'].get(restaurant.id, 0)
    if ordered_count:
        candidate.add_score(min(40, 20 + ordered_count * 5), 'ordered_before')

    categories = {item.food_categ for item in restaurant.food_items.all()}
    category_match = sum(
        signals['category_affinity'].get(category, 0)
        for category in categories
    )
    if category_match:
        candidate.add_score(min(18, category_match * 3), 'category_match')

    rating = _safe_decimal(
        getattr(restaurant, 'recommendation_average_rating', None)
        or getattr(restaurant, 'average_rating', None)
    )
    if rating >= Decimal('4.0'):
        candidate.add_score(rating * Decimal('4'), 'top_rated')
    elif rating:
        candidate.add_score(rating * Decimal('2'))

    delivered_count = getattr(restaurant, 'delivered_order_count', 0) or 0
    if delivered_count:
        candidate.add_score(min(30, delivered_count * 4), 'popular')

    profile = getattr(restaurant.owner, 'merchant_profile', None)
    if profile and profile.is_verified:
        candidate.add_score(8, 'verified_merchant')

    if has_location:
        distance = candidate.distance_km
        if candidate.is_serviceable is False:
            candidate.add_score(-35)
        elif distance is not None:
            if distance <= Decimal('3'):
                candidate.add_score(24, 'close_to_you')
            elif distance <= Decimal('8'):
                candidate.add_score(14, 'close_to_you')
            else:
                candidate.add_score(4)
            if (
                candidate.is_serviceable
                and restaurant.estimated_prep_minutes <= 25
                and distance <= Decimal('5')
            ):
                candidate.add_score(14, 'fast_nearby')

    if not any(
        code in candidate.reason_codes
        for code in ('ordered_before', 'favorite', 'popular', 'top_rated')
    ):
        candidate.add_reason('new_to_try')

    return candidate


def _serialize_candidates(candidates, request, location):
    restaurants = [candidate.restaurant for candidate in candidates]
    serializer = RestaurantSerializer(
        restaurants,
        many=True,
        context={'request': request, 'location': location},
    )
    serialized = []
    for candidate, restaurant_data in zip(candidates, serializer.data):
        serialized.append({
            'restaurant': restaurant_data,
            'score': candidate.output_score(),
            'reason_codes': candidate.reason_codes,
            'reason_label': candidate.reason_label,
        })
    return serialized


def _limit(candidates, count=SECTION_LIMIT):
    return candidates[:count]


def get_customer_recommendations(request, location=None):
    user = request.user if request.user.is_authenticated else None
    has_location = bool(location)
    queryset = _restaurant_queryset()

    if has_location:
        restaurants = restaurants_sorted_for_location(
            queryset,
            location['latitude'],
            location['longitude'],
        )
    else:
        restaurants = list(queryset)

    signals = _customer_signal_maps(user)
    candidates = [
        _score_restaurant(restaurant, signals, has_location)
        for restaurant in restaurants
        if restaurant.is_active
    ]
    open_candidates = [
        candidate for candidate in candidates if candidate.is_accepting_orders
    ]
    ranked = sorted(open_candidates, key=_candidate_sort_key)

    ordered = sorted(
        [
            candidate for candidate in ranked
            if candidate.restaurant.id in signals['ordered_counts']
        ],
        key=lambda candidate: (
            -signals['ordered_counts'].get(candidate.restaurant.id, 0),
            *_candidate_sort_key(candidate),
        ),
    )

    serviceable = [
        candidate for candidate in ranked
        if not has_location or candidate.is_serviceable is True
    ]
    nearby_fast = sorted(
        [
            candidate for candidate in serviceable
            if has_location and candidate.distance_km is not None
        ],
        key=lambda candidate: (
            candidate.distance_km,
            candidate.restaurant.estimated_prep_minutes,
            -candidate.score,
        ),
    )

    popular = sorted(
        [
            candidate for candidate in serviceable
            if getattr(candidate.restaurant, 'delivered_order_count', 0) > 0
        ],
        key=lambda candidate: (
            -getattr(candidate.restaurant, 'delivered_order_count', 0),
            candidate.distance_km if candidate.distance_km is not None else Decimal('999999'),
            -candidate.score,
        ),
    )

    top_rated = sorted(
        [
            candidate for candidate in ranked
            if _safe_decimal(
                getattr(candidate.restaurant, 'recommendation_average_rating', None)
                or getattr(candidate.restaurant, 'average_rating', None)
            ) >= Decimal('4.0')
        ],
        key=lambda candidate: (
            -_safe_decimal(
                getattr(candidate.restaurant, 'recommendation_average_rating', None)
                or getattr(candidate.restaurant, 'average_rating', None)
            ),
            -candidate.score,
        ),
    )

    known_ids = set(signals['favorite_ids']) | set(signals['ordered_counts'].keys())
    new_to_try = [
        candidate for candidate in ranked
        if candidate.restaurant.id not in known_ids
    ]

    sections = {
        'recommended_for_you': _limit(ranked),
        'nearby_fast': _limit(nearby_fast),
        'popular_near_you': _limit(popular),
        'order_again': _limit(ordered),
        'top_rated': _limit(top_rated),
        'new_to_try': _limit(new_to_try),
    }

    return {
        name: _serialize_candidates(candidates, request, location)
        for name, candidates in sections.items()
    }

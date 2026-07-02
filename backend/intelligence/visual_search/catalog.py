from decimal import Decimal, InvalidOperation

from django.db.models import Count, Q

from markets.models import Market
from restaurants.models import FoodItem, Restaurant
from restaurants.services import restaurants_sorted_for_location


MAX_VISUAL_SEARCH_ITEMS = 12
MAX_VISUAL_SEARCH_MERCHANTS = 10


def parse_visual_search_location(latitude, longitude):
    if latitude in (None, '') or longitude in (None, ''):
        return None
    try:
        latitude = Decimal(str(latitude))
        longitude = Decimal(str(longitude))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not Decimal('-90') <= latitude <= Decimal('90'):
        return None
    if not Decimal('-180') <= longitude <= Decimal('180'):
        return None
    return {'latitude': latitude, 'longitude': longitude}


def resolve_market(value):
    if value in (None, ''):
        return None
    value = str(value).strip()
    queryset = Market.objects.filter(is_active=True)
    if value.isdigit():
        return queryset.filter(id=value).first()
    return queryset.filter(Q(slug__iexact=value) | Q(country_code__iexact=value)).first()


def search_visual_catalog(labels, normalized_query='', market=None, category='',
                          location=None):
    tokens = _query_tokens(labels, normalized_query, category)
    item_queryset = FoodItem.objects.filter(is_available=True).select_related(
        'restaurant',
        'restaurant__market',
        'restaurant__city_ref',
        'restaurant__area_ref',
    )
    branch_queryset = Restaurant.objects.filter(is_active=True).select_related(
        'market',
        'city_ref',
        'area_ref',
        'owner',
        'owner__merchant_profile',
    ).annotate(
        item_count=Count(
            'food_items',
            filter=Q(food_items__is_available=True),
            distinct=True,
        )
    )

    if market:
        item_queryset = item_queryset.filter(restaurant__market=market)
        branch_queryset = branch_queryset.filter(market=market)
    if category:
        item_queryset = item_queryset.filter(
            Q(food_categ__icontains=category)
            | Q(restaurant__branch_type__iexact=category)
        )
        branch_queryset = branch_queryset.filter(
            Q(branch_type__iexact=category)
            | Q(food_items__food_categ__icontains=category)
        ).distinct()

    item_queryset = _filter_items_by_tokens(item_queryset, tokens)
    branch_queryset = _filter_branches_by_tokens(branch_queryset, tokens)

    items = sorted(
        item_queryset.distinct()[:50],
        key=lambda item: (
            -_item_relevance(item, tokens),
            item.food_name.lower(),
            item.id,
        ),
    )[:MAX_VISUAL_SEARCH_ITEMS]

    branches = list(branch_queryset.distinct()[:50])
    if location:
        branches = restaurants_sorted_for_location(
            branch_queryset.distinct(),
            location['latitude'],
            location['longitude'],
        )[:MAX_VISUAL_SEARCH_MERCHANTS]
    else:
        branches = sorted(
            branches,
            key=lambda branch: (
                -_branch_relevance(branch, tokens),
                branch.rest_name.lower(),
                branch.id,
            ),
        )[:MAX_VISUAL_SEARCH_MERCHANTS]

    return {
        'matched_items': [_serialize_item(item, tokens) for item in items],
        'matched_merchants': [_serialize_branch(branch, tokens) for branch in branches],
        'similar_categories': _similar_categories(items, branches, labels, category),
    }


def _query_tokens(labels, normalized_query, category):
    raw = list(labels or [])
    raw.extend(str(normalized_query or '').split())
    if category:
        raw.append(category)
    tokens = []
    for value in raw:
        token = str(value).strip().lower()
        if token and token not in tokens:
            tokens.append(token)
    return tokens or ['product']


def _filter_items_by_tokens(queryset, tokens):
    query = Q()
    for token in tokens:
        query |= (
            Q(food_name__icontains=token)
            | Q(food_desc__icontains=token)
            | Q(food_categ__icontains=token)
            | Q(restaurant__rest_name__icontains=token)
            | Q(restaurant__branch_name__icontains=token)
            | Q(restaurant__branch_type__icontains=token)
        )
    return queryset.filter(query) if query else queryset.none()


def _filter_branches_by_tokens(queryset, tokens):
    query = Q()
    for token in tokens:
        query |= (
            Q(rest_name__icontains=token)
            | Q(branch_name__icontains=token)
            | Q(branch_type__icontains=token)
            | Q(rest_city__icontains=token)
            | Q(city_ref__name__icontains=token)
            | Q(area_ref__name__icontains=token)
            | Q(food_items__food_name__icontains=token)
            | Q(food_items__food_desc__icontains=token)
            | Q(food_items__food_categ__icontains=token)
        )
    return queryset.filter(query) if query else queryset.none()


def _item_relevance(item, tokens):
    haystack = ' '.join([
        item.food_name,
        item.food_desc,
        item.food_categ,
        item.restaurant.rest_name,
        item.restaurant.branch_name,
        item.restaurant.branch_type,
    ]).lower()
    return sum(1 for token in tokens if token in haystack)


def _branch_relevance(branch, tokens):
    haystack = ' '.join([
        branch.rest_name,
        branch.branch_name,
        branch.branch_type,
        branch.rest_city,
        branch.city_ref.name if branch.city_ref_id else '',
        branch.area_ref.name if branch.area_ref_id else '',
    ]).lower()
    return sum(1 for token in tokens if token in haystack)


def _serialize_item(item, tokens):
    branch = item.restaurant
    return {
        'id': item.id,
        'name': item.food_name,
        'description': item.food_desc,
        'category': item.food_categ,
        'price': str(item.food_price),
        'branch_id': branch.id,
        'branch_name': branch.branch_name or branch.rest_name,
        'branch_type': branch.branch_type,
        'merchant_name': _merchant_name(branch),
        'relevance_score': _item_relevance(item, tokens),
    }


def _serialize_branch(branch, tokens):
    return {
        'id': branch.id,
        'rest_name': branch.rest_name,
        'branch_name': branch.branch_name or branch.rest_name,
        'branch_type': branch.branch_type,
        'merchant_name': _merchant_name(branch),
        'market': branch.market_id,
        'market_name': branch.market.name if branch.market_id else '',
        'country_code': branch.country_code,
        'city': branch.city_ref.name if branch.city_ref_id else branch.rest_city,
        'area': branch.area_ref.name if branch.area_ref_id else '',
        'address': branch.rest_address,
        'item_count': getattr(branch, 'item_count', 0),
        'distance_km': _string_or_none(getattr(branch, 'distance_km', None)),
        'is_serviceable': getattr(branch, 'is_serviceable', None),
        'relevance_score': _branch_relevance(branch, tokens),
    }


def _merchant_name(branch):
    profile = getattr(branch.owner, 'merchant_profile', None)
    if profile:
        return str(profile)
    return branch.owner.get_full_name() or branch.owner.username if branch.owner else ''


def _similar_categories(items, branches, labels, requested_category):
    categories = []
    for label in labels or []:
        _append_unique(categories, str(label).strip())
    if requested_category:
        _append_unique(categories, requested_category)
    for item in items:
        _append_unique(categories, item.food_categ)
    for branch in branches:
        _append_unique(categories, branch.branch_type)
    return categories[:10]


def _append_unique(values, value):
    if value and value not in values:
        values.append(value)


def _string_or_none(value):
    return str(value) if value is not None else None

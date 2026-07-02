from collections import Counter, defaultdict

from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.utils import timezone

from customers.models import Customer
from delivery.models import Delivery, DeliveryPartner
from intelligence.models import VisualSearchEvent
from markets.models import CommerceArea, CommerceCity
from orders.models import Order, SupportTicket
from restaurants.models import MerchantProfile, Restaurant, RestaurantReview
from api.operations_views import (
    apply_request_scope_filter,
    scoped_customer_queryset,
    scoped_delivery_queryset,
    scoped_merchant_queryset,
    scoped_order_queryset,
    scoped_partner_queryset,
    scoped_branch_queryset,
)


def _minutes_between(start, end):
    if not start or not end:
        return None
    seconds = (end - start).total_seconds()
    if seconds < 0:
        return None
    return round(seconds / 60, 1)


def _status_time(order, status):
    for event in order.status_events.all():
        if event.status == status:
            return event.created_at
    return None


def _restaurant_for_order(order):
    first_item = order.items.all()[0] if order.items.all() else None
    return first_item.food.restaurant if first_item else None


def _area_for_order(order):
    restaurant = _restaurant_for_order(order)
    if restaurant and restaurant.rest_city:
        return restaurant.rest_city
    return 'Unknown area'


def _order_delivery_minutes(order):
    start = _status_time(order, 'READY_FOR_PICKUP') or _status_time(order, 'PREPARING')
    end = _status_time(order, 'DELIVERED')
    return _minutes_between(start, end)


def _order_prep_minutes(order):
    return _minutes_between(
        _status_time(order, 'PREPARING'),
        _status_time(order, 'READY_FOR_PICKUP'),
    )


def _merchant_name(user):
    profile = getattr(user, 'merchant_profile', None)
    if profile and profile.business_name:
        return profile.business_name
    return user.get_full_name() or user.username


def _visual_search_queryset(actor=None, request=None):
    queryset = VisualSearchEvent.objects.all()
    if actor is not None and not actor.is_global_scope:
        q = Q()
        if actor.assigned_market_ids:
            q |= Q(market_id__in=actor.assigned_market_ids)
        if actor.assigned_country_codes:
            q |= Q(country_code__in=actor.assigned_country_codes)
            q |= Q(market__country_code__in=actor.assigned_country_codes)
        if actor.assigned_city_ids:
            city_market_ids = CommerceCity.objects.filter(
                id__in=actor.assigned_city_ids,
            ).values_list('market_id', flat=True)
            q |= Q(market_id__in=city_market_ids)
        if actor.assigned_area_ids:
            area_market_ids = CommerceArea.objects.filter(
                id__in=actor.assigned_area_ids,
            ).values_list('market_id', flat=True)
            q |= Q(market_id__in=area_market_ids)
        queryset = queryset.filter(q).distinct() if q else queryset.none()
    if request is not None:
        market = request.query_params.get('market')
        country_code = request.query_params.get('country_code')
        city = request.query_params.get('city')
        area = request.query_params.get('area')
        if market:
            if str(market).isdigit():
                queryset = queryset.filter(market_id=market)
            else:
                queryset = queryset.filter(market__slug__iexact=market)
        if country_code:
            queryset = queryset.filter(
                Q(country_code__iexact=country_code)
                | Q(market__country_code__iexact=country_code)
            )
        if city:
            city_market_ids = CommerceCity.objects.filter(
                Q(id=city) if str(city).isdigit() else (
                    Q(name__icontains=city) | Q(slug__iexact=city)
                )
            ).values_list('market_id', flat=True)
            queryset = queryset.filter(market_id__in=city_market_ids)
        if area:
            area_market_ids = CommerceArea.objects.filter(
                Q(id=area) if str(area).isdigit() else (
                    Q(name__icontains=area) | Q(slug__iexact=area)
                )
            ).values_list('market_id', flat=True)
            queryset = queryset.filter(market_id__in=area_market_ids)
    return queryset


def _visual_search_summary(actor=None, request=None):
    searches = _visual_search_queryset(actor=actor, request=request)
    labels = Counter()
    fallback_queries = Counter()
    provider_usage = Counter()
    confidences = []
    for event in searches:
        for label in event.labels or []:
            label = str(label).strip().lower()
            if label:
                labels[label] += 1
        if event.result_count == 0 and event.fallback_query:
            fallback_queries[event.fallback_query] += 1
        if event.provider_code:
            provider_usage[event.provider_code] += 1
        if event.confidence is not None:
            confidences.append(float(event.confidence))
    return {
        'total_visual_searches': searches.count(),
        'top_labels': [
            {'label': label, 'count': count}
            for label, count in labels.most_common(10)
        ],
        'no_result_searches': searches.filter(result_count=0).count(),
        'top_fallback_queries': [
            {'query': query, 'count': count}
            for query, count in fallback_queries.most_common(10)
        ],
        'provider_usage': [
            {'provider_code': provider_code, 'count': count}
            for provider_code, count in provider_usage.most_common()
        ],
        'average_confidence': (
            round(sum(confidences) / len(confidences), 4)
            if confidences else None
        ),
    }


def operations_insights(actor=None, request=None):
    now = timezone.now()
    customers = Customer.objects.select_related('user')
    merchants = MerchantProfile.objects.select_related('user')
    partners = DeliveryPartner.objects.select_related('user')
    restaurants = Restaurant.objects.select_related('owner', 'owner__merchant_profile')
    orders = Order.objects.prefetch_related(
        'items__food__restaurant__owner__merchant_profile',
        'status_events',
    )
    deliveries = Delivery.objects.select_related(
        'delivery_partner__user',
        'order',
    ).prefetch_related('order__status_events')
    tickets = SupportTicket.objects.select_related(
        'customer',
        'order',
    ).prefetch_related('order__items__food__restaurant__owner__merchant_profile')

    if actor is not None:
        customers = scoped_customer_queryset(customers, actor)
        merchants = scoped_merchant_queryset(merchants, actor)
        partners = scoped_partner_queryset(partners, actor)
        restaurants = scoped_branch_queryset(actor).select_related(
            'owner', 'owner__merchant_profile'
        )
        orders = scoped_order_queryset(orders, actor)
        deliveries = scoped_delivery_queryset(deliveries, actor)
        tickets = tickets.filter(order__in=scoped_order_queryset(Order.objects.all(), actor))

    if request is not None:
        customers = apply_request_scope_filter(customers, request, 'customer')
        merchants = apply_request_scope_filter(merchants, request, 'merchant')
        partners = apply_request_scope_filter(partners, request, 'partner')
        restaurants = apply_request_scope_filter(restaurants, request, 'branch')
        orders = apply_request_scope_filter(orders, request, 'order')
        deliveries = apply_request_scope_filter(deliveries, request, 'delivery')
        tickets = tickets.filter(
            order__in=apply_request_scope_filter(Order.objects.all(), request, 'order')
        )

    active_customer_ids = set(
        orders.values_list('customer_id', flat=True)
    ) | set(customers.values_list('user_id', flat=True))

    delayed_orders = []
    for order in orders.exclude(status__in=('DELIVERED', 'CANCELLED', 'EXPIRED')):
        age_minutes = _minutes_between(order.created_at, now)
        if age_minutes is not None and age_minutes >= 45:
            restaurant = _restaurant_for_order(order)
            delayed_orders.append({
                'order_id': order.id,
                'status': order.status,
                'age_minutes': age_minutes,
                'restaurant': restaurant.rest_name if restaurant else '',
                'area': _area_for_order(order),
            })
    delayed_orders.sort(key=lambda row: -row['age_minutes'])

    area_counts = defaultdict(lambda: {'orders': 0, 'cancelled_orders': 0})
    for order in orders:
        area = _area_for_order(order)
        area_counts[area]['orders'] += 1
        if order.status == 'CANCELLED':
            area_counts[area]['cancelled_orders'] += 1
    high_cancellation_areas = []
    for area, counts in area_counts.items():
        rate = (
            round((counts['cancelled_orders'] / counts['orders']) * 100, 2)
            if counts['orders'] else 0
        )
        if counts['cancelled_orders']:
            high_cancellation_areas.append({
                'area': area,
                **counts,
                'cancellation_rate': rate,
            })
    high_cancellation_areas.sort(
        key=lambda row: (-row['cancellation_rate'], -row['cancelled_orders'])
    )

    hour_counts = Counter(order.created_at.hour for order in orders)
    peak_ordering_hours = [
        {'hour': hour, 'orders': count}
        for hour, count in hour_counts.most_common(5)
    ]

    delivery_minutes = [
        _order_delivery_minutes(order)
        for order in orders.filter(status='DELIVERED')
    ]
    delivery_minutes = [value for value in delivery_minutes if value is not None]
    average_delivery_time = (
        round(sum(delivery_minutes) / len(delivery_minutes), 1)
        if delivery_minutes else None
    )

    merchant_rows = []
    for merchant in merchants:
        merchant_orders = [
            order for order in orders
            if any(
                item.food.restaurant.owner_id == merchant.user_id
                for item in order.items.all()
            )
        ]
        delivered = [order for order in merchant_orders if order.status == 'DELIVERED']
        cancelled = [order for order in merchant_orders if order.status == 'CANCELLED']
        total_terminal = len(delivered) + len(cancelled)
        cancellation_rate = (
            round((len(cancelled) / total_terminal) * 100, 2)
            if total_terminal else 0
        )
        prep_values = [
            _order_prep_minutes(order)
            for order in merchant_orders
        ]
        prep_values = [value for value in prep_values if value is not None]
        average_prep_time = (
            round(sum(prep_values) / len(prep_values), 1)
            if prep_values else None
        )
        rating_agg = RestaurantReview.objects.filter(
            restaurant__owner=merchant.user,
        ).aggregate(total=Count('id'))
        rating_values = list(
            RestaurantReview.objects.filter(
                restaurant__owner=merchant.user,
            ).values_list('rating', flat=True)
        )
        average_rating = (
            round(sum(rating_values) / len(rating_values), 2)
            if rating_values else None
        )
        merchant_rows.append({
            'merchant_id': merchant.id,
            'name': _merchant_name(merchant.user),
            'orders': len(merchant_orders),
            'delivered_orders': len(delivered),
            'cancelled_orders': len(cancelled),
            'cancellation_rate': cancellation_rate,
            'average_prep_time': average_prep_time,
            'average_rating': average_rating,
            'review_count': rating_agg['total'],
        })

    partner_rows = []
    for partner in partners:
        partner_deliveries = [
            delivery for delivery in deliveries
            if delivery.delivery_partner_id == partner.id
        ]
        delivered = [
            delivery for delivery in partner_deliveries
            if delivery.status == 'DELIVERED'
        ]
        delivery_times = [
            _order_delivery_minutes(delivery.order)
            for delivery in delivered
        ]
        delivery_times = [value for value in delivery_times if value is not None]
        average_minutes = (
            round(sum(delivery_times) / len(delivery_times), 1)
            if delivery_times else None
        )
        partner_rows.append({
            'partner_id': partner.id,
            'name': partner.partner_name,
            'deliveries': len(partner_deliveries),
            'delivered_deliveries': len(delivered),
            'average_delivery_minutes': average_minutes,
            'is_available': partner.is_available,
            'is_verified': partner.is_verified,
        })

    support_categories = [
        {'category': category, 'count': count}
        for category, count in Counter(
            tickets.values_list('category', flat=True)
        ).most_common()
    ]
    refund_counts = Counter(tickets.values_list('refund_status', flat=True))
    refund_trends = [
        {'refund_status': status, 'count': count}
        for status, count in refund_counts.items()
    ]
    merchant_support = defaultdict(int)
    customer_support = defaultdict(int)
    for ticket in tickets:
        restaurant = _restaurant_for_order(ticket.order)
        if restaurant and restaurant.owner_id:
            merchant_support[_merchant_name(restaurant.owner)] += 1
        customer_support[
            ticket.customer.get_full_name() or ticket.customer.username
        ] += 1

    unassigned_deliveries = deliveries.filter(delivery_partner__isnull=True).count()
    area_partner_counts = Counter(
        partner.market.name if partner.market_id else 'Default market'
        for partner in partners.filter(is_verified=True)
    )
    areas_lacking_partners = [
        {'area': area, 'verified_partners': count}
        for area, count in area_partner_counts.items()
        if count < 2
    ]

    recommendations = []
    if unassigned_deliveries:
        recommendations.append(
            f'Consider recruiting or activating more delivery partners; {unassigned_deliveries} deliveries are unassigned.'
        )
    if high_cancellation_areas:
        area = high_cancellation_areas[0]
        recommendations.append(
            f"Review cancellation causes in {area['area']} where cancellation rate is {area['cancellation_rate']}%."
        )
    high_cancel_merchants = [
        row for row in merchant_rows if row['cancellation_rate'] >= 20
    ]
    if high_cancel_merchants:
        merchant = sorted(high_cancel_merchants, key=lambda row: -row['cancellation_rate'])[0]
        recommendations.append(
            f"{merchant['name']} has unusually high cancellation rates."
        )
    slow_merchants = [
        row for row in merchant_rows
        if row['average_prep_time'] is not None and row['average_prep_time'] > 30
    ]
    if slow_merchants:
        merchant = sorted(slow_merchants, key=lambda row: -row['average_prep_time'])[0]
        recommendations.append(
            f"Consider reviewing {merchant['name']}'s preparation workflow."
        )
    top_merchants = [
        row for row in merchant_rows
        if row['average_rating'] is not None and row['average_rating'] >= 4.5
    ]
    if top_merchants:
        merchant = sorted(top_merchants, key=lambda row: (-row['average_rating'], -row['delivered_orders']))[0]
        recommendations.append(
            f"{merchant['name']} is consistently highly rated; consider promoting them."
        )
    if peak_ordering_hours:
        peak = peak_ordering_hours[0]['hour']
        recommendations.append(
            f'Peak demand occurs around {peak:02d}:00; staff support and dispatch coverage should be ready.'
        )
    if not recommendations:
        recommendations.append('Marketplace health is stable. Keep monitoring orders, support, and dispatch coverage.')

    return {
        'marketplace_health': {
            'active_restaurants': restaurants.filter(is_active=True).count(),
            'verified_merchants': merchants.filter(is_verified=True).count(),
            'verified_partners': partners.filter(is_verified=True).count(),
            'active_customers': len(active_customer_ids),
            'marketplace_growth_summary': (
                f"{customers.count()} customer profiles, {merchants.count()} merchants, "
                f"and {partners.count()} delivery partners registered."
            ),
        },
        'order_intelligence': {
            'delayed_orders': delayed_orders[:10],
            'high_cancellation_areas': high_cancellation_areas[:5],
            'unassigned_delivery_pressure': {
                'unassigned_deliveries': unassigned_deliveries,
            },
            'peak_ordering_hours': peak_ordering_hours,
            'average_delivery_time': average_delivery_time,
        },
        'merchant_intelligence': {
            'high_cancellation_merchants': sorted(
                [row for row in merchant_rows if row['cancellation_rate'] >= 20],
                key=lambda row: -row['cancellation_rate'],
            )[:5],
            'slow_preparation_merchants': sorted(
                [row for row in merchant_rows if row['average_prep_time'] and row['average_prep_time'] > 30],
                key=lambda row: -row['average_prep_time'],
            )[:5],
            'low_rating_merchants': sorted(
                [row for row in merchant_rows if row['average_rating'] is not None and row['average_rating'] < 3.5],
                key=lambda row: row['average_rating'],
            )[:5],
            'outstanding_merchants': sorted(
                [row for row in merchant_rows if row['average_rating'] is not None and row['average_rating'] >= 4.5],
                key=lambda row: (-row['average_rating'], -row['delivered_orders']),
            )[:5],
        },
        'delivery_intelligence': {
            'partner_workload': sorted(
                partner_rows,
                key=lambda row: (-row['deliveries'], row['name']),
            )[:10],
            'slow_delivery_partners': sorted(
                [row for row in partner_rows if row['average_delivery_minutes'] and row['average_delivery_minutes'] > 45],
                key=lambda row: -row['average_delivery_minutes'],
            )[:5],
            'excellent_partners': sorted(
                [row for row in partner_rows if row['delivered_deliveries'] and (row['average_delivery_minutes'] is None or row['average_delivery_minutes'] <= 30)],
                key=lambda row: (-row['delivered_deliveries'], row['average_delivery_minutes'] or 0),
            )[:5],
            'areas_lacking_delivery_partners': areas_lacking_partners,
        },
        'support_intelligence': {
            'common_complaint_categories': support_categories,
            'refund_trends': refund_trends,
            'high_support_merchants': [
                {'merchant': merchant, 'tickets': count}
                for merchant, count in sorted(
                    merchant_support.items(),
                    key=lambda item: (-item[1], item[0]),
                )[:5]
            ],
            'high_support_customers': [
                {'customer': customer, 'tickets': count}
                for customer, count in sorted(
                    customer_support.items(),
                    key=lambda item: (-item[1], item[0]),
                )[:5]
            ],
        },
        'visual_search_intelligence': _visual_search_summary(
            actor=actor,
            request=request,
        ),
        'marketplace_recommendations': recommendations,
    }

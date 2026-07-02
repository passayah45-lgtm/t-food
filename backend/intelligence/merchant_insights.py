from decimal import Decimal

from django.db.models import Count, Sum

from orders.models import Order, OrderItem
from restaurants.models import FoodItem, Restaurant, RestaurantReview


def _money(value):
    return value or Decimal('0.00')


def _average(values):
    values = [value for value in values if value is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def _prep_minutes(order, start_status, end_status):
    events = {event.status: event.created_at for event in order.status_events.all()}
    if start_status not in events or end_status not in events:
        return None
    seconds = (events[end_status] - events[start_status]).total_seconds()
    if seconds < 0:
        return None
    return seconds / 60


def _merchant_orders(user):
    return Order.objects.filter(
        items__food__restaurant__owner=user,
    ).prefetch_related('items__food', 'status_events').distinct()


def _item_sales(user, delivered_order_ids):
    sold_by_item = {}
    for line in OrderItem.objects.filter(
        order_id__in=delivered_order_ids,
        food__restaurant__owner=user,
    ).select_related('food'):
        row = sold_by_item.setdefault(line.food_id, {
            'item_id': line.food_id,
            'name': line.food.food_name,
            'quantity': 0,
            'gross_sales': Decimal('0.00'),
        })
        row['quantity'] += line.quantity
        row['gross_sales'] += line.price * line.quantity
    return sold_by_item


def merchant_insights_for(user):
    orders = _merchant_orders(user)
    delivered = orders.filter(status='DELIVERED')
    delivered_ids = list(delivered.values_list('id', flat=True))
    cancelled_count = orders.filter(status='CANCELLED').count()
    delivered_count = delivered.count()
    completed_or_cancelled = delivered_count + cancelled_count
    cancellation_rate = (
        round((cancelled_count / completed_or_cancelled) * 100, 2)
        if completed_or_cancelled else 0
    )

    gross_sales = _money(delivered.aggregate(total=Sum('total_amount'))['total'])
    average_order_value = (
        (gross_sales / delivered_count).quantize(Decimal('0.01'))
        if delivered_count else Decimal('0.00')
    )

    sold_by_item = _item_sales(user, delivered_ids)
    best_selling_items = sorted(
        sold_by_item.values(),
        key=lambda row: (-row['quantity'], row['name']),
    )[:5]

    all_items = list(
        FoodItem.objects.filter(restaurant__owner=user).select_related('restaurant')
        .order_by('food_name')
    )
    low_performing_items = sorted(
        [
            {
                'item_id': item.id,
                'name': item.food_name,
                'quantity': sold_by_item.get(item.id, {}).get('quantity', 0),
                'gross_sales': sold_by_item.get(
                    item.id, {}
                ).get('gross_sales', Decimal('0.00')),
            }
            for item in all_items
        ],
        key=lambda row: (row['quantity'], row['name']),
    )[:5]
    zero_sale_items = [
        {'item_id': item.id, 'name': item.food_name}
        for item in all_items
        if item.id not in sold_by_item
    ]
    unavailable_items = [
        {
            'item_id': item.id,
            'name': item.food_name,
            'restaurant': item.restaurant.rest_name,
        }
        for item in all_items
        if not item.is_available
    ]
    high_value_items = sorted(
        [
            {
                'item_id': item.id,
                'name': item.food_name,
                'price': item.food_price,
            }
            for item in all_items
        ],
        key=lambda row: (-row['price'], row['name']),
    )[:5]
    suggested_promotion_candidates = [
        item for item in low_performing_items if item['quantity'] <= 1
    ][:5]

    prep_orders = list(orders)
    accept_minutes = [
        _prep_minutes(order, 'CONFIRMED', 'PREPARING')
        for order in prep_orders
    ]
    ready_minutes = [
        _prep_minutes(order, 'PREPARING', 'READY_FOR_PICKUP')
        for order in prep_orders
    ]
    average_accept_minutes = _average(accept_minutes)
    average_prep_minutes = _average(ready_minutes)
    estimated_average = Restaurant.objects.filter(owner=user).aggregate(
        total=Sum('estimated_prep_minutes'),
        count=Count('id'),
    )
    expected_prep = (
        round(estimated_average['total'] / estimated_average['count'], 1)
        if estimated_average['total'] is not None and estimated_average['count']
        else None
    )
    slow_prep_warnings = []
    if average_prep_minutes is not None and expected_prep is not None:
        if average_prep_minutes > expected_prep:
            slow_prep_warnings.append({
                'code': 'prep_above_estimate',
                'message': (
                    f'Average prep time is {average_prep_minutes} minutes, '
                    f'above the listed {expected_prep} minutes.'
                ),
            })
    if average_accept_minutes is not None and average_accept_minutes > 10:
        slow_prep_warnings.append({
            'code': 'slow_acceptance',
            'message': 'Orders are taking more than 10 minutes to accept on average.',
        })
    ready_delay_warnings = [
        {
            'code': 'ready_for_pickup_delay',
            'message': 'Some orders take longer than expected to become ready for pickup.',
        }
    ] if average_prep_minutes is not None and average_prep_minutes > 35 else []

    reviews = RestaurantReview.objects.filter(
        restaurant__owner=user,
    ).select_related('restaurant').order_by('-created_at')
    rating_summary = reviews.aggregate(
        average_rating=Sum('rating'),
        review_count=Count('id'),
    )
    average_rating = (
        round(rating_summary['average_rating'] / rating_summary['review_count'], 2)
        if rating_summary['review_count'] else None
    )
    recent_review_issues = [
        {
            'restaurant': review.restaurant.rest_name,
            'rating': review.rating,
            'comment': review.comment,
            'created_at': review.created_at,
        }
        for review in reviews.filter(rating__lte=2)[:5]
    ]
    repeat_customers = orders.values('customer').annotate(
        order_count=Count('id', distinct=True)
    ).filter(order_count__gte=2).count()

    revenue_trend_summary = (
        'Sales are building from delivered orders.'
        if delivered_count else
        'No delivered sales yet.'
    )

    actions = []
    if best_selling_items:
        actions.append(
            f"Promote {best_selling_items[0]['name']} during peak meal hours."
        )
    if zero_sale_items:
        actions.append('Review items with zero sales and improve photos or pricing.')
    if unavailable_items:
        actions.append('Bring popular unavailable items back online when stock returns.')
    if cancellation_rate >= 20:
        actions.append('Reduce cancellations by checking availability before accepting orders.')
    if average_prep_minutes is not None and average_prep_minutes > 30:
        actions.append('Improve prep speed during peak hours.')
    if average_rating is not None and average_rating < 3.5:
        actions.append('Review recent low ratings and fix recurring quality issues.')
    if not actions:
        actions.append('Keep menu availability and prep time accurate to grow repeat orders.')

    return {
        'sales_insights': {
            'best_selling_items': best_selling_items,
            'low_performing_items': low_performing_items,
            'average_order_value': average_order_value,
            'revenue_trend_summary': revenue_trend_summary,
        },
        'menu_insights': {
            'items_with_zero_sales': zero_sale_items,
            'unavailable_items': unavailable_items,
            'high_value_items': high_value_items,
            'suggested_promotion_candidates': suggested_promotion_candidates,
        },
        'operations_insights': {
            'average_accept_minutes': average_accept_minutes,
            'average_prep_minutes': average_prep_minutes,
            'slow_prep_warnings': slow_prep_warnings,
            'cancellation_rate': cancellation_rate,
            'cancelled_orders': cancelled_count,
            'ready_for_pickup_delay_warnings': ready_delay_warnings,
        },
        'customer_insights': {
            'rating_summary': {
                'average_rating': average_rating,
                'review_count': rating_summary['review_count'],
            },
            'recent_review_issues': recent_review_issues,
            'repeat_customer_signals': {
                'repeat_customers': repeat_customers,
            },
        },
        'action_recommendations': actions,
    }

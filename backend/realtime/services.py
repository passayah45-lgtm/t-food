from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction


def _group_send(groups, payload):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    for group in sorted(set(filter(None, groups))):
        async_to_sync(channel_layer.group_send)(
            group,
            {
                'type': 'realtime.message',
                'payload': payload,
            },
        )


def _merchant_groups_for_order(order):
    owner_ids = (
        order.items.filter(food__restaurant__owner_id__isnull=False)
        .values_list('food__restaurant__owner_id', flat=True)
        .distinct()
    )
    return [f'merchant_{owner_id}' for owner_id in owner_ids]


def _branch_for_order(order):
    if getattr(order, 'pickup_branch_id', None):
        return order.pickup_branch
    first_item = order.items.all()[0] if order.items.all() else None
    return first_item.food.restaurant if first_item else None


def _operations_groups_for_order(order):
    groups = {'operations', 'operations_global'}
    scoped_groups = set()

    market_id = getattr(order, 'market_id', None)
    if market_id:
        scoped_groups.add(f'operations_market_{market_id}')

    branch = _branch_for_order(order)
    if branch:
        if branch.market_id:
            scoped_groups.add(f'operations_market_{branch.market_id}')
        if branch.country_code:
            scoped_groups.add(f'operations_country_{branch.country_code.upper()}')
        if branch.city_ref_id:
            scoped_groups.add(f'operations_city_{branch.city_ref_id}')
        if branch.area_ref_id:
            scoped_groups.add(f'operations_area_{branch.area_ref_id}')

    if not scoped_groups:
        return ['operations']
    return [*groups, *scoped_groups]


def _partner_group_for_order(order):
    try:
        partner = order.delivery.delivery_partner
    except AttributeError:
        return None
    if not partner:
        return None
    return f'partner_{partner.user_id}'


def broadcast_order_created(order_id):
    def publish():
        from orders.models import Order

        order = (
            Order.objects.filter(id=order_id)
            .prefetch_related('items__food__restaurant')
            .first()
        )
        if not order:
            return
        payload = {
            'type': 'order.created',
            'order_id': order.id,
            'status': order.status,
        }
        groups = [
            f'user_{order.customer_id}',
            *_operations_groups_for_order(order),
            *_merchant_groups_for_order(order),
        ]
        _group_send(groups, payload)

    transaction.on_commit(publish)


def broadcast_order_status_changed(order_id, status, previous_status):
    def publish():
        from orders.models import Order

        order = (
            Order.objects.filter(id=order_id)
            .select_related('delivery__delivery_partner')
            .prefetch_related('items__food__restaurant')
            .first()
        )
        if not order:
            return
        groups = [
            f'user_{order.customer_id}',
            *_operations_groups_for_order(order),
            _partner_group_for_order(order),
            *_merchant_groups_for_order(order),
        ]
        _group_send(
            groups,
            {
                'type': 'order.status_changed',
                'order_id': order.id,
                'status': status,
                'previous_status': previous_status,
            },
        )
        if status == 'READY_FOR_PICKUP':
            _group_send(
                ['partners_available', *_operations_groups_for_order(order)],
                {
                    'type': 'delivery.available_changed',
                    'order_id': order.id,
                    'status': status,
                },
            )

    transaction.on_commit(publish)


def broadcast_delivery_status_changed(delivery_id, status, previous_status):
    def publish():
        from delivery.models import Delivery

        delivery = (
            Delivery.objects.filter(id=delivery_id)
            .select_related('order__customer', 'delivery_partner')
            .prefetch_related('order__items__food__restaurant')
            .first()
        )
        if not delivery:
            return
        groups = [
            f'user_{delivery.order.customer_id}',
            f'partner_{delivery.delivery_partner.user_id}'
            if delivery.delivery_partner_id else None,
            *_operations_groups_for_order(delivery.order),
            *_merchant_groups_for_order(delivery.order),
        ]
        _group_send(
            groups,
            {
                'type': 'delivery.status_changed',
                'delivery_id': delivery.id,
                'order_id': delivery.order_id,
                'status': status,
                'previous_status': previous_status,
            },
        )

    transaction.on_commit(publish)

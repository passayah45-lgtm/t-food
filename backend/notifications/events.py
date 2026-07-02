import logging

from .models import Notification
from .services import notify_event

logger = logging.getLogger(__name__)


def _safe_notify_event(**kwargs):
    try:
        return notify_event(**kwargs)
    except Exception:
        logger.exception('Notification event delivery failed.')
        return None


def schedule_notification_event(**kwargs):
    # In-app notifications are written inside the same database transaction as
    # the completed business event, so a rollback removes them too. Realtime and
    # future external delivery remain deferred by the router's on_commit hooks.
    return _safe_notify_event(**kwargs)


def _first_order_branch(order):
    if not order:
        return None
    branch = getattr(order, 'pickup_branch', None)
    if branch:
        return branch
    first_item = (
        order.items
        .select_related('food__restaurant')
        .first()
    )
    return first_item.food.restaurant if first_item else None


def _merchant_from_branch(branch):
    owner = getattr(branch, 'owner', None)
    return getattr(owner, 'merchant_profile', None) if owner else None


def _merchant_from_order(order):
    branch = _first_order_branch(order)
    if branch:
        return _merchant_from_branch(branch)
    first_item = (
        order.items
        .select_related('food__restaurant__owner__merchant_profile')
        .first()
    )
    if not first_item:
        return None
    return getattr(first_item.food.restaurant.owner, 'merchant_profile', None)


def _scope_for_branch(branch):
    if not branch:
        return {}
    market = getattr(branch, 'market', None)
    city = getattr(branch, 'city_ref', None)
    area = getattr(branch, 'area_ref', None)
    return {
        'branch': branch,
        'market': market,
        'country_code': getattr(branch, 'country_code', None) or getattr(market, 'country_code', None),
        'city': city,
        'area': area,
    }


def _scope_for_order(order):
    branch = _first_order_branch(order)
    scope = _scope_for_branch(branch)
    scope.update({
        'order': order,
        'market': getattr(order, 'market', None) or scope.get('market'),
    })
    if not scope.get('country_code') and scope.get('market'):
        scope['country_code'] = getattr(scope['market'], 'country_code', None)
    return scope


def _order_payload(order, *, title, message, intent='informational', metadata=None):
    return {
        'title': title,
        'message': message,
        'intent': intent,
        'metadata': {
            'order_id': order.id,
            **(metadata or {}),
        },
    }


ORDER_EVENT_CONFIG = {
    'placed': (
        'order.placed',
        Notification.CATEGORY_ORDER,
        Notification.PRIORITY_NORMAL,
        'Order #{id} placed',
        'Your order was placed successfully.',
        'informational',
    ),
    'confirmed': (
        'order.confirmed',
        Notification.CATEGORY_ORDER,
        Notification.PRIORITY_HIGH,
        'Order #{id} confirmed',
        'This order is ready for merchant acceptance.',
        'informational',
    ),
    'accepted': (
        'order.accepted',
        Notification.CATEGORY_ORDER,
        Notification.PRIORITY_NORMAL,
        'Order #{id} accepted',
        'The merchant accepted this order.',
        'kitchen',
    ),
    'preparing': (
        'order.preparing',
        Notification.CATEGORY_ORDER,
        Notification.PRIORITY_NORMAL,
        'Order #{id} is being prepared',
        'The merchant started preparing this order.',
        'kitchen',
    ),
    'ready_for_pickup': (
        'order.ready_for_pickup',
        Notification.CATEGORY_ORDER,
        Notification.PRIORITY_HIGH,
        'Order #{id} is ready',
        'This order is ready for pickup.',
        'dispatch',
    ),
    'rider_assigned': (
        'order.rider_assigned',
        Notification.CATEGORY_DELIVERY,
        Notification.PRIORITY_HIGH,
        'Delivery partner assigned for order #{id}',
        'A delivery partner has been assigned.',
        'dispatch',
    ),
    'picked_up': (
        'order.picked_up',
        Notification.CATEGORY_DELIVERY,
        Notification.PRIORITY_NORMAL,
        'Order #{id} picked up',
        'Your delivery partner picked up the order.',
        'dispatch',
    ),
    'on_the_way': (
        'order.on_the_way',
        Notification.CATEGORY_DELIVERY,
        Notification.PRIORITY_NORMAL,
        'Order #{id} is on the way',
        'Your order is on the way.',
        'dispatch',
    ),
    'delivered': (
        'order.delivered',
        Notification.CATEGORY_DELIVERY,
        Notification.PRIORITY_HIGH,
        'Order #{id} delivered',
        'Your order was delivered.',
        'informational',
    ),
    'cancelled': (
        'order.cancelled',
        Notification.CATEGORY_ORDER,
        Notification.PRIORITY_HIGH,
        'Order #{id} cancelled',
        'This order was cancelled.',
        'informational',
    ),
    'expired': (
        'order.expired',
        Notification.CATEGORY_PAYMENT,
        Notification.PRIORITY_NORMAL,
        'Payment time expired for order #{id}',
        'This order expired before payment was completed.',
        'informational',
    ),
}


def notify_order_event(order, event, *, actor=None, delivery=None, message=None):
    if not order:
        return
    config = ORDER_EVENT_CONFIG[event]
    event_type, category, priority, title, default_message, intent = config
    branch = _first_order_branch(order)
    merchant = _merchant_from_order(order)
    recipients = {'customer': order.customer}
    if merchant:
        recipients['merchant'] = merchant
        recipients['merchant_staff'] = {
            'merchant': merchant,
            'branch': branch,
        }
    if delivery and getattr(delivery, 'delivery_partner_id', None):
        recipients['delivery_partner'] = delivery.delivery_partner
    if event in {'placed', 'confirmed', 'cancelled', 'expired'}:
        recipients['operations'] = {'scope': _scope_for_order(order)}
    payload = _order_payload(
        order,
        title=title.format(id=order.id),
        message=message or default_message,
        intent=intent,
        metadata={'event': event},
    )
    schedule_notification_event(
        event_type=event_type,
        actor=actor,
        recipients=recipients,
        subject=order,
        scope=_scope_for_order(order),
        payload=payload,
        priority=priority,
        category=category,
        action_url=f'/orders/{order.id}',
        idempotency_key=f'{event_type}:{order.id}',
    )


def notify_payment_event(payment, event, *, actor=None, support_ticket=None):
    if not payment:
        return
    order = payment.order
    event_map = {
        'confirmed': ('payment.confirmed', 'Payment confirmed', 'Payment was confirmed for this order.'),
        'cod_confirmed': ('payment.cod_confirmed', 'COD confirmed', 'Cash on delivery payment was confirmed.'),
        'refund_requested': ('payment.refund_requested', 'Refund requested', 'A refund was requested.'),
        'refund_processing': ('payment.refund_processing', 'Refund processing', 'A refund is being processed.'),
        'refund_completed': ('payment.refund_completed', 'Refund completed', 'The refund was completed.'),
    }
    event_type, title, message = event_map[event]
    recipients = {'customer': order.customer}
    if event.startswith('refund'):
        recipients['operations'] = {'scope': _scope_for_order(order)}
        merchant = _merchant_from_order(order)
        if merchant:
            recipients['merchant'] = merchant
            recipients['merchant_staff'] = {'merchant': merchant, 'branch': _first_order_branch(order)}
    schedule_notification_event(
        event_type=event_type,
        actor=actor,
        recipients=recipients,
        subject=order,
        scope=_scope_for_order(order),
        payload=_order_payload(
            order,
            title=f'{title} for order #{order.id}',
            message=message,
            intent='finance' if event.startswith('refund') else 'payment',
            metadata={
                'payment_id': payment.id,
                'support_ticket_id': getattr(support_ticket, 'id', None),
            },
        ),
        priority=Notification.PRIORITY_HIGH if event.startswith('refund') else Notification.PRIORITY_NORMAL,
        category=Notification.CATEGORY_PAYMENT,
        action_url=f'/orders/{order.id}',
        idempotency_key=(
            f'{event_type}:{payment.id}:ticket:{support_ticket.id}'
            if support_ticket else f'{event_type}:{payment.id}'
        ),
    )


def notify_payout_event(subject, event, *, actor=None):
    if event.startswith('merchant'):
        order = subject
        merchant = _merchant_from_order(order)
        if not merchant:
            return
        recipients = {
            'merchant': merchant,
            'merchant_staff': {
                'merchant': merchant,
                'branch': _first_order_branch(order),
            },
        }
        amount = order.merchant_payout
        key_id = order.id
        scope = _scope_for_order(order)
        action_url = '/merchant/dashboard'
    else:
        delivery = subject
        order = delivery.order
        recipients = {'delivery_partner': delivery.delivery_partner}
        amount = delivery.partner_fee
        key_id = delivery.id
        scope = _scope_for_order(order)
        action_url = '/partner/dashboard'
    paid = event.endswith('paid')
    event_type = f'payout.{event}'
    title = 'Payout paid' if paid else 'Payout available'
    if event == 'partner_paid':
        title = f'Payout sent for order #{order.id}'
    if event == 'merchant_paid':
        title = f'Merchant payout sent for order #{order.id}'
    schedule_notification_event(
        event_type=event_type,
        actor=actor,
        recipients=recipients,
        subject=order,
        scope=scope,
        payload=_order_payload(
            order,
            title=title,
            message=f'Payout amount {amount} is {"paid" if paid else "available"}.',
            intent='finance',
            metadata={'payout_event': event, 'amount': str(amount)},
        ),
        priority=Notification.PRIORITY_NORMAL,
        category=Notification.CATEGORY_PAYMENT,
        action_url=action_url,
        idempotency_key=f'{event_type}:{key_id}',
    )


def notify_verification_event(subject, event, *, actor=None):
    event_type = f'verification.{event}'
    title_map = {
        'merchant_pending': 'Merchant verification pending',
        'merchant_approved': 'Merchant account approved',
        'merchant_rejected': 'Merchant account suspended',
        'partner_pending': 'Delivery partner verification pending',
        'partner_approved': 'Delivery partner account approved',
        'partner_rejected': 'Delivery partner account suspended',
        'staff_pending': 'Staff verification pending',
        'staff_approved': 'Staff verification approved',
        'staff_rejected': 'Staff verification rejected',
        'staff_suspended': 'Staff verification suspended',
        'staff_more_info_requested': 'More staff verification information requested',
    }
    scope = {}
    recipients = {}
    subject_id = getattr(subject, 'id', 'unknown')
    if event.startswith('merchant'):
        recipients = {'users': [subject.user]}
        first_branch = subject.user.owned_restaurants.select_related(
            'market', 'city_ref', 'area_ref'
        ).first()
        scope = _scope_for_branch(first_branch)
    elif event.startswith('partner'):
        recipients = {'delivery_partner': subject}
    elif event.startswith('staff'):
        recipients = {'users': [subject.user], 'merchant': subject.merchant}
        first_access = subject.branch_access.select_related(
            'branch__market', 'branch__city_ref', 'branch__area_ref'
        ).first()
        scope = _scope_for_branch(first_access.branch if first_access else None)
    if event.endswith('pending'):
        recipients['operations'] = {'scope': scope}
    schedule_notification_event(
        event_type=event_type,
        actor=actor,
        recipients=recipients,
        subject=subject,
        scope=scope,
        payload={
            'title': title_map.get(event, 'Verification update'),
            'message': title_map.get(event, 'Verification status changed.'),
            'intent': 'informational',
            'metadata': {'subject_id': subject_id, 'verification_event': event},
        },
        priority=Notification.PRIORITY_HIGH if event.endswith('pending') else Notification.PRIORITY_NORMAL,
        category=Notification.CATEGORY_VERIFICATION,
        action_url='/operations',
        idempotency_key=f'{event_type}:{subject_id}',
    )


def notify_branch_event(branch, event, *, actor=None):
    merchant = _merchant_from_branch(branch)
    if not merchant:
        return
    event_type = f'branch.{event}'
    title = f'Branch {event.replace("_", " ")}'
    schedule_notification_event(
        event_type=event_type,
        actor=actor,
        recipients={
            'merchant': merchant,
            'merchant_staff': {'merchant': merchant, 'branch': branch},
            'operations': {'scope': _scope_for_branch(branch)},
        },
        subject=branch,
        scope=_scope_for_branch(branch),
        payload={
            'title': title.title(),
            'message': f'{branch.branch_name or branch.rest_name} was {event.replace("_", " ")}.',
            'intent': 'branch',
            'metadata': {'branch_id': branch.id, 'branch_event': event},
        },
        priority=Notification.PRIORITY_NORMAL,
        category=Notification.CATEGORY_MERCHANT,
        action_url='/merchant/dashboard',
        idempotency_key=f'{event_type}:{branch.id}',
    )


def notify_staff_event(staff_member, event, *, actor=None):
    merchant = staff_member.merchant
    event_type = f'staff.{event}'
    schedule_notification_event(
        event_type=event_type,
        actor=actor,
        recipients={
            'users': [staff_member.user],
            'merchant': merchant,
            'merchant_staff': {'merchant': merchant},
        },
        subject=staff_member,
        payload={
            'title': f'Staff {event.replace("_", " ")}'.title(),
            'message': f'{staff_member.user.get_full_name() or staff_member.user.username} staff status changed.',
            'intent': 'staff',
            'metadata': {'staff_member_id': staff_member.id, 'staff_event': event},
        },
        priority=Notification.PRIORITY_NORMAL,
        category=Notification.CATEGORY_STAFF,
        action_url='/merchant/dashboard',
        idempotency_key=f'{event_type}:{staff_member.id}',
    )


def notify_rider_event(rider, event, *, actor=None, branch=None):
    merchant = getattr(rider, 'merchant', None)
    branch = branch or getattr(rider, 'home_restaurant', None)
    event_type = f'rider.{event}'
    recipients = {}
    if merchant:
        recipients['merchant'] = merchant
        recipients['merchant_staff'] = {'merchant': merchant, 'branch': branch}
    if getattr(rider, 'partner', None):
        recipients['delivery_partner'] = rider.partner
    schedule_notification_event(
        event_type=event_type,
        actor=actor,
        recipients=recipients,
        subject=rider,
        scope=_scope_for_branch(branch),
        payload={
            'title': f'Rider {event.replace("_", " ")}'.title(),
            'message': 'A merchant rider status changed.',
            'intent': 'dispatch',
            'metadata': {'merchant_rider_id': rider.id, 'rider_event': event},
        },
        priority=Notification.PRIORITY_NORMAL,
        category=Notification.CATEGORY_RIDER,
        action_url='/merchant/dashboard',
        idempotency_key=f'{event_type}:{rider.id}',
    )


def notify_support_event(ticket, event, *, actor=None):
    order = ticket.order
    merchant = _merchant_from_order(order)
    recipients = {
        'customer': ticket.customer,
        'operations': {'scope': _scope_for_order(order)},
    }
    if merchant:
        recipients['merchant'] = merchant
        recipients['merchant_staff'] = {
            'merchant': merchant,
            'branch': _first_order_branch(order),
        }
    event_type = f'support.ticket_{event}'
    schedule_notification_event(
        event_type=event_type,
        actor=actor,
        recipients=recipients,
        subject=order,
        scope=_scope_for_order(order),
        payload=_order_payload(
            order,
            title=f'Support ticket #{ticket.id} {event.replace("_", " ")}',
            message='Support ticket status changed.',
            intent='support',
            metadata={
                'support_ticket_id': ticket.id,
                'support_event': event,
                'refund_status': ticket.refund_status,
            },
        ),
        priority=Notification.PRIORITY_HIGH if event == 'created' else Notification.PRIORITY_NORMAL,
        category=Notification.CATEGORY_SUPPORT,
        action_url='/support',
        idempotency_key=f'{event_type}:{ticket.id}:{ticket.updated_at.timestamp() if event == "updated" else ""}',
    )


def notify_operations_event(event_type, *, title, message, scope=None, priority=None, actor=None, metadata=None):
    schedule_notification_event(
        event_type=event_type,
        actor=actor,
        recipients={'operations': {'scope': scope or {}}},
        scope=scope or {},
        payload={
            'title': title,
            'message': message,
            'intent': 'informational',
            'metadata': metadata or {},
        },
        priority=priority or Notification.PRIORITY_NORMAL,
        category=Notification.CATEGORY_SYSTEM,
        action_url='/operations',
        idempotency_key=f'{event_type}:{metadata or {}}',
    )

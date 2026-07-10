import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from notifications.events import notify_order_event
from payments.models import Payment
from restaurants.models import Restaurant

from .models import Order


def _branch_order_prefix(branch):
    source = branch.branch_name or branch.rest_name or 'TFOO'
    cleaned = re.sub(r'[^A-Za-z0-9]', '', source).upper()
    return (cleaned or 'TFOO')[:4]


def _branch_local_date(branch, now=None):
    timezone_name = getattr(getattr(branch, 'market', None), 'timezone', '') or settings.TIME_ZONE
    try:
        tzinfo = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        tzinfo = ZoneInfo(settings.TIME_ZONE)
    return timezone.localtime(now or timezone.now(), tzinfo).date()


def assign_merchant_order_code(order):
    if order.merchant_order_code:
        return order
    if not order.pickup_branch_id:
        return order

    with transaction.atomic():
        branch = Restaurant.objects.select_for_update().select_related('market').get(
            id=order.pickup_branch_id
        )
        sequence_date = _branch_local_date(branch)
        last_sequence = (
            Order.objects.filter(
                pickup_branch=branch,
                merchant_sequence_date=sequence_date,
            )
            .exclude(id=order.id)
            .aggregate(value=Max('merchant_daily_sequence'))['value']
            or 0
        )
        daily_sequence = last_sequence + 1
        order.merchant_sequence_date = sequence_date
        order.merchant_daily_sequence = daily_sequence
        order.merchant_order_code = (
            f'{_branch_order_prefix(branch)}-{branch.id}-{sequence_date:%Y%m%d}-{daily_sequence:03d}'
        )
        order.save(update_fields=[
            'merchant_sequence_date',
            'merchant_daily_sequence',
            'merchant_order_code',
            'updated_at',
        ])
    return order


def expire_unpaid_orders(now=None, batch_size=100):
    now = now or timezone.now()
    order_ids = list(
        Order.objects.filter(
            status='PLACED',
            payment_expires_at__isnull=False,
            payment_expires_at__lte=now,
        ).values_list('id', flat=True)[:batch_size]
    )
    expired = 0
    for order_id in order_ids:
        with transaction.atomic():
            order = Order.objects.select_for_update().filter(
                id=order_id,
                status='PLACED',
                payment_expires_at__lte=now,
            ).first()
            if not order:
                continue
            payment = Payment.objects.select_for_update().filter(
                order=order
            ).first()
            if payment and payment.status == 'SUCCESS':
                order.payment_expires_at = None
                order.save(update_fields=['payment_expires_at', 'updated_at'])
                continue
            order.status = 'EXPIRED'
            order.merchant_payout_status = 'CANCELLED'
            order.save(update_fields=[
                'status', 'merchant_payout_status', 'updated_at'
            ])
            if payment and payment.status in ('PENDING', 'FAILED'):
                payment.status = 'CANCELLED'
                payment.save(update_fields=['status', 'updated_at'])
            notify_order_event(
                order,
                'expired',
                message='The unpaid order was closed. You can reorder whenever you are ready.',
            )
            expired += 1
    return expired

from django.db import transaction
from django.utils import timezone

from notifications.events import notify_order_event
from orders.models import Order
from payments.models import Payment


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

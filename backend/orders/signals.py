from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from events.services import publish_event
from orders.models import Order, OrderStatusEvent
from realtime.services import (
    broadcast_order_created,
    broadcast_order_status_changed,
)


STATUS_DETAILS = {
    'PLACED': ('CHECKOUT', 'Order created and awaiting payment.'),
    'CONFIRMED': ('PAYMENT', 'Payment or cash-on-delivery confirmation received.'),
    'PREPARING': ('MERCHANT', 'Merchant accepted the order and began preparation.'),
    'READY_FOR_PICKUP': ('MERCHANT', 'Order is ready for a delivery partner.'),
    'ON_THE_WAY': ('DELIVERY', 'Delivery partner is on the way to the customer.'),
    'DELIVERED': ('DELIVERY', 'Order was delivered to the customer.'),
    'CANCELLED': ('CANCELLATION', 'Order was cancelled.'),
    'EXPIRED': ('SYSTEM', 'Payment window expired before confirmation.'),
}


@receiver(pre_save, sender=Order)
def remember_previous_order_status(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_status = None
        return
    instance._previous_status = sender.objects.filter(pk=instance.pk).values_list(
        'status', flat=True
    ).first()


@receiver(post_save, sender=Order)
def record_order_status_event(sender, instance, created, **kwargs):
    previous = getattr(instance, '_previous_status', None)
    if not created and previous == instance.status:
        return
    source, description = STATUS_DETAILS.get(
        instance.status,
        ('SYSTEM', f'Order status changed to {instance.get_status_display()}.'),
    )
    OrderStatusEvent.objects.create(
        order=instance,
        status=instance.status,
        source=source,
        description=description,
    )
    if created:
        publish_event(
            event_name='order.created',
            aggregate_type='order',
            aggregate_id=instance.id,
            payload={
                'order_id': instance.id,
                'customer_id': instance.customer_id,
                'status': instance.status,
                'market_id': instance.market_id,
                'total_amount': str(instance.total_amount),
                'created_at': instance.created_at.isoformat(),
            },
        )
        broadcast_order_created(instance.id)
        return
    publish_event(
        event_name='order.status_changed',
        aggregate_type='order',
        aggregate_id=instance.id,
        payload={
            'order_id': instance.id,
            'customer_id': instance.customer_id,
            'previous_status': previous,
            'status': instance.status,
            'market_id': instance.market_id,
            'changed_at': instance.updated_at.isoformat(),
        },
    )
    broadcast_order_status_changed(instance.id, instance.status, previous)

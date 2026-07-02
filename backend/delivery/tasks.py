from celery import shared_task

from delivery.models import Delivery
from delivery.services import notify_delivery_candidates
from fooddelivery.tasks import TFoodTask


@shared_task(
    bind=True,
    base=TFoodTask,
    name='delivery.tasks.notify_pending_delivery_candidates_task',
)
def notify_pending_delivery_candidates_task(self, batch_size=100):
    deliveries = (
        Delivery.objects.filter(
            delivery_partner__isnull=True,
            order__status='READY_FOR_PICKUP',
        )
        .select_related('order')
        .prefetch_related('order__items__food__restaurant')
        .order_by('delivery_date')[:batch_size]
    )
    notified = 0
    for delivery in deliveries:
        notified += notify_delivery_candidates(delivery)
    return notified


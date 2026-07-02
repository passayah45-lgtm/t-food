from celery import shared_task
from django.contrib.auth import get_user_model

from fooddelivery.tasks import TFoodTask
from notifications.models import Notification
from orders.models import Order


@shared_task(
    bind=True,
    base=TFoodTask,
    name='notifications.tasks.create_notification_task',
)
def create_notification_task(
    self,
    user_id,
    kind,
    title,
    message,
    order_id=None,
):
    user = get_user_model().objects.filter(id=user_id).first()
    if not user:
        return None
    order = Order.objects.filter(id=order_id).first() if order_id else None
    notification = Notification.objects.create(
        user=user,
        order=order,
        kind=kind,
        title=title,
        message=message,
    )
    return notification.id


from celery import shared_task

from fooddelivery.tasks import TFoodTask
from orders.services import expire_unpaid_orders


@shared_task(
    bind=True,
    base=TFoodTask,
    name='orders.tasks.expire_unpaid_orders_task',
)
def expire_unpaid_orders_task(self, batch_size=100):
    return expire_unpaid_orders(batch_size=batch_size)


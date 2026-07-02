import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from delivery.models import Delivery
from delivery.services import notify_delivery_candidates
from fooddelivery.observability import touch_worker_heartbeat
from orders.services import expire_unpaid_orders


class Command(BaseCommand):
    help = 'Expands delivery offer waves and notifies newly eligible partners.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('T-Food dispatch worker started'))
        while True:
            close_old_connections()
            touch_worker_heartbeat('dispatch_worker')
            deliveries = Delivery.objects.filter(
                delivery_partner__isnull=True,
                order__status='READY_FOR_PICKUP',
            ).select_related('order').prefetch_related(
                'order__items__food__restaurant'
            )
            for delivery in deliveries:
                notify_delivery_candidates(delivery)
            expire_unpaid_orders()
            time.sleep(15)

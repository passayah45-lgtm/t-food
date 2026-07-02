import logging

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from events.models import OutboxEvent


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Publishes pending transactional outbox events.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100)

    def handle(self, *args, **options):
        limit = max(1, options['limit'])
        published = 0

        while published < limit:
            event = self.claim_next_event()
            if not event:
                break
            try:
                self.publish(event)
                event.mark_published()
                published += 1
            except Exception as exc:  # pragma: no cover - defensive relay guard
                event.mark_failed(exc)
                logger.exception('Failed to relay outbox event %s', event.event_id)

        self.stdout.write(self.style.SUCCESS(f'Published {published} outbox event(s).'))

    @transaction.atomic
    def claim_next_event(self):
        queryset = (
            OutboxEvent.objects.select_for_update(skip_locked=True)
            .filter(
                status=OutboxEvent.STATUS_PENDING,
                available_at__lte=timezone.now(),
            )
            .order_by('available_at', 'id')
        )
        return queryset.first()

    def publish(self, event):
        logger.info(
            'Relaying outbox event',
            extra={
                'event_id': str(event.event_id),
                'event_name': event.event_name,
                'event_version': event.event_version,
                'aggregate_type': event.aggregate_type,
                'aggregate_id': event.aggregate_id,
            },
        )


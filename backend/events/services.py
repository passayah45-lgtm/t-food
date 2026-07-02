import hashlib
import json

from django.db import transaction

from fooddelivery.correlation import get_correlation_id

from .models import InboxEvent, OutboxEvent


def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), default=str)


def payload_hash(payload) -> str:
    return hashlib.sha256(canonical_json(payload).encode('utf-8')).hexdigest()


def publish_event(
    *,
    event_name: str,
    aggregate_type: str,
    aggregate_id,
    payload: dict,
    event_version: int = 1,
    headers: dict | None = None,
) -> OutboxEvent:
    event_headers = {
        'correlation_id': get_correlation_id(),
        **(headers or {}),
    }
    return OutboxEvent.objects.create(
        event_name=event_name,
        event_version=event_version,
        aggregate_type=aggregate_type,
        aggregate_id=str(aggregate_id),
        payload=payload,
        headers=event_headers,
    )


@transaction.atomic
def record_inbox_event(
    *,
    event_id,
    consumer: str,
    event_name: str,
    payload: dict,
    event_version: int = 1,
    headers: dict | None = None,
) -> tuple[InboxEvent, bool]:
    event, created = InboxEvent.objects.get_or_create(
        event_id=event_id,
        consumer=consumer,
        defaults={
            'event_name': event_name,
            'event_version': event_version,
            'payload_hash': payload_hash(payload),
            'payload': payload,
            'headers': headers or {},
        },
    )
    return event, created

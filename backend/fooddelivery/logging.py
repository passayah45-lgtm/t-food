import json
import logging

from django.utils import timezone

from .correlation import get_correlation_id


SAFE_EXTRA_FIELDS = {
    'request_id',
    'user_id',
    'operation',
    'duration_ms',
    'method',
    'path',
    'status_code',
    'service',
    'task_id',
    'task_name',
    'queue',
    'worker',
}


class CorrelationIdFilter(logging.Filter):
    def filter(self, record):
        record.correlation_id = get_correlation_id()
        if not getattr(record, 'request_id', None):
            record.request_id = record.correlation_id
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            'timestamp': timezone.now().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'correlation_id': getattr(record, 'correlation_id', ''),
        }
        for field in SAFE_EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload['exception'] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)

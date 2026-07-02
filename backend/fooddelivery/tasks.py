import logging

from celery import shared_task
from celery import Task
from django.db import DatabaseError, OperationalError


logger = logging.getLogger(__name__)


class TFoodTask(Task):
    abstract = True
    autoretry_for = (OperationalError,)
    retry_backoff = True
    retry_jitter = True
    retry_kwargs = {'max_retries': 3}

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning(
            'Retrying Celery task',
            extra={
                'task_id': task_id,
                'task_name': self.name,
                'exception': str(exc),
            },
        )
        super().on_retry(exc, task_id, args, kwargs, einfo)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.exception(
            'Celery task failed',
            extra={
                'task_id': task_id,
                'task_name': self.name,
                'exception': str(exc),
            },
        )
        super().on_failure(exc, task_id, args, kwargs, einfo)


TRANSIENT_DB_ERRORS = (OperationalError, DatabaseError)


@shared_task(
    bind=True,
    base=TFoodTask,
    name='fooddelivery.tasks.record_celery_beat_heartbeat_task',
)
def record_celery_beat_heartbeat_task(self):
    from fooddelivery.observability import touch_worker_heartbeat

    touch_worker_heartbeat('celery_beat')
    return 'ok'

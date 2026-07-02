import os

from celery import Celery
from celery.signals import beat_init, heartbeat_sent, worker_ready


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fooddelivery.settings')

app = Celery('fooddelivery')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


@worker_ready.connect
def record_worker_ready(**kwargs):
    from fooddelivery.observability import touch_worker_heartbeat

    touch_worker_heartbeat('celery_worker')


@heartbeat_sent.connect
def record_worker_heartbeat(**kwargs):
    from fooddelivery.observability import touch_worker_heartbeat

    touch_worker_heartbeat('celery_worker')


@beat_init.connect
def record_beat_heartbeat(**kwargs):
    from fooddelivery.observability import touch_worker_heartbeat

    touch_worker_heartbeat('celery_beat')

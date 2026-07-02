#!/bin/sh
set -e

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

if [ "${SERVICE_MODE:-web}" = "dispatch" ]; then
  exec python manage.py dispatch_worker
fi

if [ "${SERVICE_MODE:-web}" = "celery_worker" ]; then
  exec celery -A fooddelivery worker \
    -l "${CELERY_LOG_LEVEL:-INFO}" \
    -Q "${CELERY_WORKER_QUEUES:-critical,dispatch,notifications,maintenance,default}"
fi

if [ "${SERVICE_MODE:-web}" = "celery_beat" ]; then
  exec celery -A fooddelivery beat \
    -l "${CELERY_LOG_LEVEL:-INFO}" \
    --schedule "${CELERY_BEAT_SCHEDULE_FILE:-/app/celerybeat-schedule}"
fi

if [ "${RUN_MIGRATIONS:-True}" = "True" ]; then
  python manage.py migrate --noinput
fi

if [ "${RUN_COLLECTSTATIC:-True}" = "True" ]; then
  python manage.py collectstatic --noinput
fi
if [ "${SEED_DEMO_DATA:-False}" = "True" ]; then
  python manage.py seed_demo
fi

exec daphne \
  -b 0.0.0.0 \
  -p 8000 \
  fooddelivery.asgi:application

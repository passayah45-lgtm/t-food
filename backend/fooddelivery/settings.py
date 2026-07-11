import os
import sys
from pathlib import Path
from datetime import timedelta
from ctypes.util import find_library
from django.core.exceptions import ImproperlyConfigured
import dj_database_url
from kombu import Exchange, Queue
from fooddelivery.env_validation import enforce_startup_environment

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get('DEBUG', 'True') == 'True'
RUNNING_TESTS = 'test' in sys.argv
APP_ENV = os.environ.get(
    'APP_ENV',
    os.environ.get('ENVIRONMENT', 'development' if DEBUG else 'production'),
).strip().lower()


def env_bool(name, default):
    value = os.environ.get(name)
    if value is None:
        return bool(default)
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


from operations_access.config import (  # noqa: E402
    default_legacy_operations_access,
    validate_legacy_operations_access,
)


_legacy_operations_access_default = (
    True
    if RUNNING_TESTS
    else default_legacy_operations_access(APP_ENV, debug=DEBUG)
)
ALLOW_LEGACY_GLOBAL_OPERATIONS_ACCESS = env_bool(
    'ALLOW_LEGACY_GLOBAL_OPERATIONS_ACCESS',
    _legacy_operations_access_default,
)
if not RUNNING_TESTS:
    validate_legacy_operations_access(APP_ENV, ALLOW_LEGACY_GLOBAL_OPERATIONS_ACCESS)

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-local-development-only'
    else:
        raise ImproperlyConfigured('DJANGO_SECRET_KEY is required when DEBUG=False.')


def env_list(name, default=''):
    return [value.strip() for value in os.environ.get(name, default).split(',') if value.strip()]


ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1')

GEODJANGO_AVAILABLE = bool(
    os.environ.get('GDAL_LIBRARY_PATH')
    or find_library('gdal')
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    *(["django.contrib.gis"] if GEODJANGO_AVAILABLE else []),
    # third party
    'channels',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    # project apps
    'customers',
    'markets',
    'ledger',
    'events',
    'realtime',
    'verifications',
    'intelligence',
    'operations_access',
    'user_preferences',
    'restaurants',
    'merchant_staff',
    'orders',
    'delivery',
    'payments',
    'notifications',
    'api',
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "fooddelivery.middleware.CorrelationIdMiddleware",
    "fooddelivery.middleware.RequestLoggingMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "fooddelivery.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "fooddelivery.wsgi.application"
ASGI_APPLICATION = "fooddelivery.asgi.application"

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
elif os.environ.get('POSTGRES_HOST'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('POSTGRES_DB', 'tfood'),
            'USER': os.environ.get('POSTGRES_USER', 'tfood'),
            'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''),
            'HOST': os.environ['POSTGRES_HOST'],
            'PORT': os.environ.get('POSTGRES_PORT', '5432'),
            'CONN_MAX_AGE': 600,
            'CONN_HEALTH_CHECKS': True,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

if GEODJANGO_AVAILABLE:
    database_engine = DATABASES['default'].get('ENGINE')
    if database_engine == 'django.db.backends.postgresql':
        DATABASES['default']['ENGINE'] = 'django.contrib.gis.db.backends.postgis'

REDIS_URL = os.environ.get('REDIS_URL', '')
if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 't-food-development-cache',
        }
    }

DASHBOARD_CACHE_ENABLED = (
    os.environ.get('DASHBOARD_CACHE_ENABLED', 'True') == 'True'
    and not RUNNING_TESTS
)
MONITORING_ENABLED = env_bool('MONITORING_ENABLED', True)
METRICS_ENABLED = env_bool('METRICS_ENABLED', True)
ERROR_REPORTING_ENABLED = env_bool('ERROR_REPORTING_ENABLED', False)
SLOW_QUERY_THRESHOLD_MS = int(os.environ.get('SLOW_QUERY_THRESHOLD_MS', '500'))

CHANNEL_REDIS_URL = os.environ.get(
    'CHANNEL_REDIS_URL',
    'redis://localhost:6379/4',
)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'realtime.channel_layers.TFoodRedisChannelLayer',
        'CONFIG': {
            'hosts': [CHANNEL_REDIS_URL],
        },
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL  = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}
MEDIA_URL   = "/media/"
MEDIA_ROOT  = BASE_DIR / "media"
PRIVATE_MEDIA_ROOT = Path(os.environ.get('PRIVATE_MEDIA_ROOT', BASE_DIR / 'private_media'))

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/delivery/partner/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend',
)
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@fooddelivery.com')
EMAIL_NOTIFICATIONS_ENABLED = env_bool('EMAIL_NOTIFICATIONS_ENABLED', False)
EMAIL_NOTIFICATION_SUBJECT_PREFIX = os.environ.get(
    'EMAIL_NOTIFICATION_SUBJECT_PREFIX',
    '[T-Food] ',
)
PUBLIC_APP_URL = os.environ.get('PUBLIC_APP_URL', 'http://localhost:5173').rstrip('/')

AI_ASSISTANT_ENABLED = env_bool('AI_ASSISTANT_ENABLED', False)
AI_ASSISTANT_PROVIDER = os.environ.get('AI_ASSISTANT_PROVIDER', 'openai').strip().lower()
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
OPENAI_ASSISTANT_MODEL = os.environ.get('OPENAI_ASSISTANT_MODEL', 'gpt-4.1-mini')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
ANTHROPIC_ASSISTANT_MODEL = os.environ.get(
    'ANTHROPIC_ASSISTANT_MODEL',
    'claude-3-5-haiku-latest',
)
AI_ASSISTANT_TIMEOUT_SECONDS = int(os.environ.get('AI_ASSISTANT_TIMEOUT_SECONDS', '20'))
AI_ASSISTANT_MAX_INPUT_CHARS = int(os.environ.get('AI_ASSISTANT_MAX_INPUT_CHARS', '2000'))

RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')
RAZORPAY_WEBHOOK_SECRET = os.environ.get('RAZORPAY_WEBHOOK_SECRET', '')
PAYMENT_TIMEOUT_MINUTES = int(os.environ.get('PAYMENT_TIMEOUT_MINUTES', '15'))
NOTIFICATIONS_ASYNC_ENABLED = os.environ.get(
    'NOTIFICATIONS_ASYNC_ENABLED', 'False'
) == 'True'

CELERY_BROKER_URL = os.environ.get(
    'CELERY_BROKER_URL',
    os.environ.get('REDIS_URL', 'redis://localhost:6379/2'),
)
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', CELERY_BROKER_URL)
CELERY_TASK_DEFAULT_QUEUE = 'default'
CELERY_TASK_DEFAULT_EXCHANGE = 'default'
CELERY_TASK_DEFAULT_ROUTING_KEY = 'default'
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_QUEUES = (
    Queue('critical', Exchange('critical'), routing_key='critical'),
    Queue('dispatch', Exchange('dispatch'), routing_key='dispatch'),
    Queue('notifications', Exchange('notifications'), routing_key='notifications'),
    Queue('maintenance', Exchange('maintenance'), routing_key='maintenance'),
    Queue('default', Exchange('default'), routing_key='default'),
)
CELERY_TASK_ROUTES = {
    'orders.tasks.expire_unpaid_orders_task': {
        'queue': 'maintenance',
        'routing_key': 'maintenance',
    },
    'delivery.tasks.notify_pending_delivery_candidates_task': {
        'queue': 'dispatch',
        'routing_key': 'dispatch',
    },
    'notifications.tasks.create_notification_task': {
        'queue': 'notifications',
        'routing_key': 'notifications',
    },
    'fooddelivery.tasks.record_celery_beat_heartbeat_task': {
        'queue': 'maintenance',
        'routing_key': 'maintenance',
    },
}
CELERY_BEAT_SCHEDULE = {
    'expire-unpaid-orders-every-minute': {
        'task': 'orders.tasks.expire_unpaid_orders_task',
        'schedule': 60.0,
        'options': {
            'queue': 'maintenance',
            'routing_key': 'maintenance',
        },
    },
    'notify-pending-delivery-candidates-every-15-seconds': {
        'task': 'delivery.tasks.notify_pending_delivery_candidates_task',
        'schedule': 15.0,
        'options': {
            'queue': 'dispatch',
            'routing_key': 'dispatch',
        },
    },
    'record-celery-beat-heartbeat-every-minute': {
        'task': 'fooddelivery.tasks.record_celery_beat_heartbeat_task',
        'schedule': 60.0,
        'options': {
            'queue': 'maintenance',
            'routing_key': 'maintenance',
        },
    },
}

# ──────────────────────────────────────────────
# Django REST Framework
# ──────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'anon': os.environ.get('THROTTLE_ANON_RATE', '1000/day'),
        'user': os.environ.get('THROTTLE_USER_RATE', '5000/day'),
        'auth_login': os.environ.get('THROTTLE_LOGIN_RATE', '10/minute'),
        'auth_register': os.environ.get('THROTTLE_REGISTER_RATE', '5/hour'),
        'auth_refresh': os.environ.get('THROTTLE_REFRESH_RATE', '60/minute'),
        'password_reset': os.environ.get('THROTTLE_PASSWORD_RESET_RATE', '5/hour'),
        'password_reset_confirm': os.environ.get(
            'THROTTLE_PASSWORD_CONFIRM_RATE', '10/hour'
        ),
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
}

# ──────────────────────────────────────────────
# JWT Settings
# ──────────────────────────────────────────────
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS':  True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ──────────────────────────────────────────────
# CORS  (allow React dev server)
# ──────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = env_list(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:5173,http://127.0.0.1:5173',
)
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS')

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True') == 'True'
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

if not RUNNING_TESTS:
    enforce_startup_environment(APP_ENV, DEBUG, os.environ)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'correlation_id': {
            '()': 'fooddelivery.logging.CorrelationIdFilter',
        },
    },
    'formatters': {
        'json': {
            '()': 'fooddelivery.logging.JsonFormatter',
        },
        'console': {
            'format': '%(levelname)s %(name)s [%(correlation_id)s] %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'filters': ['correlation_id'],
            'formatter': 'json' if not DEBUG else 'console',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.environ.get('LOG_LEVEL', 'INFO'),
    },
    'loggers': {
        'django.server': {
            'handlers': ['console'],
            'level': os.environ.get('DJANGO_SERVER_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}

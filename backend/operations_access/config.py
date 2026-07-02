from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


PRODUCTION_ENVIRONMENTS = {'production', 'prod'}
STAGING_ENVIRONMENTS = {'staging', 'stage'}


def normalize_app_env(value):
    return str(value or '').strip().lower() or 'development'


def default_legacy_operations_access(app_env, *, debug=False):
    normalized = normalize_app_env(app_env)
    if normalized in PRODUCTION_ENVIRONMENTS | STAGING_ENVIRONMENTS:
        return False
    return bool(debug)


def validate_legacy_operations_access(app_env, allow_legacy):
    normalized = normalize_app_env(app_env)
    if normalized in PRODUCTION_ENVIRONMENTS and allow_legacy:
        raise ImproperlyConfigured(
            'ALLOW_LEGACY_GLOBAL_OPERATIONS_ACCESS must be False when APP_ENV=production.'
        )


def legacy_global_operations_access_enabled():
    return bool(getattr(settings, 'ALLOW_LEGACY_GLOBAL_OPERATIONS_ACCESS', False))

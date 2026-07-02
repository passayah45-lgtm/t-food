import hashlib
import json

from django.conf import settings
from django.core.cache import cache


CACHE_VERSION = 'tf:v1:dashboard'


def _normalize_params(params):
    normalized = {}
    for key in sorted(params.keys()):
        values = params.getlist(key) if hasattr(params, 'getlist') else [params.get(key)]
        normalized[key] = [str(value) for value in values if value not in (None, '')]
    return normalized


def _actor_scope(actor_or_user):
    if actor_or_user is None:
        return {'kind': 'anonymous'}

    if hasattr(actor_or_user, 'assigned_market_ids'):
        return {
            'kind': 'operations',
            'user_id': getattr(getattr(actor_or_user, 'user', None), 'id', None),
            'role': getattr(actor_or_user, 'role', ''),
            'status': getattr(actor_or_user, 'status', ''),
            'is_global_scope': getattr(actor_or_user, 'is_global_scope', False),
            'is_legacy_staff': getattr(actor_or_user, 'is_legacy_staff', False),
            'markets': list(getattr(actor_or_user, 'assigned_market_ids', ())),
            'countries': list(getattr(actor_or_user, 'assigned_country_codes', ())),
            'cities': list(getattr(actor_or_user, 'assigned_city_ids', ())),
            'areas': list(getattr(actor_or_user, 'assigned_area_ids', ())),
        }

    user = actor_or_user
    if getattr(user, 'is_authenticated', False):
        return {
            'kind': 'user',
            'user_id': getattr(user, 'id', None),
            'is_staff': getattr(user, 'is_staff', False),
            'is_superuser': getattr(user, 'is_superuser', False),
        }
    return {'kind': 'anonymous'}


def cache_key_for_scope(prefix, actor_or_user=None, params=None, extra=None):
    payload = {
        'prefix': prefix,
        'scope': _actor_scope(actor_or_user),
        'params': _normalize_params(params or {}),
        'extra': extra or {},
    }
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str)
    digest = hashlib.sha256(raw.encode('utf-8')).hexdigest()
    return f'{CACHE_VERSION}:{prefix}:{digest}'


def get_cached_response_data(prefix, actor_or_user=None, params=None, extra=None):
    if not getattr(settings, 'DASHBOARD_CACHE_ENABLED', True):
        return None
    return cache.get(cache_key_for_scope(prefix, actor_or_user, params, extra))


def set_cached_response_data(prefix, data, timeout, actor_or_user=None, params=None, extra=None):
    if not getattr(settings, 'DASHBOARD_CACHE_ENABLED', True):
        return data
    cache.set(
        cache_key_for_scope(prefix, actor_or_user, params, extra),
        data,
        timeout=timeout,
    )
    return data

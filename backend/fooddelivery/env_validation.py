from django.core.exceptions import ImproperlyConfigured


PRODUCTION_ENVIRONMENTS = {'production', 'prod'}
PLACEHOLDER_TOKENS = {
    'replace-with',
    'your-domain.example',
    'example.com',
    'changeme',
}


def _env_value(env, name):
    value = env.get(name, '')
    return str(value).strip()


def _is_placeholder(value):
    normalized = str(value or '').strip().lower()
    return any(token in normalized for token in PLACEHOLDER_TOKENS)


def _is_missing_or_placeholder(env, name):
    value = _env_value(env, name)
    return not value or _is_placeholder(value)


def _list_values(value):
    return [item.strip().lower() for item in str(value or '').split(',') if item.strip()]


def validate_startup_environment(app_env, debug, env):
    """Return production startup validation errors without mutating settings."""
    normalized_env = str(app_env or '').strip().lower()
    if normalized_env not in PRODUCTION_ENVIRONMENTS:
        return []

    errors = []
    if debug:
        errors.append('DEBUG must be False when APP_ENV=production.')

    for name in (
        'DJANGO_SECRET_KEY',
        'ALLOWED_HOSTS',
        'CSRF_TRUSTED_ORIGINS',
        'PUBLIC_APP_URL',
        'PRIVATE_MEDIA_ROOT',
        'REDIS_URL',
        'CHANNEL_REDIS_URL',
    ):
        if _is_missing_or_placeholder(env, name):
            errors.append(f'{name} must be set to a production value.')

    if _is_missing_or_placeholder(env, 'DATABASE_URL') and _is_missing_or_placeholder(
        env, 'POSTGRES_PASSWORD'
    ):
        errors.append('DATABASE_URL or POSTGRES_PASSWORD must be set for production.')

    allowed_hosts = _list_values(env.get('ALLOWED_HOSTS', ''))
    if allowed_hosts and set(allowed_hosts).issubset({'localhost', '127.0.0.1'}):
        errors.append('ALLOWED_HOSTS must include the production domain.')

    csrf_origins = _list_values(env.get('CSRF_TRUSTED_ORIGINS', ''))
    if csrf_origins and not any(origin.startswith('https://') for origin in csrf_origins):
        errors.append('CSRF_TRUSTED_ORIGINS must include HTTPS production origins.')

    public_app_url = _env_value(env, 'PUBLIC_APP_URL').lower()
    if public_app_url and (
        public_app_url.startswith('http://localhost')
        or public_app_url.startswith('http://127.0.0.1')
    ):
        errors.append('PUBLIC_APP_URL must use the production HTTPS domain.')

    if _env_value(env, 'SECURE_SSL_REDIRECT').lower() in {'false', '0', 'no', 'off'}:
        errors.append('SECURE_SSL_REDIRECT must be enabled for production.')

    return errors


def enforce_startup_environment(app_env, debug, env):
    errors = validate_startup_environment(app_env, debug, env)
    if errors:
        raise ImproperlyConfigured(
            'Production environment validation failed: ' + ' '.join(errors)
        )

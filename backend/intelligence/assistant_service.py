import json
import urllib.error
import urllib.request

from django.conf import settings


SUPPORTED_ASSISTANT_SURFACES = {'support', 'operations', 'merchant', 'customer'}


class AssistantProviderError(Exception):
    pass


def assistant_is_configured():
    if not settings.AI_ASSISTANT_ENABLED:
        return False

    provider = settings.AI_ASSISTANT_PROVIDER
    if provider == 'openai':
        return bool(settings.OPENAI_API_KEY)
    if provider == 'anthropic':
        return bool(settings.ANTHROPIC_API_KEY)
    return False


def _surface_prompt(surface):
    base = (
        'You are T-Food Assistant. Give short, practical guidance for using the '
        'T-Food platform. You are read-only: you cannot change orders, payments, '
        'ledger entries, dispatch assignments, verification approvals, payouts, '
        'or private media. Never ask for passwords, JWT tokens, payment secrets, '
        'provider credentials, or full verification documents. If a user asks for '
        'a protected action, explain the safe next step inside T-Food.'
    )
    prompts = {
        'support': (
            'Help customers describe order issues, delivery problems, refunds, '
            'missing items, and support tickets. Do not promise a refund.'
        ),
        'customer': (
            'Help customers browse restaurants, use search, understand checkout, '
            'track orders, reviews, preferences, and notifications.'
        ),
        'merchant': (
            'Help merchant owners and staff understand onboarding, branches, menu, '
            'orders, riders, reviews, payouts, verification, and dashboard actions.'
        ),
        'operations': (
            'Help T-Food Operations understand dashboard sections, scopes, markets, '
            'cities, areas, verification queues, review moderation, support, and '
            'safe operational checks. Do not reveal secrets or bypass permissions.'
        ),
    }
    return f'{base}\n\nCurrent assistant surface: {surface}.\n{prompts[surface]}'


def _post_json(url, payload, headers):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers=headers,
        method='POST',
    )
    with urllib.request.urlopen(
        request,
        timeout=settings.AI_ASSISTANT_TIMEOUT_SECONDS,
    ) as response:
        return json.loads(response.read().decode('utf-8'))


def _ask_openai(system_prompt, cleaned_message):
    payload = {
        'model': settings.OPENAI_ASSISTANT_MODEL,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': cleaned_message},
        ],
        'temperature': 0.2,
        'max_tokens': 500,
    }
    data = _post_json(
        'https://api.openai.com/v1/chat/completions',
        payload,
        {
            'Authorization': f'Bearer {settings.OPENAI_API_KEY}',
            'Content-Type': 'application/json',
        },
    )
    return (
        data.get('choices', [{}])[0]
        .get('message', {})
        .get('content', '')
        .strip()
    )


def _ask_anthropic(system_prompt, cleaned_message):
    payload = {
        'model': settings.ANTHROPIC_ASSISTANT_MODEL,
        'system': system_prompt,
        'messages': [
            {'role': 'user', 'content': cleaned_message},
        ],
        'temperature': 0.2,
        'max_tokens': 500,
    }
    data = _post_json(
        'https://api.anthropic.com/v1/messages',
        payload,
        {
            'x-api-key': settings.ANTHROPIC_API_KEY,
            'anthropic-version': '2023-06-01',
            'Content-Type': 'application/json',
        },
    )
    text_parts = [
        block.get('text', '').strip()
        for block in data.get('content', [])
        if block.get('type') == 'text'
    ]
    return '\n'.join(part for part in text_parts if part)


def ask_tfood_assistant(surface, message):
    if surface not in SUPPORTED_ASSISTANT_SURFACES:
        raise ValueError('Unsupported assistant surface.')

    cleaned_message = (message or '').strip()
    if not cleaned_message:
        raise ValueError('Message is required.')

    max_chars = settings.AI_ASSISTANT_MAX_INPUT_CHARS
    if len(cleaned_message) > max_chars:
        cleaned_message = cleaned_message[:max_chars]

    if not assistant_is_configured():
        return {
            'enabled': False,
            'provider': 'disabled',
            'answer': (
                'T-Food Assistant is not enabled yet. Add the AI key on the '
                'server to turn on guided answers.'
            ),
        }

    try:
        system_prompt = _surface_prompt(surface)
        if settings.AI_ASSISTANT_PROVIDER == 'openai':
            answer = _ask_openai(system_prompt, cleaned_message)
        elif settings.AI_ASSISTANT_PROVIDER == 'anthropic':
            answer = _ask_anthropic(system_prompt, cleaned_message)
        else:
            answer = ''
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise AssistantProviderError('Assistant provider is unavailable.') from exc

    if not answer:
        raise AssistantProviderError('Assistant provider returned an empty answer.')

    return {
        'enabled': True,
        'provider': settings.AI_ASSISTANT_PROVIDER,
        'answer': answer,
    }

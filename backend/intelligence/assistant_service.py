import json
import urllib.error
import urllib.request

from django.conf import settings


SUPPORTED_ASSISTANT_SURFACES = {'support', 'operations', 'merchant', 'customer'}


class AssistantProviderError(Exception):
    pass


def assistant_is_configured():
    return (
        settings.AI_ASSISTANT_ENABLED
        and settings.AI_ASSISTANT_PROVIDER == 'openai'
        and bool(settings.OPENAI_API_KEY)
    )


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

    payload = {
        'model': settings.OPENAI_ASSISTANT_MODEL,
        'messages': [
            {'role': 'system', 'content': _surface_prompt(surface)},
            {'role': 'user', 'content': cleaned_message},
        ],
        'temperature': 0.2,
        'max_tokens': 500,
    }
    request = urllib.request.Request(
        'https://api.openai.com/v1/chat/completions',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {settings.OPENAI_API_KEY}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=settings.AI_ASSISTANT_TIMEOUT_SECONDS,
        ) as response:
            data = json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise AssistantProviderError('Assistant provider is unavailable.') from exc

    answer = (
        data.get('choices', [{}])[0]
        .get('message', {})
        .get('content', '')
        .strip()
    )
    if not answer:
        raise AssistantProviderError('Assistant provider returned an empty answer.')

    return {
        'enabled': True,
        'provider': settings.AI_ASSISTANT_PROVIDER,
        'answer': answer,
    }

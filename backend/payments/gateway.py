import base64
import hashlib
import hmac
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings


class PaymentGatewayError(Exception):
    pass


def online_payments_enabled():
    return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)


def create_razorpay_order(order):
    if not online_payments_enabled():
        raise PaymentGatewayError('Online payments are not configured.')

    credentials = base64.b64encode(
        f'{settings.RAZORPAY_KEY_ID}:{settings.RAZORPAY_KEY_SECRET}'.encode()
    ).decode()
    payload = json.dumps({
        'amount': int(order.total_amount * 100),
        'currency': 'INR',
        'receipt': f'tfood-order-{order.id}',
        'notes': {'tfood_order_id': str(order.id)},
    }).encode()
    request = Request(
        'https://api.razorpay.com/v1/orders',
        data=payload,
        method='POST',
        headers={
            'Authorization': f'Basic {credentials}',
            'Content-Type': 'application/json',
        },
    )
    try:
        with urlopen(request, timeout=15) as response:
            result = json.loads(response.read().decode())
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise PaymentGatewayError(
            'The payment provider is temporarily unavailable.'
        ) from exc

    provider_order_id = result.get('id')
    if not provider_order_id:
        raise PaymentGatewayError('The payment provider returned an invalid response.')
    return provider_order_id


def verify_razorpay_signature(provider_order_id, payment_id, signature):
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        f'{provider_order_id}|{payment_id}'.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_razorpay_webhook_signature(payload, signature):
    if not settings.RAZORPAY_WEBHOOK_SECRET or not signature:
        return False
    expected = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

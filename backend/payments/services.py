import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from notifications.events import notify_order_event, notify_payment_event
from ledger.services import (
    record_merchant_payout_available,
    record_merchant_payout_settled,
    record_partner_payout_available,
    record_partner_payout_settled,
    record_refund,
)
from markets.models import Market
from payments.gateway import PaymentGatewayError, online_payments_enabled
from payments.models import (
    MerchantPayoutAudit,
    PartnerPayoutAudit,
    Payment,
    PaymentWebhookEvent,
    RefundAudit,
)
from payments.providers.resolver import (
    PaymentProviderResolutionError,
    resolve_provider,
)


class OnlinePaymentsUnavailable(PaymentGatewayError):
    pass


@dataclass
class PaymentCreationResult:
    payment: Payment
    provider: object
    provider_order_id: str | None = None


@dataclass
class WebhookResult:
    data: dict
    status_code: int = 200


def confirm_order(order, method):
    if order.status != 'PLACED':
        return
    order.status = 'CONFIRMED'
    order.save(update_fields=['status', 'updated_at'])
    notify_order_event(order, 'confirmed')


def restore_expired_paid_order(order):
    if order.status != 'EXPIRED':
        return
    order.status = 'PLACED'
    order.merchant_payout_status = 'PENDING'
    order.save(update_fields=[
        'status', 'merchant_payout_status', 'updated_at'
    ])


class PaymentService:
    def create_payment(self, order, method, user=None, provider_code=None):
        provider = resolve_provider(
            market=order.market,
            payment_method=method,
            provider_code=provider_code,
        )
        payment, created = Payment.objects.get_or_create(
            order=order,
            defaults={
                'method': method,
                'status': 'PENDING',
                'market': order.market,
            },
        )
        if created and order.market and not payment.market_id:
            payment.market = order.market

        if payment.status in ('SUCCESS', 'REFUNDED', 'CANCELLED'):
            return PaymentCreationResult(payment=payment, provider=provider)

        if provider.code == 'cod':
            payment.method = 'COD'
            payment.status = 'PENDING'
            payment.provider = ''
            payment.provider_order_id = None
            payment.transaction_id = None
            if order.market and not payment.market_id:
                payment.market = order.market
            payment.save()
            confirm_order(order, method)
            notify_payment_event(payment, 'cod_confirmed')
            return PaymentCreationResult(payment=payment, provider=provider)

        if not online_payments_enabled():
            raise OnlinePaymentsUnavailable(
                'Online payments are not available yet. Please choose cash on delivery.'
            )

        payment.method = method
        payment.status = 'PENDING'
        payment.provider = provider.code.upper()
        if order.market and not payment.market_id:
            payment.market = order.market
        if not payment.provider_order_id:
            payment.provider_order_id = provider.create_payment(order, payment)
        payment.save()
        return PaymentCreationResult(
            payment=payment,
            provider=provider,
            provider_order_id=payment.provider_order_id,
        )

    @transaction.atomic
    def confirm_payment(self, payment, confirmation_payload=None, user=None):
        if payment.status == 'SUCCESS':
            return payment
        if payment.provider != 'RAZORPAY' or not payment.provider_order_id:
            raise ValidationError('No online payment is pending.')

        provider = resolve_provider(
            market=payment.market or payment.order.market,
            payment_method=payment.method,
            provider_code=payment.provider,
        )
        payload = confirmation_payload or {}
        if not provider.verify_customer_confirmation(payment, payload):
            raise ValidationError('Payment verification failed.')

        payment.status = 'SUCCESS'
        payment.transaction_id = payload.get('razorpay_payment_id', '')
        payment.save(update_fields=['status', 'transaction_id', 'updated_at'])
        restore_expired_paid_order(payment.order)
        confirm_order(payment.order, payment.method)
        notify_payment_event(payment, 'confirmed')
        return payment

    @transaction.atomic
    def handle_webhook(self, provider_code, request):
        if str(provider_code).lower() != 'razorpay':
            raise PaymentProviderResolutionError('Unknown payment provider.')
        if not settings.RAZORPAY_WEBHOOK_SECRET:
            return WebhookResult(
                {'detail': 'Webhook processing is not configured.'},
                status_code=503,
            )

        provider = resolve_provider(
            country='IN',
            currency='INR',
            payment_method='CARD',
            provider_code='razorpay',
        )
        raw_payload = request.body
        if not provider.verify_webhook(request):
            return WebhookResult(
                {'detail': 'Invalid webhook signature.'},
                status_code=401,
            )
        try:
            payload = provider.parse_webhook_event(request)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return WebhookResult({'detail': 'Invalid webhook payload.'}, status_code=400)

        event_type = payload.get('event', '')
        payload_hash = hashlib.sha256(raw_payload).hexdigest()
        event_id = request.headers.get('X-Razorpay-Event-Id') or payload_hash
        event, created = PaymentWebhookEvent.objects.get_or_create(
            event_id=event_id,
            defaults={
                'event_type': event_type,
                'payload_hash': payload_hash,
            },
        )
        if not created and event.processed:
            return WebhookResult({'status': 'already_processed'})
        if not created and event.payload_hash != payload_hash:
            return WebhookResult(
                {'detail': 'Webhook event ID conflict.'},
                status_code=400,
            )

        entity = (
            payload.get('payload', {})
            .get('payment', {})
            .get('entity', {})
        )
        provider_order_id = entity.get('order_id')
        if event_type not in ('payment.captured', 'payment.failed'):
            event.processed = True
            event.processed_at = timezone.now()
            event.save(update_fields=['processed', 'processed_at'])
            return WebhookResult({'status': 'ignored'})

        payment = Payment.objects.select_for_update().select_related(
            'order__customer'
        ).filter(
            provider='RAZORPAY',
            provider_order_id=provider_order_id,
        ).first()
        if not payment:
            event.processed = True
            event.processed_at = timezone.now()
            event.save(update_fields=['processed', 'processed_at'])
            return WebhookResult({'status': 'ignored'})

        expected_amount = int(payment.order.total_amount * 100)
        if entity.get('currency') != 'INR' or entity.get('amount') != expected_amount:
            return WebhookResult(
                {'detail': 'Webhook payment amount mismatch.'},
                status_code=400,
            )

        payment_id = entity.get('id')
        if event_type == 'payment.captured':
            if not payment_id:
                return WebhookResult(
                    {'detail': 'Webhook payment ID is missing.'},
                    status_code=400,
                )
            if payment.status != 'SUCCESS':
                payment.status = 'SUCCESS'
                payment.transaction_id = payment_id
                payment.save(update_fields=['status', 'transaction_id', 'updated_at'])
                restore_expired_paid_order(payment.order)
                confirm_order(payment.order, payment.method)
                notify_payment_event(payment, 'confirmed')
        elif payment.status != 'SUCCESS':
            payment.status = 'FAILED'
            payment.transaction_id = payment_id or payment.transaction_id
            payment.save(update_fields=['status', 'transaction_id', 'updated_at'])

        event.processed = True
        event.processed_at = timezone.now()
        event.save(update_fields=['processed', 'processed_at'])
        return WebhookResult({'status': 'processed'})


def _default_market():
    return (
        Market.objects.filter(slug='india').select_related('default_currency').first()
        or Market.objects.filter(is_active=True).select_related('default_currency').first()
    )


def _refund_market(order, payment):
    market = payment.market or order.market or _default_market()
    if not market or not market.default_currency_id:
        raise ValidationError({'market': ['A market is required to audit refunds.']})
    return market


def _refund_provider_code(payment):
    return str(payment.provider or payment.method or 'COD').upper()


def refund_idempotency_key(order, payment, support_ticket=None, amount=None):
    if support_ticket:
        return f'refund:{order.id}:{support_ticket.id}'
    return f'refund:{payment.id}:{amount}'


def record_refund_audit(
    *,
    order,
    payment,
    amount,
    reason,
    actor=None,
    support_ticket=None,
):
    market = _refund_market(order, payment)
    if not payment.market_id:
        payment.market = market
        payment.save(update_fields=['market', 'updated_at'])
    if not order.market_id:
        order.market = market
        order.save(update_fields=['market', 'updated_at'])

    idempotency_key = refund_idempotency_key(
        order,
        payment,
        support_ticket=support_ticket,
        amount=amount,
    )
    ledger_transaction = record_refund(
        payment,
        amount,
        reason,
        actor=actor,
        support_ticket=support_ticket,
    )
    audit, created = RefundAudit.objects.get_or_create(
        idempotency_key=idempotency_key,
        defaults={
            'order': order,
            'payment': payment,
            'support_ticket': support_ticket,
            'amount': amount,
            'currency': market.default_currency.code,
            'reason': reason or '',
            'initiated_by': actor,
            'provider_code': _refund_provider_code(payment),
            'status': RefundAudit.STATUS_SUCCEEDED,
            'ledger_transaction': ledger_transaction,
            'metadata': {
                'source': 'operations_support_refund',
                'support_ticket_id': support_ticket.id if support_ticket else None,
                'ledger_idempotency_key': ledger_transaction.idempotency_key,
            },
        },
    )
    if not created and not audit.ledger_transaction_id:
        audit.ledger_transaction = ledger_transaction
        audit.save(update_fields=['ledger_transaction', 'updated_at'])
    return audit


def _order_merchant_profile(order):
    first_item = order.items.select_related(
        'food__restaurant__owner__merchant_profile'
    ).first()
    if not first_item:
        raise ValidationError({'merchant': ['Order has no merchant item.']})
    merchant = getattr(first_item.food.restaurant.owner, 'merchant_profile', None)
    if not merchant:
        raise ValidationError({'merchant': ['Order merchant profile is required.']})
    return merchant


def payout_market_for_order(order):
    market = order.market or _default_market()
    if not market or not market.default_currency_id:
        raise ValidationError({'market': ['A market is required to audit payouts.']})
    if not order.market_id:
        order.market = market
        order.save(update_fields=['market', 'updated_at'])
    return market


def payout_market_for_delivery(delivery):
    market = delivery.market or delivery.order.market or _default_market()
    if not market or not market.default_currency_id:
        raise ValidationError({'market': ['A market is required to audit payouts.']})
    update_fields = []
    if not delivery.market_id:
        delivery.market = market
        update_fields.append('market')
    if not delivery.order.market_id:
        delivery.order.market = market
        delivery.order.save(update_fields=['market', 'updated_at'])
    if update_fields:
        delivery.save(update_fields=update_fields)
    return market


def merchant_payout_idempotency_key(order, status):
    return f'merchant-payout:{order.id}:{status}'


def partner_payout_idempotency_key(delivery, status):
    return f'partner-payout:{delivery.id}:{status}'


def record_merchant_payout_audit(*, order, status, actor=None):
    if Decimal(str(order.merchant_payout or 0)) <= 0:
        return None
    merchant = _order_merchant_profile(order)
    market = payout_market_for_order(order)
    normalized_status = str(status).upper()
    if normalized_status == MerchantPayoutAudit.STATUS_AVAILABLE:
        ledger_transaction = record_merchant_payout_available(order, actor=actor)
        paid_at = None
    elif normalized_status == MerchantPayoutAudit.STATUS_PAID:
        ledger_transaction = record_merchant_payout_settled(order, actor=actor)
        paid_at = order.merchant_paid_at
    else:
        raise ValidationError({'status': ['Unsupported merchant payout audit status.']})

    audit, created = MerchantPayoutAudit.objects.get_or_create(
        idempotency_key=merchant_payout_idempotency_key(order, normalized_status),
        defaults={
            'order': order,
            'merchant': merchant,
            'amount': order.merchant_payout,
            'currency': market.default_currency.code,
            'market': market,
            'country_code': market.country_code,
            'status': normalized_status,
            'marked_by': actor,
            'paid_at': paid_at,
            'ledger_transaction': ledger_transaction,
            'metadata': {
                'source': 'merchant_payout_flow',
                'ledger_idempotency_key': ledger_transaction.idempotency_key,
            },
        },
    )
    if not created and not audit.ledger_transaction_id:
        audit.ledger_transaction = ledger_transaction
        audit.save(update_fields=['ledger_transaction', 'updated_at'])
    return audit


def record_partner_payout_audit(*, delivery, status, actor=None):
    if not delivery.delivery_partner_id:
        raise ValidationError({'partner': ['Delivery partner is required.']})
    if Decimal(str(delivery.partner_fee or 0)) <= 0:
        return None
    market = payout_market_for_delivery(delivery)
    normalized_status = str(status).upper()
    if normalized_status == PartnerPayoutAudit.STATUS_AVAILABLE:
        ledger_transaction = record_partner_payout_available(delivery, actor=actor)
        paid_at = None
    elif normalized_status == PartnerPayoutAudit.STATUS_PAID:
        ledger_transaction = record_partner_payout_settled(delivery, actor=actor)
        paid_at = delivery.paid_at
    else:
        raise ValidationError({'status': ['Unsupported partner payout audit status.']})

    audit, created = PartnerPayoutAudit.objects.get_or_create(
        idempotency_key=partner_payout_idempotency_key(delivery, normalized_status),
        defaults={
            'delivery': delivery,
            'partner': delivery.delivery_partner,
            'amount': delivery.partner_fee,
            'currency': market.default_currency.code,
            'market': market,
            'country_code': market.country_code,
            'status': normalized_status,
            'marked_by': actor,
            'paid_at': paid_at,
            'ledger_transaction': ledger_transaction,
            'metadata': {
                'source': 'partner_payout_flow',
                'ledger_idempotency_key': ledger_transaction.idempotency_key,
            },
        },
    )
    if not created and not audit.ledger_transaction_id:
        audit.ledger_transaction = ledger_transaction
        audit.save(update_fields=['ledger_transaction', 'updated_at'])
    return audit

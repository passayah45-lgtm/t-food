from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .models import LedgerAccount, LedgerEntry, LedgerTransaction


def _amount(value):
    try:
        return Decimal(str(value or 0)).quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError('Financial event amount must be a valid decimal value.') from exc


def _market_from(*objects):
    for obj in objects:
        if not obj:
            continue
        market = getattr(obj, 'market', None)
        if market:
            return market
        order = getattr(obj, 'order', None)
        if order and getattr(order, 'market', None):
            return order.market
    raise ValidationError({'market': ['A market is required to write ledger events.']})


def _currency(market):
    if not market or not market.default_currency_id:
        raise ValidationError({'currency': ['A market default currency is required.']})
    return market.default_currency.code


def _provider(provider_code):
    code = str(provider_code or '').upper()
    if not code:
        raise ValidationError({'provider_code': ['Provider code is required.']})
    return code


def _account(account_type, market, name, *, provider_code='', user=None, merchant=None, partner=None):
    provider_code = str(provider_code or '').upper()
    lookup = {
        'market': market,
        'currency': _currency(market),
        'country_code': market.country_code,
        'account_type': account_type,
        'provider_code': provider_code,
        'user': user,
        'merchant': merchant,
        'partner': partner,
        'external_reference': '',
    }
    account, _ = LedgerAccount.objects.get_or_create(
        **lookup,
        defaults={'name': name},
    )
    return account


def _platform_account(market, provider_code):
    return _account(
        LedgerAccount.ACCOUNT_PLATFORM,
        market,
        f'T-Food {market.name} platform',
        provider_code=provider_code,
    )


def _provider_account(market, provider_code):
    account_type = (
        LedgerAccount.ACCOUNT_CASH_CLEARING
        if provider_code == 'COD'
        else LedgerAccount.ACCOUNT_PAYMENT_PROVIDER
    )
    return _account(
        account_type,
        market,
        f'{provider_code} clearing',
        provider_code=provider_code,
    )


def _refund_account(market, provider_code):
    return _account(
        LedgerAccount.ACCOUNT_REFUND_CLEARING,
        market,
        f'{provider_code} refund clearing',
        provider_code=provider_code,
    )


def _merchant_account(order, market, provider_code):
    first_item = order.items.select_related('food__restaurant__owner__merchant_profile').first()
    merchant = None
    user = None
    if first_item:
        user = first_item.food.restaurant.owner
        merchant = getattr(user, 'merchant_profile', None)
    return _account(
        LedgerAccount.ACCOUNT_MERCHANT,
        market,
        getattr(merchant, 'business_name', None) or f'Merchant for order #{order.id}',
        provider_code=provider_code,
        user=user,
        merchant=merchant,
    )


def _partner_account(delivery, market, provider_code):
    partner = delivery.delivery_partner
    return _account(
        LedgerAccount.ACCOUNT_PARTNER,
        market,
        getattr(partner, 'partner_name', None) or f'Partner for delivery #{delivery.id}',
        provider_code=provider_code,
        user=getattr(partner, 'user', None),
        partner=partner,
    )


def _fulfillment_account(market, provider_code):
    return _account(
        LedgerAccount.ACCOUNT_FULFILLMENT_CLEARING,
        market,
        f'{provider_code} fulfillment preview clearing',
        provider_code=provider_code,
    )


def _existing_or_create(idempotency_key, create):
    existing = LedgerTransaction.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        return existing
    try:
        with transaction.atomic():
            existing = LedgerTransaction.objects.filter(idempotency_key=idempotency_key).first()
            if existing:
                return existing
            return create()
    except IntegrityError:
        return LedgerTransaction.objects.get(idempotency_key=idempotency_key)


def _create_transaction(*, market, provider_code, transaction_type, idempotency_key, entries, **kwargs):
    provider_code = _provider(provider_code)
    return _existing_or_create(
        idempotency_key,
        lambda: LedgerTransaction.objects.create_balanced(
            market=market,
            country_code=market.country_code,
            currency=_currency(market),
            provider_code=provider_code,
            transaction_type=transaction_type,
            idempotency_key=idempotency_key,
            entries=entries,
            **kwargs,
        ),
    )


def record_order_financials(order):
    market = _market_from(order)
    provider_code = 'ORDER'
    total = _amount(order.total_amount)
    if total <= 0:
        raise ValidationError('Order total must be greater than zero.')

    credits = []
    platform_fee = _amount(order.platform_fee)
    merchant_payout = _amount(order.merchant_payout)
    delivery_fee = _amount(order.delivery_fee)
    if platform_fee > 0:
        credits.append({
            'account': _platform_account(market, provider_code),
            'direction': LedgerEntry.DIRECTION_CREDIT,
            'amount': platform_fee,
            'memo': 'Platform fee snapshot.',
        })
    if merchant_payout > 0:
        credits.append({
            'account': _merchant_account(order, market, provider_code),
            'direction': LedgerEntry.DIRECTION_CREDIT,
            'amount': merchant_payout,
            'memo': 'Merchant payout available snapshot.',
        })
    if delivery_fee > 0:
        credits.append({
            'account': _fulfillment_account(market, provider_code),
            'direction': LedgerEntry.DIRECTION_CREDIT,
            'amount': delivery_fee,
            'memo': 'Delivery fee snapshot.',
        })
    credited_total = sum((entry['amount'] for entry in credits), Decimal('0.00'))
    if credited_total != total:
        raise ValidationError('Order financial components must balance to order total.')

    return _create_transaction(
        market=market,
        provider_code=provider_code,
        transaction_type=LedgerTransaction.TYPE_ORDER_GROSS,
        idempotency_key=f'order-financials:{order.id}',
        source_type='order',
        source_id=str(order.id),
        order=order,
        metadata={
            'platform_fee': str(platform_fee),
            'merchant_payout': str(merchant_payout),
            'delivery_fee': str(delivery_fee),
        },
        entries=[
            {
                'account': _provider_account(market, provider_code),
                'direction': LedgerEntry.DIRECTION_DEBIT,
                'amount': total,
                'memo': 'Order gross amount snapshot.',
            },
            *credits,
        ],
    )


def record_cod_capture(payment):
    market = _market_from(payment)
    return _record_capture(payment, market, 'COD', f'cod-capture:{payment.id}')


def record_online_capture(payment, provider_code):
    market = _market_from(payment)
    provider_code = _provider(provider_code)
    return _record_capture(
        payment,
        market,
        provider_code,
        f'online-capture:{provider_code}:{payment.id}',
    )


def _record_capture(payment, market, provider_code, idempotency_key):
    amount = _amount(payment.order.total_amount)
    return _create_transaction(
        market=market,
        provider_code=provider_code,
        transaction_type=LedgerTransaction.TYPE_ORDER_GROSS,
        idempotency_key=idempotency_key,
        source_type='payment',
        source_id=str(payment.id),
        order=payment.order,
        payment=payment,
        entries=[
            {
                'account': _provider_account(market, provider_code),
                'direction': LedgerEntry.DIRECTION_DEBIT,
                'amount': amount,
                'memo': f'{provider_code} payment capture.',
            },
            {
                'account': _platform_account(market, provider_code),
                'direction': LedgerEntry.DIRECTION_CREDIT,
                'amount': amount,
                'memo': 'Payment captured for platform clearing.',
            },
        ],
    )


def record_refund(payment, amount, reason, actor=None, support_ticket=None):
    market = _market_from(payment)
    provider_code = _provider(payment.provider or payment.method or 'COD')
    refund_amount = _amount(amount)
    ticket_part = support_ticket.id if support_ticket else str(refund_amount)
    return _create_transaction(
        market=market,
        provider_code=provider_code,
        transaction_type=LedgerTransaction.TYPE_REFUND,
        idempotency_key=f'refund:{payment.id}:{ticket_part}',
        source_type='support_ticket' if support_ticket else 'payment',
        source_id=str(ticket_part),
        order=payment.order,
        payment=payment,
        created_by=actor,
        metadata={'reason': reason or ''},
        entries=[
            {
                'account': _platform_account(market, provider_code),
                'direction': LedgerEntry.DIRECTION_DEBIT,
                'amount': refund_amount,
                'memo': 'Refund liability recorded.',
            },
            {
                'account': _refund_account(market, provider_code),
                'direction': LedgerEntry.DIRECTION_CREDIT,
                'amount': refund_amount,
                'memo': 'Refund clearing recorded.',
            },
        ],
    )


def record_merchant_payout_settled(order, actor=None):
    market = _market_from(order)
    provider_code = 'PAYOUT'
    amount = _amount(order.merchant_payout)
    return _create_transaction(
        market=market,
        provider_code=provider_code,
        transaction_type=LedgerTransaction.TYPE_PAYOUT_SETTLEMENT,
        idempotency_key=f'merchant-payout:{order.id}',
        source_type='order',
        source_id=str(order.id),
        order=order,
        created_by=actor,
        entries=[
            {
                'account': _platform_account(market, provider_code),
                'direction': LedgerEntry.DIRECTION_DEBIT,
                'amount': amount,
                'memo': 'Merchant payout settlement.',
            },
            {
                'account': _merchant_account(order, market, provider_code),
                'direction': LedgerEntry.DIRECTION_CREDIT,
                'amount': amount,
                'memo': 'Merchant payout settled.',
            },
        ],
    )


def record_merchant_payout_available(order, actor=None):
    market = _market_from(order)
    provider_code = 'PAYOUT_AVAILABLE'
    amount = _amount(order.merchant_payout)
    return _create_transaction(
        market=market,
        provider_code=provider_code,
        transaction_type=LedgerTransaction.TYPE_MERCHANT_PAYOUT,
        idempotency_key=f'merchant-payout-available:{order.id}',
        source_type='order',
        source_id=str(order.id),
        order=order,
        created_by=actor,
        entries=[
            {
                'account': _platform_account(market, provider_code),
                'direction': LedgerEntry.DIRECTION_DEBIT,
                'amount': amount,
                'memo': 'Merchant payout became available.',
            },
            {
                'account': _merchant_account(order, market, provider_code),
                'direction': LedgerEntry.DIRECTION_CREDIT,
                'amount': amount,
                'memo': 'Merchant payout available.',
            },
        ],
    )


def record_partner_payout_settled(delivery, actor=None):
    market = _market_from(delivery)
    provider_code = 'PAYOUT'
    amount = _amount(delivery.partner_fee)
    return _create_transaction(
        market=market,
        provider_code=provider_code,
        transaction_type=LedgerTransaction.TYPE_PAYOUT_SETTLEMENT,
        idempotency_key=f'partner-payout:{delivery.id}',
        source_type='delivery',
        source_id=str(delivery.id),
        order=delivery.order,
        delivery=delivery,
        created_by=actor,
        entries=[
            {
                'account': _platform_account(market, provider_code),
                'direction': LedgerEntry.DIRECTION_DEBIT,
                'amount': amount,
                'memo': 'Partner payout settlement.',
            },
            {
                'account': _partner_account(delivery, market, provider_code),
                'direction': LedgerEntry.DIRECTION_CREDIT,
                'amount': amount,
                'memo': 'Partner payout settled.',
            },
        ],
    )


def record_partner_payout_available(delivery, actor=None):
    market = _market_from(delivery)
    provider_code = 'PAYOUT_AVAILABLE'
    amount = _amount(delivery.partner_fee)
    return _create_transaction(
        market=market,
        provider_code=provider_code,
        transaction_type=LedgerTransaction.TYPE_PARTNER_DELIVERY_FEE,
        idempotency_key=f'partner-payout-available:{delivery.id}',
        source_type='delivery',
        source_id=str(delivery.id),
        order=delivery.order,
        delivery=delivery,
        created_by=actor,
        entries=[
            {
                'account': _platform_account(market, provider_code),
                'direction': LedgerEntry.DIRECTION_DEBIT,
                'amount': amount,
                'memo': 'Partner payout became available.',
            },
            {
                'account': _partner_account(delivery, market, provider_code),
                'direction': LedgerEntry.DIRECTION_CREDIT,
                'amount': amount,
                'memo': 'Partner payout available.',
            },
        ],
    )


def record_fulfillment_preview(fulfillment_request):
    market = _market_from(fulfillment_request.order)
    provider_code = 'FULFILLMENT_PREVIEW'
    preview = fulfillment_request.settlement_preview or {}
    amount = _amount(
        preview.get('original_merchant_payout')
        or fulfillment_request.order.merchant_payout
    )
    fulfilling_share = _amount(
        preview.get('suggested_fulfilling_merchant_share') or amount
    )
    requesting_share = _amount(
        preview.get('suggested_requesting_merchant_share') or Decimal('0.00')
    )
    if fulfilling_share + requesting_share != amount:
        raise ValidationError('Fulfillment preview shares must balance to merchant payout.')

    return _create_transaction(
        market=market,
        provider_code=provider_code,
        transaction_type=LedgerTransaction.TYPE_FULFILLMENT_PREVIEW,
        idempotency_key=f'fulfillment-preview:{fulfillment_request.id}',
        source_type='merchant_fulfillment_request',
        source_id=str(fulfillment_request.id),
        order=fulfillment_request.order,
        fulfillment_request=fulfillment_request,
        metadata={
            'preview_only': True,
            'customer_visible': False,
            'payment_unchanged': True,
            'payout_unchanged': True,
        },
        entries=[
            {
                'account': _fulfillment_account(market, provider_code),
                'direction': LedgerEntry.DIRECTION_DEBIT,
                'amount': amount,
                'memo': 'Preview-only fulfillment settlement source.',
            },
            {
                'account': _account(
                    LedgerAccount.ACCOUNT_MERCHANT,
                    market,
                    fulfillment_request.fulfilling_merchant.business_name,
                    provider_code=provider_code,
                    user=fulfillment_request.fulfilling_merchant.user,
                    merchant=fulfillment_request.fulfilling_merchant,
                ),
                'direction': LedgerEntry.DIRECTION_CREDIT,
                'amount': fulfilling_share,
                'memo': 'Preview-only fulfilling merchant share.',
            },
            {
                'account': _account(
                    LedgerAccount.ACCOUNT_MERCHANT,
                    market,
                    fulfillment_request.requesting_merchant.business_name,
                    provider_code=provider_code,
                    user=fulfillment_request.requesting_merchant.user,
                    merchant=fulfillment_request.requesting_merchant,
                ),
                'direction': LedgerEntry.DIRECTION_CREDIT,
                'amount': requesting_share,
                'memo': 'Preview-only requesting merchant share.',
            },
        ],
    )

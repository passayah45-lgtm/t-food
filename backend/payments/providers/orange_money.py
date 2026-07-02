from .base import ExternalPaymentProvider


class OrangeMoneyProvider(ExternalPaymentProvider):
    code = 'orange_money'
    display_name = 'Orange Money'
    countries = ('GN', 'SN', 'CI', 'ML', 'BF')
    currencies = ('GNF', 'XOF')
    payment_methods = ('MOBILE_MONEY',)
    required_credentials = (
        'client_id',
        'client_secret',
        'merchant_key',
        'webhook_secret',
    )

    def build_create_payment_payload(self, order, payment):
        payload = super().build_create_payment_payload(order, payment)
        payload.update({
            'merchant_transaction_id': f'tfood-order-{order.id}-payment-{payment.id}',
            'subscriber_msisdn': order.contact_phone,
        })
        return payload

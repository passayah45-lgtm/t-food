from .base import ExternalPaymentProvider


class MTNMobileMoneyProvider(ExternalPaymentProvider):
    code = 'mtn_mobile_money'
    display_name = 'MTN Mobile Money'
    countries = ('GH', 'UG', 'RW', 'CI', 'CM', 'ZM', 'GN')
    currencies = ('GHS', 'UGX', 'RWF', 'XOF', 'XAF', 'ZMW', 'GNF')
    payment_methods = ('MOBILE_MONEY',)
    required_credentials = (
        'subscription_key',
        'api_user',
        'api_key',
        'target_environment',
        'webhook_secret',
    )

    def build_create_payment_payload(self, order, payment):
        payload = super().build_create_payment_payload(order, payment)
        payload.update({
            'external_id': f'tfood-order-{order.id}-payment-{payment.id}',
            'payer': {
                'party_id_type': 'MSISDN',
                'party_id': order.contact_phone,
            },
        })
        return payload

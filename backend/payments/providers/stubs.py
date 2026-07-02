from .base import CapabilityOnlyProvider


class AirtelMoneyProvider(CapabilityOnlyProvider):
    code = 'airtel_money'
    display_name = 'Airtel Money'
    countries = ('KE', 'UG', 'TZ', 'RW', 'ZM', 'MW', 'CD')
    currencies = ('KES', 'UGX', 'TZS', 'RWF', 'ZMW', 'MWK', 'CDF')
    payment_methods = ('MOBILE_MONEY',)

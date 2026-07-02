from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from markets.models import Currency, Market

from .models import (
    ImmutableLedgerError,
    LedgerAccount,
    LedgerEntry,
    LedgerTransaction,
)


class LedgerFoundationTests(TestCase):
    def setUp(self):
        self.india = Market.objects.get(slug='india')
        self.platform = LedgerAccount.objects.create(
            market=self.india,
            country_code='IN',
            currency='INR',
            account_type=LedgerAccount.ACCOUNT_PLATFORM,
            name='T-Food India platform',
            provider_code='RAZORPAY',
        )
        self.provider = LedgerAccount.objects.create(
            market=self.india,
            country_code='IN',
            currency='INR',
            account_type=LedgerAccount.ACCOUNT_PAYMENT_PROVIDER,
            name='Razorpay clearing',
            provider_code='RAZORPAY',
        )

    def create_balanced_transaction(self, key='ledger-test-1'):
        return LedgerTransaction.objects.create_balanced(
            market=self.india,
            country_code='IN',
            currency='INR',
            provider_code='RAZORPAY',
            transaction_type=LedgerTransaction.TYPE_ORDER_GROSS,
            idempotency_key=key,
            source_type='test',
            source_id=key,
            entries=[
                {
                    'account': self.provider,
                    'direction': LedgerEntry.DIRECTION_DEBIT,
                    'amount': Decimal('100.00'),
                    'memo': 'Provider receives customer payment.',
                },
                {
                    'account': self.platform,
                    'direction': LedgerEntry.DIRECTION_CREDIT,
                    'amount': Decimal('100.00'),
                    'memo': 'Platform recognizes order gross amount.',
                },
            ],
        )

    def test_balanced_transaction_stores_market_country_currency_amount_and_provider(self):
        transaction = self.create_balanced_transaction()

        self.assertEqual(transaction.market, self.india)
        self.assertEqual(transaction.country_code, 'IN')
        self.assertEqual(transaction.currency, 'INR')
        self.assertEqual(transaction.provider_code, 'RAZORPAY')
        self.assertEqual(transaction.amount, Decimal('100.00'))
        self.assertEqual(transaction.debit_total, Decimal('100.00'))
        self.assertEqual(transaction.credit_total, Decimal('100.00'))
        self.assertEqual(transaction.entries.count(), 2)

    def test_ledger_transaction_cannot_be_modified_after_creation(self):
        transaction = self.create_balanced_transaction()
        transaction.amount = Decimal('99.00')

        with self.assertRaises(ImmutableLedgerError):
            transaction.save()

    def test_ledger_entry_cannot_be_modified_after_creation(self):
        transaction = self.create_balanced_transaction()
        entry = transaction.entries.first()
        entry.amount = Decimal('99.00')

        with self.assertRaises(ImmutableLedgerError):
            entry.save()

    def test_ledger_records_cannot_be_deleted(self):
        transaction = self.create_balanced_transaction()
        entry = transaction.entries.first()

        with self.assertRaises(ImmutableLedgerError):
            entry.delete()
        with self.assertRaises(ImmutableLedgerError):
            transaction.delete()

    def test_duplicate_idempotency_keys_are_rejected(self):
        self.create_balanced_transaction(key='duplicate-key')

        with self.assertRaises(ValidationError):
            self.create_balanced_transaction(key='duplicate-key')

    def test_unbalanced_transaction_is_rejected(self):
        with self.assertRaises(ValidationError):
            LedgerTransaction.objects.create_balanced(
                market=self.india,
                country_code='IN',
                currency='INR',
                provider_code='RAZORPAY',
                transaction_type=LedgerTransaction.TYPE_ORDER_GROSS,
                idempotency_key='unbalanced-key',
                entries=[
                    {
                        'account': self.provider,
                        'direction': LedgerEntry.DIRECTION_DEBIT,
                        'amount': Decimal('100.00'),
                    },
                    {
                        'account': self.platform,
                        'direction': LedgerEntry.DIRECTION_CREDIT,
                        'amount': Decimal('99.00'),
                    },
                ],
            )

    def test_direct_transaction_and_entry_creation_are_rejected(self):
        with self.assertRaises(ImmutableLedgerError):
            LedgerTransaction.objects.create(
                market=self.india,
                country_code='IN',
                currency='INR',
                provider_code='RAZORPAY',
                transaction_type=LedgerTransaction.TYPE_ORDER_GROSS,
                amount=Decimal('100.00'),
                debit_total=Decimal('100.00'),
                credit_total=Decimal('100.00'),
                idempotency_key='direct-create-key',
            )

        transaction = self.create_balanced_transaction()
        with self.assertRaises(ImmutableLedgerError):
            LedgerEntry.objects.create(
                transaction=transaction,
                account=self.platform,
                direction=LedgerEntry.DIRECTION_CREDIT,
                amount=Decimal('1.00'),
                currency='INR',
            )

    def test_different_currencies_cannot_exist_inside_same_transaction(self):
        usd = Currency.objects.create(
            code='USD',
            numeric_code='840',
            name='US Dollar',
            symbol='$',
        )
        united_states = Market.objects.create(
            slug='united-states',
            name='United States',
            country_code='US',
            default_currency=usd,
            timezone='America/New_York',
            phone_country_code='+1',
        )
        stripe_account = LedgerAccount.objects.create(
            market=united_states,
            country_code='US',
            currency='USD',
            account_type=LedgerAccount.ACCOUNT_PAYMENT_PROVIDER,
            name='Stripe clearing',
            provider_code='STRIPE',
        )

        with self.assertRaises(ValidationError):
            LedgerTransaction.objects.create_balanced(
                market=self.india,
                country_code='IN',
                currency='INR',
                provider_code='RAZORPAY',
                transaction_type=LedgerTransaction.TYPE_ORDER_GROSS,
                idempotency_key='mixed-currency-key',
                entries=[
                    {
                        'account': self.provider,
                        'direction': LedgerEntry.DIRECTION_DEBIT,
                        'amount': Decimal('100.00'),
                        'currency': 'INR',
                    },
                    {
                        'account': stripe_account,
                        'direction': LedgerEntry.DIRECTION_CREDIT,
                        'amount': Decimal('100.00'),
                        'currency': 'USD',
                    },
                ],
            )

    def test_guinea_mobile_money_transaction_uses_gnf_and_provider_code(self):
        gnf = Currency.objects.create(
            code='GNF',
            numeric_code='324',
            name='Guinean Franc',
            symbol='FG',
            minor_unit=0,
        )
        guinea = Market.objects.create(
            slug='guinea',
            name='Guinea',
            country_code='GN',
            default_currency=gnf,
            timezone='Africa/Conakry',
            phone_country_code='+224',
        )
        wave = LedgerAccount.objects.create(
            market=guinea,
            country_code='GN',
            currency='GNF',
            account_type=LedgerAccount.ACCOUNT_PAYMENT_PROVIDER,
            name='Wave Guinea clearing',
            provider_code='WAVE',
        )
        platform = LedgerAccount.objects.create(
            market=guinea,
            country_code='GN',
            currency='GNF',
            account_type=LedgerAccount.ACCOUNT_PLATFORM,
            name='T-Food Guinea platform',
            provider_code='WAVE',
        )

        transaction = LedgerTransaction.objects.create_balanced(
            market=guinea,
            country_code='GN',
            currency='GNF',
            provider_code='WAVE',
            transaction_type=LedgerTransaction.TYPE_ORDER_GROSS,
            idempotency_key='guinea-wave-order-1',
            entries=[
                {
                    'account': wave,
                    'direction': LedgerEntry.DIRECTION_DEBIT,
                    'amount': Decimal('50000.00'),
                },
                {
                    'account': platform,
                    'direction': LedgerEntry.DIRECTION_CREDIT,
                    'amount': Decimal('50000.00'),
                },
            ],
        )

        self.assertEqual(transaction.market, guinea)
        self.assertEqual(transaction.country_code, 'GN')
        self.assertEqual(transaction.currency, 'GNF')
        self.assertEqual(transaction.provider_code, 'WAVE')

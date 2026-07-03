from io import StringIO

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from delivery.models import DeliveryPartner, MerchantRider
from markets.models import CommerceArea, CommerceCity, Currency, Market
from merchant_staff.models import MerchantStaffBranchAccess, MerchantStaffMember
from operations_access.models import OperationsStaffProfile
from payments.models import PaymentProviderConfig
from restaurants.models import FoodItem, MerchantProfile, Restaurant


DEMO_PASSWORD = 'DemoPass123!'
DEMO_EMAILS = [
    'ops.guinea.demo@t-food.test',
    'customer.guinea.demo@t-food.test',
    'merchant.guinea.demo@t-food.test',
    'staff.guinea.demo@t-food.test',
    'rider.guinea.demo@t-food.test',
]


class SeedGuineaDemoCommandTests(TestCase):
    def run_seed(self, *args):
        output = StringIO()
        call_command('seed_guinea_demo', *args, stdout=output)
        return output.getvalue()

    def test_command_creates_demo_foundation(self):
        output = self.run_seed()

        self.assertIn('Guinea demo data ready', output)
        currency = Currency.objects.get(code='GNF')
        market = Market.objects.get(slug='guinea')
        city = CommerceCity.objects.get(market=market, slug='conakry')

        self.assertEqual(currency.minor_unit, 0)
        self.assertEqual(market.country_code, 'GN')
        self.assertEqual(market.default_currency, currency)
        self.assertEqual(market.timezone, 'Africa/Conakry')
        self.assertEqual(city.name, 'Conakry')
        self.assertEqual(
            set(CommerceArea.objects.filter(city=city).values_list('name', flat=True)),
            {'Kaloum', 'Ratoma', 'Matoto', 'Dixinn', 'Matam'},
        )

        users = User.objects.filter(email__in=DEMO_EMAILS)
        self.assertEqual(users.count(), 5)
        for email in DEMO_EMAILS:
            self.assertIsNotNone(authenticate(username=email, password=DEMO_PASSWORD))

        self.assertEqual(Restaurant.objects.filter(market=market).count(), 3)
        self.assertEqual(FoodItem.objects.filter(restaurant__market=market).count(), 11)
        self.assertTrue(
            Restaurant.objects.filter(
                rest_name='Conakry Grill',
                branch_type=Restaurant.BRANCH_TYPE_FOOD,
            ).exists()
        )
        self.assertTrue(
            Restaurant.objects.filter(
                rest_name='Fresh Market Conakry',
                branch_type=Restaurant.BRANCH_TYPE_GROCERY,
            ).exists()
        )
        self.assertTrue(
            Restaurant.objects.filter(
                rest_name='Sante Plus Pharmacy',
                branch_type=Restaurant.BRANCH_TYPE_PHARMACY,
            ).exists()
        )

    def test_command_creates_verified_roles_and_provider_configs(self):
        self.run_seed()

        ops_user = User.objects.get(email='ops.guinea.demo@t-food.test')
        ops_profile = OperationsStaffProfile.objects.get(user=ops_user)
        self.assertEqual(ops_profile.role, OperationsStaffProfile.ROLE_GLOBAL_ADMIN)
        self.assertEqual(ops_profile.status, OperationsStaffProfile.STATUS_ACTIVE)

        merchant_user = User.objects.get(email='merchant.guinea.demo@t-food.test')
        merchant = MerchantProfile.objects.get(user=merchant_user)
        self.assertTrue(merchant.is_verified)

        staff_user = User.objects.get(email='staff.guinea.demo@t-food.test')
        staff = MerchantStaffMember.objects.get(user=staff_user, merchant=merchant)
        self.assertEqual(staff.membership_status, MerchantStaffMember.STATUS_ACTIVE)
        self.assertEqual(staff.verification_status, MerchantStaffMember.VERIFICATION_VERIFIED)
        self.assertEqual(staff.role, MerchantStaffMember.ROLE_BRANCH_MANAGER)
        self.assertEqual(MerchantStaffBranchAccess.objects.filter(staff_member=staff).count(), 1)

        rider_user = User.objects.get(email='rider.guinea.demo@t-food.test')
        rider = DeliveryPartner.objects.get(user=rider_user)
        self.assertTrue(rider.is_verified)
        self.assertTrue(rider.is_available)
        self.assertEqual(rider.market.slug, 'guinea')
        self.assertEqual(rider.merchant_rider_link.status, MerchantRider.STATUS_ACTIVE)

        market = Market.objects.get(slug='guinea')
        cod = PaymentProviderConfig.objects.get(
            market=market,
            provider_code='cod',
            payment_method=PaymentProviderConfig.METHOD_COD,
        )
        self.assertTrue(cod.is_active)
        self.assertTrue(cod.is_preferred)
        self.assertFalse(cod.credentials_present)

        mobile_money_configs = PaymentProviderConfig.objects.filter(
            market=market,
            payment_method=PaymentProviderConfig.METHOD_MOBILE_MONEY,
        )
        self.assertEqual(mobile_money_configs.count(), 3)
        self.assertFalse(mobile_money_configs.filter(is_active=True).exists())
        self.assertTrue(all(config.config_metadata.get('demo') for config in mobile_money_configs))

    def test_command_is_idempotent(self):
        self.run_seed()
        first_counts = {
            'users': User.objects.filter(email__in=DEMO_EMAILS).count(),
            'branches': Restaurant.objects.filter(market__slug='guinea').count(),
            'items': FoodItem.objects.filter(restaurant__market__slug='guinea').count(),
            'providers': PaymentProviderConfig.objects.filter(market__slug='guinea').count(),
        }

        self.run_seed()

        self.assertEqual(
            {
                'users': User.objects.filter(email__in=DEMO_EMAILS).count(),
                'branches': Restaurant.objects.filter(market__slug='guinea').count(),
                'items': FoodItem.objects.filter(restaurant__market__slug='guinea').count(),
                'providers': PaymentProviderConfig.objects.filter(market__slug='guinea').count(),
            },
            first_counts,
        )

    def test_reset_demo_removes_only_demo_records(self):
        real_user = User.objects.create_user(
            username='real-guinea-user',
            email='real@example.com',
        )

        self.run_seed()
        output = self.run_seed('--reset-demo')

        self.assertIn('Removed existing Guinea demo records', output)
        self.assertTrue(User.objects.filter(id=real_user.id).exists())
        self.assertEqual(User.objects.filter(email__in=DEMO_EMAILS).count(), 0)
        self.assertFalse(Restaurant.objects.filter(rest_email__endswith='.demo@t-food.test').exists())

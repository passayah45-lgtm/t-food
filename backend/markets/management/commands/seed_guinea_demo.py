from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from customers.models import Customer, DeliveryAddress
from delivery.models import DeliveryPartner, MerchantRider
from fooddelivery.gis_utils import make_point
from markets.models import CommerceArea, CommerceCity, Currency, Market
from merchant_staff.models import MerchantStaffBranchAccess, MerchantStaffMember
from operations_access.models import OperationsStaffProfile
from payments.models import PaymentProviderConfig
from restaurants.models import FoodItem, MerchantProfile, Restaurant
from verifications.constants import VERIFICATION_APPROVED


DEMO_PASSWORD = 'DemoPass123!'
DEMO_EMAILS = {
    'ops': 'ops.guinea.demo@t-food.test',
    'customer': 'customer.guinea.demo@t-food.test',
    'merchant': 'merchant.guinea.demo@t-food.test',
    'staff': 'staff.guinea.demo@t-food.test',
    'rider': 'rider.guinea.demo@t-food.test',
}
DEMO_BRANCH_EMAILS = [
    'conakry.grill.demo@t-food.test',
    'fresh.market.conakry.demo@t-food.test',
    'sante.plus.pharmacy.demo@t-food.test',
]
DEMO_PROVIDER_CODES = ['cod', 'wave', 'orange_money', 'mtn_mobile_money']


class Command(BaseCommand):
    help = 'Create or reset safe Guinea demo data for local pilot testing.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset-demo',
            action='store_true',
            help='Remove only clearly marked Guinea demo records before seeding.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['reset_demo']:
            self._reset_demo()
            self.stdout.write(self.style.WARNING('Removed existing Guinea demo records.'))
            return

        currency = self._seed_currency()
        market = self._seed_market(currency)
        city = self._seed_city(market)
        areas = self._seed_areas(market, city)
        users = self._seed_users()
        merchant = self._seed_profiles(users, market)
        branches = self._seed_branches(users['merchant'], market, city, areas)
        item_count = self._seed_catalog(branches)
        self._seed_staff(users, merchant, branches['food'])
        self._seed_rider(users, merchant, market, branches['food'])
        self._seed_payment_configs(users['ops'], market)
        self._seed_customer(users['customer'], market, areas['Kaloum'])

        self.stdout.write(self.style.SUCCESS('Guinea demo data ready.'))
        self.stdout.write(f'Password for every demo account: {DEMO_PASSWORD}')
        for label, email in DEMO_EMAILS.items():
            self.stdout.write(f'{label}: {email}')
        self.stdout.write(
            self.style.SUCCESS(
                f'Created/updated {len(branches)} demo branches and {item_count} catalog items.'
            )
        )
        self.stdout.write(
            self.style.WARNING(
                'Demo credentials are for local/Codespaces testing only. Never use them in production.'
            )
        )

    def _reset_demo(self):
        market = Market.objects.filter(slug='guinea').first()
        if market:
            PaymentProviderConfig.objects.filter(
                market=market,
                provider_code__in=DEMO_PROVIDER_CODES,
            ).delete()

        Restaurant.objects.filter(rest_email__in=DEMO_BRANCH_EMAILS).delete()
        User.objects.filter(email__in=DEMO_EMAILS.values()).delete()

        if not market:
            return

        for area in CommerceArea.objects.filter(market=market, city__slug='conakry'):
            if not area.branches.exists() and not area.notifications.exists():
                area.delete()

        city = CommerceCity.objects.filter(market=market, slug='conakry').first()
        if city and not city.areas.exists() and not city.branches.exists():
            city.delete()

        market.refresh_from_db()
        if (
            not market.commerce_cities.exists()
            and not market.commerce_areas.exists()
            and not market.restaurants.exists()
            and not market.customers.exists()
            and not market.payment_provider_configs.exists()
            and not market.delivery_partners.exists()
        ):
            currency = market.default_currency
            market.delete()
            if not currency.markets.exists():
                currency.delete()

    def _seed_currency(self):
        currency, _ = Currency.objects.update_or_create(
            code='GNF',
            defaults={
                'numeric_code': '324',
                'name': 'Guinean Franc',
                'symbol': 'GNF',
                'minor_unit': 0,
                'is_active': True,
            },
        )
        return currency

    def _seed_market(self, currency):
        market, _ = Market.objects.update_or_create(
            slug='guinea',
            defaults={
                'name': 'Guinea',
                'country_code': 'GN',
                'default_currency': currency,
                'timezone': 'Africa/Conakry',
                'phone_country_code': '+224',
                'is_active': True,
            },
        )
        return market

    def _seed_city(self, market):
        city, _ = CommerceCity.objects.update_or_create(
            market=market,
            slug='conakry',
            defaults={
                'name': 'Conakry',
                'center_point': make_point('-13.6773', '9.6412'),
                'is_active': True,
            },
        )
        return city

    def _seed_areas(self, market, city):
        area_points = {
            'Kaloum': ('-13.7028', '9.5092'),
            'Ratoma': ('-13.6404', '9.6506'),
            'Matoto': ('-13.5737', '9.5695'),
            'Dixinn': ('-13.6679', '9.5681'),
            'Matam': ('-13.6346', '9.5517'),
        }
        areas = {}
        for name, coordinates in area_points.items():
            area, _ = CommerceArea.objects.update_or_create(
                city=city,
                slug=slugify(name),
                defaults={
                    'market': market,
                    'name': name,
                    'center_point': make_point(*coordinates),
                    'service_radius_km': Decimal('8.00'),
                    'is_active': True,
                },
            )
            areas[name] = area
        return areas

    def _seed_users(self):
        users = {}
        names = {
            'ops': ('T-Food', 'Guinea Ops'),
            'customer': ('Aminata', 'T-Food Demo'),
            'merchant': ('Mamadou', 'T-Food Merchant'),
            'staff': ('Mariama', 'T-Food Staff'),
            'rider': ('Ibrahima', 'T-Food Rider'),
        }
        for key, email in DEMO_EMAILS.items():
            user, _ = User.objects.update_or_create(
                username=email,
                defaults={
                    'email': email,
                    'first_name': names[key][0],
                    'last_name': names[key][1],
                    'is_active': True,
                    'is_staff': key == 'ops',
                    'is_superuser': False,
                },
            )
            user.set_password(DEMO_PASSWORD)
            user.save(update_fields=['password'])
            users[key] = user
        return users

    def _seed_profiles(self, users, market):
        Customer.objects.update_or_create(
            user=users['customer'],
            defaults={
                'market': market,
                'phone': '+224620000101',
                'address': 'Kaloum, Conakry',
                'loyalty_points': 250,
            },
        )
        merchant, _ = MerchantProfile.objects.update_or_create(
            user=users['merchant'],
            defaults={
                'market': market,
                'business_name': 'T-Food Guinea Demo Merchant',
                'phone': '+224620000202',
                'is_verified': True,
                'verification_status': VERIFICATION_APPROVED,
                'verification_reviewed_at': timezone.now(),
                'verification_reviewed_by': users['ops'],
            },
        )
        OperationsStaffProfile.objects.update_or_create(
            user=users['ops'],
            defaults={
                'role': OperationsStaffProfile.ROLE_GLOBAL_ADMIN,
                'status': OperationsStaffProfile.STATUS_ACTIVE,
                'permissions': [],
                'created_by': users['ops'],
                'updated_by': users['ops'],
            },
        )
        return merchant

    def _seed_branches(self, owner, market, city, areas):
        branch_specs = {
            'food': {
                'rest_name': 'Conakry Grill',
                'rest_email': DEMO_BRANCH_EMAILS[0],
                'rest_contact': '+224620000301',
                'rest_address': 'Avenue de la Republique, Kaloum, Conakry',
                'branch_name': 'Conakry Grill Kaloum',
                'branch_code': 'GN-CKY-KALOUM-GRILL-DEMO',
                'branch_type': Restaurant.BRANCH_TYPE_FOOD,
                'area': areas['Kaloum'],
                'latitude': Decimal('9.509200'),
                'longitude': Decimal('-13.702800'),
                'delivery_fee': Decimal('15000'),
                'min_order_amount': Decimal('25000'),
            },
            'grocery': {
                'rest_name': 'Fresh Market Conakry',
                'rest_email': DEMO_BRANCH_EMAILS[1],
                'rest_contact': '+224620000302',
                'rest_address': 'Route Le Prince, Ratoma, Conakry',
                'branch_name': 'Fresh Market Ratoma',
                'branch_code': 'GN-CKY-RATOMA-MARKET-DEMO',
                'branch_type': Restaurant.BRANCH_TYPE_GROCERY,
                'area': areas['Ratoma'],
                'latitude': Decimal('9.650600'),
                'longitude': Decimal('-13.640400'),
                'delivery_fee': Decimal('18000'),
                'min_order_amount': Decimal('30000'),
            },
            'pharmacy': {
                'rest_name': 'Sante Plus Pharmacy',
                'rest_email': DEMO_BRANCH_EMAILS[2],
                'rest_contact': '+224620000303',
                'rest_address': 'Matoto Market Road, Matoto, Conakry',
                'branch_name': 'Sante Plus Matoto',
                'branch_code': 'GN-CKY-MATOTO-PHARMACY-DEMO',
                'branch_type': Restaurant.BRANCH_TYPE_PHARMACY,
                'area': areas['Matoto'],
                'latitude': Decimal('9.569500'),
                'longitude': Decimal('-13.573700'),
                'delivery_fee': Decimal('12000'),
                'min_order_amount': Decimal('15000'),
            },
        }
        branches = {}
        for key, spec in branch_specs.items():
            branch, _ = Restaurant.objects.update_or_create(
                rest_email=spec['rest_email'],
                defaults={
                    'market': market,
                    'owner': owner,
                    'rest_name': spec['rest_name'],
                    'rest_contact': spec['rest_contact'],
                    'rest_address': spec['rest_address'],
                    'rest_city': 'Conakry',
                    'branch_name': spec['branch_name'],
                    'branch_code': spec['branch_code'],
                    'branch_type': spec['branch_type'],
                    'country_code': 'GN',
                    'city_ref': city,
                    'area_ref': spec['area'],
                    'pickup_latitude': spec['latitude'],
                    'pickup_longitude': spec['longitude'],
                    'delivery_fee': spec['delivery_fee'],
                    'delivery_radius_km': Decimal('15.00'),
                    'estimated_prep_minutes': 25,
                    'min_order_amount': spec['min_order_amount'],
                    'commission_percent': 10,
                    'is_active': True,
                    'is_open': True,
                },
            )
            branches[key] = branch
        return branches

    def _seed_catalog(self, branches):
        catalog = {
            'food': [
                ('Poulet yassa', 'Demo Senegalese-style chicken with onion sauce.', '65000', 'Non-Vegetarian'),
                ('Riz sauce arachide', 'Demo rice with peanut sauce.', '45000', 'Vegetarian'),
                ('Brochettes', 'Demo grilled beef skewers.', '55000', 'Non-Vegetarian'),
                ('Jus bissap', 'Demo hibiscus drink.', '18000', 'Beverages'),
            ],
            'grocery': [
                ('Rice bag', 'Demo 25 kg rice bag.', '285000', 'Vegetarian'),
                ('Cooking oil', 'Demo 5 L cooking oil.', '95000', 'Vegetarian'),
                ('Sugar', 'Demo 5 kg sugar pack.', '65000', 'Vegetarian'),
                ('Bottled water', 'Demo pack of bottled water.', '45000', 'Beverages'),
            ],
            'pharmacy': [
                ('Paracetamol', 'Demo pharmacy item for testing search only.', '15000', 'Vegetarian'),
                ('Vitamin C', 'Demo supplement pack.', '35000', 'Vegetarian'),
                ('Oral rehydration salts', 'Demo ORS sachets.', '12000', 'Vegetarian'),
            ],
        }
        count = 0
        for branch_key, items in catalog.items():
            for name, description, price, category in items:
                FoodItem.objects.update_or_create(
                    restaurant=branches[branch_key],
                    food_name=name,
                    defaults={
                        'food_desc': description,
                        'food_price': Decimal(price),
                        'food_categ': category,
                        'is_available': True,
                    },
                )
                count += 1
        return count

    def _seed_staff(self, users, merchant, branch):
        staff, _ = MerchantStaffMember.objects.update_or_create(
            merchant=merchant,
            user=users['staff'],
            defaults={
                'role': MerchantStaffMember.ROLE_BRANCH_MANAGER,
                'membership_status': MerchantStaffMember.STATUS_ACTIVE,
                'verification_status': MerchantStaffMember.VERIFICATION_VERIFIED,
                'verification_reviewed_at': timezone.now(),
                'verification_reviewed_by': users['ops'],
                'is_company_wide': False,
                'created_by': users['merchant'],
                'updated_by': users['ops'],
            },
        )
        MerchantStaffBranchAccess.objects.get_or_create(
            staff_member=staff,
            branch=branch,
            defaults={'created_by': users['merchant']},
        )

    def _seed_rider(self, users, merchant, market, branch):
        partner, _ = DeliveryPartner.objects.update_or_create(
            user=users['rider'],
            defaults={
                'market': market,
                'partner_name': 'Ibrahima T-Food Demo Rider',
                'partner_phone': '+224620000404',
                'transport_details': 'Motorbike',
                'is_available': True,
                'is_verified': True,
                'verification_status': VERIFICATION_APPROVED,
                'verification_reviewed_at': timezone.now(),
                'verification_reviewed_by': users['ops'],
                'current_latitude': Decimal('9.520000'),
                'current_longitude': Decimal('-13.690000'),
                'location_updated_at': timezone.now(),
            },
        )
        MerchantRider.objects.update_or_create(
            partner=partner,
            defaults={
                'merchant': merchant,
                'status': MerchantRider.STATUS_ACTIVE,
                'invited_by': users['merchant'],
                'approved_by': users['ops'],
                'home_restaurant': branch,
                'approved_at': timezone.now(),
            },
        )

    def _seed_payment_configs(self, ops_user, market):
        configs = [
            {
                'provider_code': 'cod',
                'payment_method': PaymentProviderConfig.METHOD_COD,
                'is_active': True,
                'is_preferred': True,
                'priority': 1,
                'supports_refund': False,
            },
            {
                'provider_code': 'wave',
                'payment_method': PaymentProviderConfig.METHOD_MOBILE_MONEY,
                'is_active': False,
                'is_preferred': False,
                'priority': 20,
                'supports_refund': True,
            },
            {
                'provider_code': 'orange_money',
                'payment_method': PaymentProviderConfig.METHOD_MOBILE_MONEY,
                'is_active': False,
                'is_preferred': False,
                'priority': 30,
                'supports_refund': True,
            },
            {
                'provider_code': 'mtn_mobile_money',
                'payment_method': PaymentProviderConfig.METHOD_MOBILE_MONEY,
                'is_active': False,
                'is_preferred': False,
                'priority': 40,
                'supports_refund': True,
            },
        ]
        for config in configs:
            PaymentProviderConfig.objects.update_or_create(
                market=market,
                provider_code=config['provider_code'],
                payment_method=config['payment_method'],
                defaults={
                    'country_code': 'GN',
                    'currency': 'GNF',
                    'is_active': config['is_active'],
                    'is_preferred': config['is_preferred'],
                    'priority': config['priority'],
                    'supports_refund': config['supports_refund'],
                    'supports_webhook': False,
                    'supports_partial_refund': False,
                    'credentials_present': False,
                    'config_metadata': {
                        'demo': True,
                        'note': 'Guinea demo configuration. External providers are inactive.',
                    },
                    'updated_by': ops_user,
                },
            )

    def _seed_customer(self, customer_user, market, area):
        DeliveryAddress.objects.update_or_create(
            user=customer_user,
            label='HOME',
            defaults={
                'market': market,
                'recipient_name': customer_user.get_full_name() or 'T-Food Demo Customer',
                'phone': '+224620000101',
                'address': 'Kaloum demo address, Conakry',
                'instructions': 'Demo address for local pilot testing.',
                'latitude': Decimal('9.509200'),
                'longitude': Decimal('-13.702800'),
                'is_default': True,
            },
        )

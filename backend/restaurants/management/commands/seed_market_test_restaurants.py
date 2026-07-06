from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from fooddelivery.gis_utils import make_point
from markets.models import CommerceArea, CommerceCity, Currency, Market
from restaurants.models import FoodItem, MerchantProfile, Restaurant
from verifications.constants import VERIFICATION_APPROVED


TEST_PASSWORD = 'TestPass123!'


MARKET_SPECS = {
    'GN': {
        'currency': {
            'code': 'GNF',
            'numeric_code': '324',
            'name': 'Guinean Franc',
            'symbol': 'GNF',
            'minor_unit': 0,
        },
        'market': {
            'name': 'Guinea',
            'slug': 'guinea',
            'timezone': 'Africa/Conakry',
            'phone_country_code': '+224',
        },
        'city': {
            'name': 'Conakry',
            'slug': 'conakry',
            'point': ('-13.6773', '9.6412'),
        },
        'area': {
            'name': 'Kaloum',
            'slug': 'kaloum',
            'point': ('-13.7028', '9.5092'),
        },
        'owner': {
            'username': 'merchant.guinea.test@t-food.test',
            'email': 'merchant.guinea.test@t-food.test',
            'first_name': 'T-Food',
            'last_name': 'Guinea Test',
            'business_name': 'T-Food Guinea Test Merchant',
            'phone': '+224620009001',
        },
        'restaurant': {
            'rest_name': 'T-Food Conakry Test Kitchen',
            'rest_email': 'conakry.test.kitchen@t-food.test',
            'rest_contact': '+224620009101',
            'rest_address': 'Kaloum, Conakry',
            'rest_city': 'Conakry',
            'branch_name': 'Conakry Test Kitchen',
            'branch_code': 'GN-CKY-TEST-KITCHEN',
            'latitude': Decimal('9.509200'),
            'longitude': Decimal('-13.702800'),
            'delivery_fee': Decimal('15000'),
            'min_order_amount': Decimal('25000'),
            'delivery_radius_km': Decimal('20.00'),
        },
        'items': [
            ('Poulet yassa test', 'Guinea test chicken plate.', '65000', 'Non-Vegetarian'),
            ('Riz sauce arachide test', 'Guinea test rice plate.', '45000', 'Vegetarian'),
        ],
    },
    'IN': {
        'currency': {
            'code': 'INR',
            'numeric_code': '356',
            'name': 'Indian Rupee',
            'symbol': '₹',
            'minor_unit': 2,
        },
        'market': {
            'name': 'India',
            'slug': 'india',
            'timezone': 'Asia/Kolkata',
            'phone_country_code': '+91',
        },
        'city': {
            'name': 'New Delhi',
            'slug': 'new-delhi',
            'point': ('77.2167', '28.6315'),
        },
        'area': {
            'name': 'Connaught Place',
            'slug': 'connaught-place',
            'point': ('77.2195', '28.6328'),
        },
        'owner': {
            'username': 'merchant.india.test@t-food.test',
            'email': 'merchant.india.test@t-food.test',
            'first_name': 'T-Food',
            'last_name': 'India Test',
            'business_name': 'T-Food India Test Merchant',
            'phone': '+919900090001',
        },
        'restaurant': {
            'rest_name': 'T-Food Delhi Test Kitchen',
            'rest_email': 'delhi.test.kitchen@t-food.test',
            'rest_contact': '+919900091001',
            'rest_address': 'Connaught Place, New Delhi',
            'rest_city': 'New Delhi',
            'branch_name': 'Delhi Test Kitchen',
            'branch_code': 'IN-DEL-TEST-KITCHEN',
            'latitude': Decimal('28.632800'),
            'longitude': Decimal('77.219500'),
            'delivery_fee': Decimal('50.00'),
            'min_order_amount': Decimal('100.00'),
            'delivery_radius_km': Decimal('20.00'),
        },
        'items': [
            ('Bombay biryani test', 'India test biryani plate.', '500.00', 'Non-Vegetarian'),
            ('Masala chai test', 'India test tea.', '80.00', 'Beverages'),
        ],
    },
}


class Command(BaseCommand):
    help = 'Create/update one Guinea and one India restaurant for market-location testing.'

    @transaction.atomic
    def handle(self, *args, **options):
        branches = []
        for country_code, spec in MARKET_SPECS.items():
            currency = self._currency(spec['currency'])
            market = self._market(country_code, currency, spec['market'])
            city = self._city(market, spec['city'])
            area = self._area(city, spec['area'])
            owner = self._owner(spec['owner'])
            self._merchant_profile(owner, market, spec['owner'])
            branch = self._restaurant(owner, market, city, area, country_code, spec['restaurant'])
            self._items(branch, spec['items'])
            branches.append(branch)

        self.stdout.write(self.style.SUCCESS('Market test restaurants ready.'))
        self.stdout.write(f'Test merchant password: {TEST_PASSWORD}')
        for branch in branches:
            self.stdout.write(
                f'{branch.rest_name}: {branch.country_code}, '
                f'{branch.rest_city}, {branch.area_ref.name}, {branch.rest_email}'
            )

    def _currency(self, spec):
        currency, _ = Currency.objects.update_or_create(
            code=spec['code'],
            defaults={**spec, 'is_active': True},
        )
        return currency

    def _market(self, country_code, currency, spec):
        market = Market.objects.filter(country_code=country_code).first()
        defaults = {
            'name': spec['name'],
            'slug': spec['slug'],
            'default_currency': currency,
            'timezone': spec['timezone'],
            'phone_country_code': spec['phone_country_code'],
            'is_active': True,
        }
        if market:
            for field, value in defaults.items():
                setattr(market, field, value)
            market.save()
            return market
        market, _ = Market.objects.update_or_create(
            slug=spec['slug'],
            defaults={
                **defaults,
                'country_code': country_code,
            },
        )
        return market

    def _city(self, market, spec):
        city, _ = CommerceCity.objects.update_or_create(
            market=market,
            slug=spec['slug'],
            defaults={
                'name': spec['name'],
                'center_point': make_point(*spec['point']),
                'is_active': True,
            },
        )
        return city

    def _area(self, city, spec):
        area, _ = CommerceArea.objects.update_or_create(
            city=city,
            slug=spec['slug'],
            defaults={
                'market': city.market,
                'name': spec['name'],
                'center_point': make_point(*spec['point']),
                'service_radius_km': Decimal('8.00'),
                'is_active': True,
            },
        )
        return area

    def _owner(self, spec):
        user, _ = User.objects.update_or_create(
            username=spec['username'],
            defaults={
                'email': spec['email'],
                'first_name': spec['first_name'],
                'last_name': spec['last_name'],
                'is_active': True,
            },
        )
        user.set_password(TEST_PASSWORD)
        user.save(update_fields=['password'])
        return user

    def _merchant_profile(self, owner, market, spec):
        MerchantProfile.objects.update_or_create(
            user=owner,
            defaults={
                'market': market,
                'business_name': spec['business_name'],
                'phone': spec['phone'],
                'is_verified': True,
                'verification_status': VERIFICATION_APPROVED,
                'verification_reviewed_at': timezone.now(),
            },
        )

    def _restaurant(self, owner, market, city, area, country_code, spec):
        restaurant, _ = Restaurant.objects.update_or_create(
            rest_email=spec['rest_email'],
            defaults={
                'market': market,
                'owner': owner,
                'rest_name': spec['rest_name'],
                'rest_contact': spec['rest_contact'],
                'rest_address': spec['rest_address'],
                'rest_city': spec['rest_city'],
                'branch_name': spec['branch_name'],
                'branch_code': spec['branch_code'],
                'branch_type': Restaurant.BRANCH_TYPE_FOOD,
                'country_code': country_code,
                'city_ref': city,
                'area_ref': area,
                'pickup_latitude': spec['latitude'],
                'pickup_longitude': spec['longitude'],
                'delivery_fee': spec['delivery_fee'],
                'delivery_radius_km': spec['delivery_radius_km'],
                'estimated_prep_minutes': 25,
                'min_order_amount': spec['min_order_amount'],
                'commission_percent': 0,
                'is_active': True,
                'is_open': True,
            },
        )
        return restaurant

    def _items(self, restaurant, items):
        for name, description, price, category in items:
            FoodItem.objects.update_or_create(
                restaurant=restaurant,
                food_name=name,
                defaults={
                    'food_desc': description,
                    'food_price': Decimal(price),
                    'food_categ': category,
                    'is_available': True,
                },
            )

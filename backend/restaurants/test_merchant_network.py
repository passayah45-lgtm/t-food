from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from restaurants.models import MerchantNetworkRelationship, MerchantProfile, Restaurant
from restaurants.services import find_nearby_merchants


class MerchantNetworkRelationshipTests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_user(username='network-operator')
        self.owner_a = User.objects.create_user(username='network-merchant-a')
        self.owner_b = User.objects.create_user(username='network-merchant-b')
        self.owner_c = User.objects.create_user(username='network-merchant-c')
        self.merchant_a = MerchantProfile.objects.create(
            user=self.owner_a,
            business_name='Network Merchant A',
            is_verified=True,
        )
        self.merchant_b = MerchantProfile.objects.create(
            user=self.owner_b,
            business_name='Network Merchant B',
            is_verified=True,
        )
        self.merchant_c = MerchantProfile.objects.create(
            user=self.owner_c,
            business_name='Network Merchant C',
            is_verified=True,
        )

    def create_restaurant(self, owner, name, latitude, longitude):
        return Restaurant.objects.create(
            owner=owner,
            rest_name=name,
            rest_email=f'{name.lower().replace(" ", "-")}@example.com',
            rest_contact='9000000000',
            rest_address=f'{name} Road',
            rest_city='Bhubaneswar',
            pickup_latitude=Decimal(str(latitude)),
            pickup_longitude=Decimal(str(longitude)),
            is_active=True,
        )

    def test_create_relationship_request(self):
        relationship = MerchantNetworkRelationship.objects.create(
            from_merchant=self.merchant_a,
            to_merchant=self.merchant_b,
            requested_by=self.owner_a,
            notes='Can help during dinner rush.',
            distance_km=Decimal('1.25'),
        )

        self.assertEqual(relationship.status, MerchantNetworkRelationship.STATUS_REQUESTED)
        self.assertEqual(relationship.from_merchant, self.merchant_a)
        self.assertEqual(relationship.to_merchant, self.merchant_b)
        self.assertEqual(relationship.requested_by, self.owner_a)
        self.assertIsNone(relationship.approved_by)
        self.assertIsNone(relationship.approved_at)

    def test_prevent_self_relationship(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                MerchantNetworkRelationship.objects.create(
                    from_merchant=self.merchant_a,
                    to_merchant=self.merchant_a,
                    requested_by=self.owner_a,
                )

    def test_prevent_duplicate_directional_relationship(self):
        MerchantNetworkRelationship.objects.create(
            from_merchant=self.merchant_a,
            to_merchant=self.merchant_b,
            requested_by=self.owner_a,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                MerchantNetworkRelationship.objects.create(
                    from_merchant=self.merchant_a,
                    to_merchant=self.merchant_b,
                    requested_by=self.owner_a,
                )

    def test_reverse_relationship_is_explicitly_directional(self):
        MerchantNetworkRelationship.objects.create(
            from_merchant=self.merchant_a,
            to_merchant=self.merchant_b,
            requested_by=self.owner_a,
        )
        reverse = MerchantNetworkRelationship.objects.create(
            from_merchant=self.merchant_b,
            to_merchant=self.merchant_a,
            requested_by=self.owner_b,
        )

        self.assertEqual(reverse.from_merchant, self.merchant_b)
        self.assertEqual(reverse.to_merchant, self.merchant_a)

    def test_status_choices_validate(self):
        relationship = MerchantNetworkRelationship(
            from_merchant=self.merchant_a,
            to_merchant=self.merchant_b,
            status='NOT_A_STATUS',
        )

        with self.assertRaises(ValidationError):
            relationship.full_clean()

    def test_pause_and_block_statuses_work(self):
        relationship = MerchantNetworkRelationship.objects.create(
            from_merchant=self.merchant_a,
            to_merchant=self.merchant_b,
            requested_by=self.owner_a,
            approved_by=self.operator,
            approved_at=timezone.now(),
            status=MerchantNetworkRelationship.STATUS_ACTIVE,
        )

        relationship.status = MerchantNetworkRelationship.STATUS_PAUSED
        relationship.save(update_fields=['status'])
        relationship.refresh_from_db()
        self.assertEqual(relationship.status, MerchantNetworkRelationship.STATUS_PAUSED)

        relationship.status = MerchantNetworkRelationship.STATUS_BLOCKED
        relationship.save(update_fields=['status'])
        relationship.refresh_from_db()
        self.assertEqual(relationship.status, MerchantNetworkRelationship.STATUS_BLOCKED)

    def test_find_nearby_merchants_returns_merchants_ordered_by_distance(self):
        self.create_restaurant(self.owner_a, 'Anchor Kitchen', '20.353000', '85.819000')
        self.create_restaurant(self.owner_b, 'Close Kitchen', '20.354000', '85.820000')
        self.create_restaurant(self.owner_c, 'Far Kitchen', '20.390000', '85.860000')

        nearby = find_nearby_merchants(self.merchant_a, radius_km=10)

        self.assertEqual([merchant.id for merchant in nearby], [
            self.merchant_b.id,
            self.merchant_c.id,
        ])
        self.assertLess(nearby[0].distance_km, nearby[1].distance_km)

    def test_find_nearby_merchants_respects_radius(self):
        self.create_restaurant(self.owner_a, 'Radius Anchor Kitchen', '20.353000', '85.819000')
        self.create_restaurant(self.owner_b, 'Radius Close Kitchen', '20.354000', '85.820000')
        self.create_restaurant(self.owner_c, 'Radius Far Kitchen', '20.390000', '85.860000')

        nearby = find_nearby_merchants(self.merchant_a, radius_km=1)

        self.assertEqual([merchant.id for merchant in nearby], [self.merchant_b.id])

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from delivery.models import DeliveryPartner, MerchantRider, MerchantRiderInvite
from restaurants.models import MerchantProfile, Restaurant


class MerchantRiderModelTests(TestCase):
    def setUp(self):
        self.merchant_user = User.objects.create_user(
            username='merchant-rider-owner',
            email='merchant-rider-owner@example.com',
        )
        self.merchant = MerchantProfile.objects.create(
            user=self.merchant_user,
            business_name='Merchant Rider Foods',
            phone='9000000001',
            is_verified=True,
        )
        self.restaurant = Restaurant.objects.create(
            owner=self.merchant_user,
            rest_name='Merchant Rider Kitchen',
            rest_email='merchant-rider-kitchen@example.com',
            rest_contact='9000000002',
            rest_address='KIIT Road',
            rest_city='Bhubaneswar',
        )
        self.partner_user = User.objects.create_user(
            username='merchant-owned-rider',
            email='merchant-owned-rider@example.com',
        )
        self.partner = DeliveryPartner.objects.create(
            user=self.partner_user,
            partner_name='Merchant Owned Rider',
            partner_phone='9000000003',
            transport_details='Bike',
            is_verified=True,
            is_available=True,
        )

    def test_create_merchant_rider_link(self):
        link = MerchantRider.objects.create(
            merchant=self.merchant,
            partner=self.partner,
            status=MerchantRider.STATUS_ACTIVE,
            invited_by=self.merchant_user,
            approved_by=self.merchant_user,
            approved_at=timezone.now(),
            home_restaurant=self.restaurant,
        )

        self.assertEqual(link.merchant, self.merchant)
        self.assertEqual(link.partner, self.partner)
        self.assertEqual(link.status, MerchantRider.STATUS_ACTIVE)
        self.assertEqual(link.home_restaurant, self.restaurant)

    def test_partner_can_only_have_one_merchant_rider_link(self):
        MerchantRider.objects.create(
            merchant=self.merchant,
            partner=self.partner,
        )
        other_user = User.objects.create_user(username='other-rider-merchant')
        other_merchant = MerchantProfile.objects.create(
            user=other_user,
            business_name='Other Rider Merchant',
        )

        with self.assertRaises(IntegrityError):
            MerchantRider.objects.create(
                merchant=other_merchant,
                partner=self.partner,
            )

    def test_merchant_rider_status_choices_validate(self):
        link = MerchantRider(
            merchant=self.merchant,
            partner=self.partner,
            status='NOT_A_STATUS',
        )

        with self.assertRaises(ValidationError):
            link.full_clean()

    def test_merchant_rider_optional_fields_can_be_null(self):
        link = MerchantRider.objects.create(
            merchant=self.merchant,
            partner=self.partner,
        )

        self.assertIsNone(link.invited_by)
        self.assertIsNone(link.approved_by)
        self.assertIsNone(link.home_restaurant)
        self.assertIsNone(link.approved_at)
        self.assertEqual(link.status, MerchantRider.STATUS_PENDING_APPROVAL)

    def test_invite_token_is_unique(self):
        MerchantRiderInvite.objects.create(
            merchant=self.merchant,
            name='First Invited Rider',
            invite_token='fixed-token',
        )

        with self.assertRaises(IntegrityError):
            MerchantRiderInvite.objects.create(
                merchant=self.merchant,
                name='Second Invited Rider',
                invite_token='fixed-token',
            )

    def test_invite_expiry_logic(self):
        expired = MerchantRiderInvite.objects.create(
            merchant=self.merchant,
            name='Expired Rider',
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        active = MerchantRiderInvite.objects.create(
            merchant=self.merchant,
            name='Active Rider',
            expires_at=timezone.now() + timedelta(days=1),
        )
        accepted = MerchantRiderInvite.objects.create(
            merchant=self.merchant,
            name='Accepted Rider',
            status=MerchantRiderInvite.STATUS_ACCEPTED,
            expires_at=timezone.now() - timedelta(minutes=1),
            linked_partner=self.partner,
        )

        self.assertTrue(expired.is_expired())
        self.assertFalse(active.is_expired())
        self.assertFalse(accepted.is_expired())

    def test_invite_optional_fields_can_be_blank_or_null(self):
        invite = MerchantRiderInvite.objects.create(
            merchant=self.merchant,
            name='Minimal Rider Invite',
        )

        self.assertEqual(invite.phone, '')
        self.assertEqual(invite.email, '')
        self.assertEqual(invite.transport_type, '')
        self.assertIsNone(invite.linked_partner)
        self.assertIsNone(invite.invited_by)
        self.assertEqual(invite.status, MerchantRiderInvite.STATUS_PENDING)
        self.assertTrue(invite.invite_token)
        self.assertGreater(invite.expires_at, timezone.now())

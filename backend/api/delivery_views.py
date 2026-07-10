from django.db import transaction
from django.db.models import F, Q, Sum
from django.utils import timezone
from secrets import compare_digest
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from delivery.models import Delivery, MerchantRiderInvite
from delivery.services import (
    claim_pending_delivery,
    notify_partner_of_pending_deliveries,
    offer_radius_km,
    partner_distance_km,
    partner_is_eligible,
    pickup_restaurant_for_order,
    sort_deliveries_for_partner,
)
from delivery.notifications import notify_admin_delivered, notify_customer_status
from customers.models import Customer
from notifications.events import (
    notify_order_event,
    notify_payment_event,
    notify_payout_event,
)
from payments.services import (
    record_merchant_payout_audit,
    record_partner_payout_audit,
)
from realtime.services import broadcast_delivery_status_changed


class PartnerDeliverySerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(source='order.id', read_only=True)
    customer_name = serializers.SerializerMethodField()
    total_amount = serializers.DecimalField(
        source='order.total_amount',
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    items = serializers.SerializerMethodField()
    restaurant_name = serializers.SerializerMethodField()
    pickup_branch_name = serializers.SerializerMethodField()
    pickup_address = serializers.SerializerMethodField()
    pickup_phone = serializers.SerializerMethodField()
    pickup_city = serializers.SerializerMethodField()
    pickup_area = serializers.SerializerMethodField()
    pickup_latitude = serializers.SerializerMethodField()
    pickup_longitude = serializers.SerializerMethodField()
    pickup_distance_km = serializers.SerializerMethodField()
    offer_radius_km = serializers.SerializerMethodField()
    delivery_address = serializers.CharField(source='order.delivery_address', read_only=True)
    delivery_instructions = serializers.CharField(
        source='order.delivery_instructions', read_only=True
    )
    payment_method = serializers.CharField(
        source='order.payment.method',
        read_only=True,
    )
    payment_status = serializers.CharField(
        source='order.payment.status',
        read_only=True,
    )

    class Meta:
        model = Delivery
        fields = (
            'id', 'order_id', 'customer_name', 'total_amount', 'items',
            'restaurant_name', 'delivery_address', 'delivery_instructions',
            'pickup_branch_name', 'pickup_address', 'pickup_phone',
            'pickup_city', 'pickup_area', 'pickup_latitude', 'pickup_longitude',
            'pickup_distance_km',
            'offer_radius_km',
            'status', 'current_latitude', 'current_longitude', 'assigned_at',
            'payment_method', 'payment_status',
            'partner_fee', 'payout_status', 'paid_at',
            'confirmation_verified_at',
        )

    def get_customer_name(self, obj):
        return obj.order.customer.get_full_name() or obj.order.customer.username

    def get_items(self, obj):
        return [
            {
                'name': item.food.food_name,
                'quantity': item.quantity,
                'selected_options': item.selected_options,
            }
            for item in obj.order.items.all()
        ]

    def get_pickup_branch(self, obj):
        if hasattr(obj, '_cached_partner_pickup_branch'):
            return obj._cached_partner_pickup_branch
        branch = pickup_restaurant_for_order(obj.order)
        obj._cached_partner_pickup_branch = branch
        return branch

    def get_restaurant_name(self, obj):
        branch = self.get_pickup_branch(obj)
        return branch.rest_name if branch else ''

    def get_pickup_branch_name(self, obj):
        branch = self.get_pickup_branch(obj)
        return branch.branch_name or branch.rest_name if branch else ''

    def get_pickup_address(self, obj):
        branch = self.get_pickup_branch(obj)
        if not branch:
            return ''
        parts = [
            branch.rest_address,
            getattr(branch.area_ref, 'name', '') if branch.area_ref_id else '',
            getattr(branch.city_ref, 'name', '') if branch.city_ref_id else branch.rest_city,
        ]
        return ', '.join(part for part in parts if part)

    def get_pickup_phone(self, obj):
        branch = self.get_pickup_branch(obj)
        return branch.rest_contact if branch else ''

    def get_pickup_city(self, obj):
        branch = self.get_pickup_branch(obj)
        if not branch:
            return ''
        return getattr(branch.city_ref, 'name', '') if branch.city_ref_id else branch.rest_city

    def get_pickup_area(self, obj):
        branch = self.get_pickup_branch(obj)
        if not branch:
            return ''
        return getattr(branch.area_ref, 'name', '') if branch.area_ref_id else ''

    def get_pickup_latitude(self, obj):
        branch = self.get_pickup_branch(obj)
        return branch.pickup_latitude if branch else None

    def get_pickup_longitude(self, obj):
        branch = self.get_pickup_branch(obj)
        return branch.pickup_longitude if branch else None

    def get_pickup_distance_km(self, obj):
        if hasattr(obj, 'pickup_distance_km'):
            distance = obj.pickup_distance_km
            return round(distance, 1) if distance is not None else None

        request = self.context.get('request')
        partner = getattr(getattr(request, 'user', None), 'delivery_partner', None)
        branch = self.get_pickup_branch(obj)
        if not partner or not branch:
            return None
        distance = partner_distance_km(partner, branch)
        return round(distance, 1) if distance is not None else None

    def get_offer_radius_km(self, obj):
        return offer_radius_km(obj)


class PartnerMerchantInviteSerializer(serializers.ModelSerializer):
    merchant = serializers.SerializerMethodField()
    home_restaurant_detail = serializers.SerializerMethodField()

    class Meta:
        model = MerchantRiderInvite
        fields = (
            'id', 'merchant', 'name', 'phone', 'email', 'transport_type',
            'home_restaurant_detail', 'invite_token', 'status', 'expires_at',
            'created_at', 'updated_at',
        )

    def get_merchant(self, obj):
        merchant = obj.merchant
        return {
            'id': merchant.id,
            'business_name': merchant.business_name,
            'phone': merchant.phone,
            'email': merchant.user.email,
        }

    def get_home_restaurant_detail(self, obj):
        branch = obj.home_restaurant
        if not branch:
            return None
        return {
            'id': branch.id,
            'name': branch.rest_name,
            'branch_name': branch.branch_name or branch.rest_name,
            'branch_type': branch.branch_type,
            'phone': branch.rest_contact,
            'city': branch.city_ref.name if branch.city_ref_id else branch.rest_city,
            'area': branch.area_ref.name if branch.area_ref_id else '',
        }


def get_partner(user):
    if not hasattr(user, 'delivery_partner'):
        raise PermissionDenied('Delivery partner access required.')
    partner = user.delivery_partner
    if not partner.is_verified:
        raise PermissionDenied('Your delivery partner account is awaiting approval.')
    return partner


def get_any_partner(user):
    if not hasattr(user, 'delivery_partner'):
        raise PermissionDenied('Delivery partner access required.')
    return user.delivery_partner


def _partner_invite_match_query(partner):
    query = Q(linked_partner=partner)
    if partner.user.email:
        query |= Q(email__iexact=partner.user.email)
    if partner.partner_phone:
        query |= Q(phone=partner.partner_phone)
    return query


class PartnerMerchantInviteListView(ListAPIView):
    serializer_class = PartnerMerchantInviteSerializer

    def get_queryset(self):
        partner = get_any_partner(self.request.user)
        return (
            MerchantRiderInvite.objects
            .filter(_partner_invite_match_query(partner))
            .filter(status=MerchantRiderInvite.STATUS_PENDING, expires_at__gt=timezone.now())
            .select_related(
                'merchant__user',
                'home_restaurant',
                'home_restaurant__city_ref',
                'home_restaurant__area_ref',
            )
            .order_by('-created_at')
        )


class PartnerDeliveryListView(ListAPIView):
    serializer_class = PartnerDeliverySerializer

    def get_queryset(self):
        partner = get_partner(self.request.user)
        return (
            Delivery.objects.filter(delivery_partner=partner)
            .select_related(
                'order__customer', 'order__payment', 'order__pickup_branch',
                'order__pickup_branch__city_ref', 'order__pickup_branch__area_ref',
            )
            .prefetch_related('order__items__food__restaurant')
            .order_by('-assigned_at')
        )


class PartnerEarningsSummaryView(APIView):
    def get(self, request):
        partner = get_partner(request.user)
        deliveries = Delivery.objects.filter(delivery_partner=partner)
        return Response({
            'active_deliveries': deliveries.exclude(status='DELIVERED').count(),
            'completed_deliveries': deliveries.filter(status='DELIVERED').count(),
            'available_earnings': deliveries.filter(
                payout_status='AVAILABLE'
            ).aggregate(total=Sum('partner_fee'))['total'] or 0,
            'paid_earnings': deliveries.filter(
                payout_status='PAID'
            ).aggregate(total=Sum('partner_fee'))['total'] or 0,
            'lifetime_earnings': deliveries.filter(
                payout_status__in=('AVAILABLE', 'PAID')
            ).aggregate(total=Sum('partner_fee'))['total'] or 0,
        })


class AvailableDeliveryListView(ListAPIView):
    serializer_class = PartnerDeliverySerializer

    def get_queryset(self):
        partner = get_partner(self.request.user)
        if not partner.is_available:
            return Delivery.objects.none()
        return Delivery.objects.filter(
            delivery_partner__isnull=True,
            order__status='READY_FOR_PICKUP',
        ).select_related(
            'order__customer', 'order__payment', 'order__pickup_branch',
            'order__pickup_branch__city_ref', 'order__pickup_branch__area_ref',
        ).prefetch_related('order__items__food__restaurant').order_by('delivery_date')

    def list(self, request, *args, **kwargs):
        partner = get_partner(request.user)
        deliveries = [
            delivery for delivery in self.get_queryset()
            if partner_is_eligible(delivery, partner)
        ]
        deliveries = sort_deliveries_for_partner(deliveries, partner)
        serializer = self.get_serializer(deliveries, many=True)
        return Response({
            'count': len(deliveries),
            'next': None,
            'previous': None,
            'results': serializer.data,
        })


class AvailableDeliveryClaimView(APIView):
    def post(self, request, delivery_id):
        partner = get_partner(request.user)
        delivery = claim_pending_delivery(delivery_id, partner)
        if not delivery:
            return Response(
                {'detail': 'This delivery is no longer available or you already have an active job.'},
                status=status.HTTP_409_CONFLICT,
            )
        delivery = Delivery.objects.select_related(
            'order__customer', 'order__payment', 'order__pickup_branch',
            'order__pickup_branch__city_ref', 'order__pickup_branch__area_ref',
        ).prefetch_related('order__items__food__restaurant').get(id=delivery.id)
        notify_order_event(
            delivery.order,
            'rider_assigned',
            actor=request.user,
            delivery=delivery,
        )
        return Response(PartnerDeliverySerializer(delivery).data)


class PartnerAvailabilityLocationView(APIView):
    def patch(self, request):
        partner = get_partner(request.user)
        try:
            latitude = float(request.data['latitude'])
            longitude = float(request.data['longitude'])
        except (KeyError, TypeError, ValueError):
            return Response(
                {'detail': 'Valid latitude and longitude are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            return Response(
                {'detail': 'Location coordinates are out of range.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        partner.current_latitude = latitude
        partner.current_longitude = longitude
        partner.location_updated_at = timezone.now()
        partner.save(update_fields=(
            'current_latitude', 'current_longitude', 'location_updated_at'
        ))
        return Response({
            'current_latitude': partner.current_latitude,
            'current_longitude': partner.current_longitude,
            'location_updated_at': partner.location_updated_at,
        })


class PartnerDeliveryStatusView(APIView):
    transitions = {
        'ASSIGNED': 'PICKED_UP',
        'PICKED_UP': 'ON_THE_WAY',
        'ON_THE_WAY': 'DELIVERED',
    }
    order_statuses = {
        'PICKED_UP': 'READY_FOR_PICKUP',
        'ON_THE_WAY': 'ON_THE_WAY',
        'DELIVERED': 'DELIVERED',
    }

    @transaction.atomic
    def patch(self, request, delivery_id):
        partner = get_partner(request.user)
        delivery = Delivery.objects.select_for_update().filter(
            id=delivery_id,
            delivery_partner=partner,
        ).select_related('order').first()
        if not delivery:
            return Response(
                {'detail': 'Delivery not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        new_status = request.data.get('status')
        expected_status = self.transitions.get(delivery.status)
        if new_status != expected_status:
            return Response(
                {'status': [f'Next status must be {expected_status or "none"}.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_status == 'DELIVERED':
            confirmation_code = str(
                request.data.get('confirmation_code', '')
            ).strip()
            if not delivery.confirmation_code or not compare_digest(
                confirmation_code, delivery.confirmation_code
            ):
                return Response(
                    {'confirmation_code': [
                        'Enter the six-digit code shown to the customer.'
                    ]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        previous_delivery_status = delivery.status
        delivery.status = new_status
        if 'latitude' in request.data:
            delivery.current_latitude = request.data['latitude']
        if 'longitude' in request.data:
            delivery.current_longitude = request.data['longitude']
        delivery.save()

        delivery.order.status = self.order_statuses[new_status]
        delivery.order.save(update_fields=['status', 'updated_at'])

        if new_status == 'DELIVERED':
            delivery.confirmation_verified_at = timezone.now()
            delivery.confirmation_code = ''
            delivery.save(update_fields=[
                'confirmation_verified_at', 'confirmation_code'
            ])
            partner.is_available = True
            partner.save(update_fields=['is_available'])
            delivery.payout_status = 'AVAILABLE'
            delivery.save(update_fields=['payout_status'])
            record_partner_payout_audit(
                delivery=delivery,
                status='AVAILABLE',
            )
            notify_payout_event(delivery, 'partner_available')
            if not delivery.order.loyalty_points_awarded:
                points = max(1, int(delivery.order.total_amount / 100))
                profile, _ = Customer.objects.get_or_create(
                    user=delivery.order.customer
                )
                Customer.objects.filter(id=profile.id).update(
                    loyalty_points=F('loyalty_points') + points
                )
                delivery.order.loyalty_points_awarded = True
                delivery.order.save(
                    update_fields=['loyalty_points_awarded', 'updated_at']
                )
            notify_admin_delivered(delivery)
            if (
                hasattr(delivery.order, 'payment')
                and delivery.order.payment.method == 'COD'
                and delivery.order.payment.status == 'PENDING'
            ):
                delivery.order.payment.status = 'SUCCESS'
                delivery.order.payment.transaction_id = (
                    f'COD-{delivery.order.id}'
                )
                delivery.order.payment.save(
                    update_fields=['status', 'transaction_id']
                )
                notify_payment_event(delivery.order.payment, 'cod_confirmed')
            if (
                hasattr(delivery.order, 'payment')
                and delivery.order.payment.status == 'SUCCESS'
            ):
                delivery.order.merchant_payout_status = 'AVAILABLE'
                delivery.order.save(update_fields=(
                    'merchant_payout_status', 'updated_at'
                ))
                record_merchant_payout_audit(
                    order=delivery.order,
                    status='AVAILABLE',
                )
                notify_payout_event(delivery.order, 'merchant_available')

        event_for_status = {
            'PICKED_UP': 'picked_up',
            'ON_THE_WAY': 'on_the_way',
            'DELIVERED': 'delivered',
        }
        notify_order_event(
            delivery.order,
            event_for_status[new_status],
            actor=request.user,
            delivery=delivery,
        )
        notify_customer_status(delivery)
        if new_status == 'DELIVERED':
            notify_partner_of_pending_deliveries(partner)
        broadcast_delivery_status_changed(
            delivery.id,
            new_status,
            previous_delivery_status,
        )
        return Response(PartnerDeliverySerializer(delivery).data)


class PartnerDeliveryLocationView(APIView):
    def patch(self, request, delivery_id):
        partner = get_partner(request.user)
        delivery = Delivery.objects.filter(
            id=delivery_id,
            delivery_partner=partner,
        ).first()
        if not delivery:
            return Response(
                {'detail': 'Delivery not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            latitude = float(request.data['latitude'])
            longitude = float(request.data['longitude'])
        except (KeyError, TypeError, ValueError):
            return Response(
                {'detail': 'Valid latitude and longitude are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            return Response(
                {'detail': 'Location coordinates are out of range.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        delivery.current_latitude = latitude
        delivery.current_longitude = longitude
        delivery.save(update_fields=['current_latitude', 'current_longitude'])
        partner.current_latitude = latitude
        partner.current_longitude = longitude
        partner.location_updated_at = timezone.now()
        partner.save(update_fields=[
            'current_latitude', 'current_longitude', 'location_updated_at',
        ])
        return Response(PartnerDeliverySerializer(delivery).data)

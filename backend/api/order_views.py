from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import IntegrityError, transaction
from uuid import UUID

from orders.models import Order
from notifications.events import notify_order_event, notify_payment_event
from restaurants.services import restaurant_accepting_orders
from .serializers import (
    OfferValidationSerializer,
    OrderCreateSerializer,
    OrderSerializer,
)


class OrderListCreateView(generics.ListCreateAPIView):
    def get_queryset(self):
        return (
            Order.objects.filter(customer=self.request.user)
            .select_related('payment', 'delivery__delivery_partner', 'review')
            .prefetch_related('items__food__restaurant', 'status_events')
            .order_by('-created_at')
        )

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return OrderCreateSerializer
        return OrderSerializer

    def create(self, request, *args, **kwargs):
        raw_client_order_id = request.data.get('client_order_id')
        if raw_client_order_id:
            try:
                client_order_id = UUID(str(raw_client_order_id))
            except (TypeError, ValueError, AttributeError):
                client_order_id = None
            if client_order_id:
                existing = Order.objects.filter(
                    customer=request.user,
                    client_order_id=client_order_id,
                ).first()
                if existing:
                    return Response(OrderSerializer(
                        existing,
                        context=self.get_serializer_context(),
                    ).data)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        client_order_id = serializer.validated_data.get('client_order_id')
        if client_order_id:
            existing = Order.objects.filter(
                customer=request.user,
                client_order_id=client_order_id,
            ).first()
            if existing:
                return Response(OrderSerializer(
                    existing, context=self.get_serializer_context()
                ).data)

        try:
            order = serializer.save()
        except IntegrityError:
            # A concurrent retry may win after the lookup but before insertion.
            order = Order.objects.filter(
                customer=request.user,
                client_order_id=client_order_id,
            ).first()
            if not order:
                raise
            return Response(OrderSerializer(
                order, context=self.get_serializer_context()
            ).data)
        notify_order_event(order, 'placed')
        return Response(
            OrderSerializer(
                order, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_201_CREATED,
        )


class OrderDetailView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.filter(
            customer=self.request.user
        ).select_related(
            'payment', 'delivery__delivery_partner', 'review'
        ).prefetch_related('items__food__restaurant', 'status_events')


class OfferValidationView(APIView):
    def post(self, request):
        serializer = OfferValidationSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        pricing = serializer.validated_data['_pricing']
        offer = pricing['offer']
        return Response({
            'offer_code': offer.code if offer else None,
            'discount_percent': offer.discount_percent if offer else 0,
            'subtotal_amount': pricing['subtotal'],
            'discount_amount': pricing['discount'],
            'delivery_fee': pricing['delivery_fee'],
            'total_amount': pricing['total'],
        })


class OrderCancelView(APIView):
    @transaction.atomic
    def post(self, request, order_id):
        order = Order.objects.select_for_update().filter(
            id=order_id,
            customer=request.user,
        ).first()
        if not order:
            return Response(
                {'detail': 'Order not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if order.status not in ('PLACED', 'CONFIRMED'):
            return Response(
                {'detail': 'This order can no longer be cancelled.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        order.status = 'CANCELLED'
        order.merchant_payout_status = 'CANCELLED'
        order.save(update_fields=[
            'status', 'merchant_payout_status', 'updated_at'
        ])
        if hasattr(order, 'payment') and order.payment.status == 'SUCCESS':
            order.payment.status = 'REFUNDED'
            order.payment.save(update_fields=['status'])
            notify_payment_event(order.payment, 'refund_completed')
        elif hasattr(order, 'payment') and order.payment.status == 'PENDING':
            order.payment.status = 'CANCELLED'
            order.payment.save(update_fields=['status'])
        notify_order_event(
            order,
            'cancelled',
            message='The customer cancelled this order before preparation.',
        )

        order = Order.objects.select_related(
            'payment', 'delivery__delivery_partner', 'review'
        ).prefetch_related('items__food__restaurant', 'status_events').get(id=order.id)
        return Response(OrderSerializer(order).data)


class OrderReorderView(APIView):
    def get(self, request, order_id):
        order = Order.objects.filter(
            id=order_id,
            customer=request.user,
        ).prefetch_related(
            'items__food__restaurant',
            'items__food__option_groups__options',
        ).first()
        if not order:
            return Response(
                {'detail': 'Order not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        first_line = order.items.first()
        if not first_line:
            return Response(
                {'detail': 'This order has no items to reorder.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        restaurant = first_line.food.restaurant
        if not restaurant_accepting_orders(restaurant):
            return Response(
                {'detail': 'This restaurant is not accepting orders right now.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        available_items = []
        unavailable_items = []
        for line in order.items.all():
            food = line.food
            if food.restaurant_id != restaurant.id or not food.is_available:
                unavailable_items.append(food.food_name)
                continue
            selected_ids = {
                option.get('option_id') for option in line.selected_options
                if option.get('option_id') is not None
            }
            current_options = []
            customization_available = True
            for group in food.option_groups.all():
                selected = [
                    option for option in group.options.all()
                    if option.id in selected_ids and option.is_available
                ]
                if not group.min_select <= len(selected) <= group.max_select:
                    customization_available = False
                    break
                current_options.extend({
                    'id': option.id,
                    'group': group.name,
                    'name': option.name,
                    'price_delta': option.price_delta,
                } for option in selected)
            if len(current_options) != len(selected_ids):
                customization_available = False
            if not customization_available:
                unavailable_items.append(f'{food.food_name} customization')
                continue
            available_items.append({
                'id': food.id,
                'food_name': food.food_name,
                'food_price': food.food_price,
                'image': (
                    request.build_absolute_uri(food.image.url)
                    if food.image else None
                ),
                'quantity': line.quantity,
                'options': current_options,
            })

        if not available_items:
            return Response(
                {'detail': 'None of the original items are currently available.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({
            'restaurant_id': restaurant.id,
            'restaurant_name': restaurant.rest_name,
            'items': available_items,
            'unavailable_items': unavailable_items,
        })

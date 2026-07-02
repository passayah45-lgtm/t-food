from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order
from payments.gateway import (
    PaymentGatewayError,
    online_payments_enabled,
)
from payments.models import Payment, PaymentWebhookEvent
from payments.providers.resolver import PaymentProviderResolutionError
from payments.services import (
    OnlinePaymentsUnavailable,
    PaymentService,
)
from .serializers import OrderSerializer


def serialized_order(order_id):
    order = Order.objects.prefetch_related('items__food').select_related(
        'payment', 'delivery__delivery_partner'
    ).get(id=order_id)
    return OrderSerializer(order).data


class PaymentConfigView(APIView):
    def get(self, request):
        return Response({
            'online_payments_enabled': online_payments_enabled(),
            'provider': 'razorpay' if online_payments_enabled() else None,
        })


class OrderPaymentView(APIView):
    @transaction.atomic
    def post(self, request, order_id):
        order = Order.objects.select_for_update().filter(
            id=order_id, customer=request.user
        ).first()
        if not order:
            return Response({'detail': 'Order not found.'}, status=404)
        if order.status == 'CANCELLED':
            return Response(
                {'detail': 'Cancelled orders cannot be paid.'}, status=400
            )
        if order.status == 'EXPIRED':
            return Response(
                {'detail': 'The payment window for this order has expired.'},
                status=400,
            )

        method = request.data.get('method')
        if method not in dict(Payment.PAYMENT_METHODS):
            return Response(
                {'method': ['Choose a valid payment method.']}, status=400
            )

        if order.status != 'PLACED':
            if (
                hasattr(order, 'payment')
                and order.payment.method == 'COD'
                and method == 'COD'
            ):
                return Response(serialized_order(order.id))
            return Response(
                {'detail': 'This order has already been confirmed.'}, status=400
            )

        existing_payment = Payment.objects.filter(order=order).first()
        if existing_payment and existing_payment.status in (
            'SUCCESS', 'REFUNDED', 'CANCELLED'
        ):
            if existing_payment.status == 'SUCCESS':
                return Response(serialized_order(order.id))
            return Response(
                {'detail': 'Payment can no longer be changed for this order.'},
                status=400,
            )

        service = PaymentService()
        try:
            result = service.create_payment(
                order,
                method,
                user=request.user,
            )
        except OnlinePaymentsUnavailable:
            return Response(
                {
                    'detail': (
                        'Online payments are not available yet. '
                        'Please choose cash on delivery.'
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except PaymentGatewayError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except PaymentProviderResolutionError as exc:
            return Response({'detail': str(exc)}, status=400)

        if result.provider.code == 'cod':
            return Response(serialized_order(order.id))

        return Response({
            'payment_required': True,
            'provider': 'razorpay',
            'key_id': settings.RAZORPAY_KEY_ID,
            'provider_order_id': result.payment.provider_order_id,
            'amount': int(order.total_amount * 100),
            'currency': 'INR',
            'order_id': order.id,
            'customer': {
                'name': request.user.get_full_name() or request.user.username,
                'email': request.user.email,
                'contact': order.contact_phone,
            },
        })


class OrderPaymentVerifyView(APIView):
    @transaction.atomic
    def post(self, request, order_id):
        order = Order.objects.select_for_update().filter(
            id=order_id, customer=request.user
        ).first()
        if not order:
            return Response({'detail': 'Payment not found.'}, status=404)
        payment = Payment.objects.select_for_update().filter(order=order).first()
        if not payment:
            return Response({'detail': 'Payment not found.'}, status=404)
        if payment.status == 'SUCCESS':
            return Response(serialized_order(order.id))
        if payment.provider != 'RAZORPAY' or not payment.provider_order_id:
            return Response({'detail': 'No online payment is pending.'}, status=400)

        provider_order_id = request.data.get('razorpay_order_id', '')
        payment_id = request.data.get('razorpay_payment_id', '')
        signature = request.data.get('razorpay_signature', '')
        if provider_order_id != payment.provider_order_id or not all(
            (payment_id, signature)
        ):
            return Response({'detail': 'Invalid payment confirmation.'}, status=400)

        try:
            PaymentService().confirm_payment(
                payment,
                confirmation_payload=request.data,
                user=request.user,
            )
        except ValidationError:
            return Response({'detail': 'Payment verification failed.'}, status=400)
        except PaymentProviderResolutionError as exc:
            return Response({'detail': str(exc)}, status=400)

        return Response(serialized_order(order.id))


class RazorpayWebhookView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_classes = ()

    @transaction.atomic
    def post(self, request):
        try:
            result = PaymentService().handle_webhook('razorpay', request)
        except PaymentProviderResolutionError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(result.data, status=result.status_code)

from rest_framework import generics, serializers

from orders.models import Order, SupportTicket
from notifications.events import notify_payment_event, notify_support_event


class SupportTicketSerializer(serializers.ModelSerializer):
    order_total = serializers.DecimalField(
        source='order.total_amount', max_digits=10, decimal_places=2, read_only=True
    )
    payment_status = serializers.CharField(source='order.payment.status', read_only=True)
    request_refund = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = SupportTicket
        fields = (
            'id', 'order', 'order_total', 'category', 'description', 'status',
            'refund_status', 'refunded_amount', 'resolution', 'payment_status',
            'request_refund', 'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'status', 'refund_status', 'refunded_amount', 'resolution',
            'created_at', 'updated_at',
        )

    def validate_order(self, order):
        if order.customer_id != self.context['request'].user.id:
            raise serializers.ValidationError('Choose one of your own orders.')
        return order

    def validate(self, attrs):
        order = attrs['order']
        if SupportTicket.objects.filter(
            customer=self.context['request'].user,
            order=order,
            status__in=('OPEN', 'IN_REVIEW'),
        ).exists():
            raise serializers.ValidationError(
                'You already have an active support ticket for this order.'
            )
        return attrs

    def create(self, validated_data):
        request_refund = validated_data.pop('request_refund', False)
        ticket = SupportTicket.objects.create(
            customer=self.context['request'].user,
            refund_status='REQUESTED' if request_refund else 'NONE',
            **validated_data,
        )
        notify_support_event(ticket, 'created', actor=self.context['request'].user)
        if request_refund and hasattr(ticket.order, 'payment'):
            notify_payment_event(
                ticket.order.payment,
                'refund_requested',
                actor=self.context['request'].user,
                support_ticket=ticket,
            )
        return ticket


class SupportTicketListCreateView(generics.ListCreateAPIView):
    serializer_class = SupportTicketSerializer

    def get_queryset(self):
        return SupportTicket.objects.filter(
            customer=self.request.user
        ).select_related('order', 'order__payment')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

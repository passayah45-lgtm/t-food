from django.db import migrations, models
import django.db.models.deletion


def backfill_status_events(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    OrderStatusEvent = apps.get_model('orders', 'OrderStatusEvent')
    details = {
        'PLACED': ('CHECKOUT', 'Order created and awaiting payment.'),
        'CONFIRMED': ('PAYMENT', 'Payment or cash-on-delivery confirmation received.'),
        'PREPARING': ('MERCHANT', 'Merchant accepted the order and began preparation.'),
        'READY_FOR_PICKUP': ('MERCHANT', 'Order is ready for a delivery partner.'),
        'ON_THE_WAY': ('DELIVERY', 'Delivery partner is on the way to the customer.'),
        'DELIVERED': ('DELIVERY', 'Order was delivered to the customer.'),
        'CANCELLED': ('CANCELLATION', 'Order was cancelled.'),
        'EXPIRED': ('SYSTEM', 'Payment window expired before confirmation.'),
    }
    events = []
    for order in Order.objects.all().iterator():
        source, description = details.get(
            order.status, ('SYSTEM', f'Current status: {order.status}.')
        )
        events.append(OrderStatusEvent(
            order_id=order.id,
            status=order.status,
            source=source,
            description=description,
        ))
    OrderStatusEvent.objects.bulk_create(events, batch_size=500)


class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0014_order_payment_expiry'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrderStatusEvent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('PLACED', 'Placed'), ('CONFIRMED', 'Confirmed'), ('PREPARING', 'Preparing'), ('READY_FOR_PICKUP', 'Ready for Pickup'), ('ON_THE_WAY', 'On the Way'), ('DELIVERED', 'Delivered'), ('CANCELLED', 'Cancelled'), ('EXPIRED', 'Payment Expired')], max_length=20)),
                ('source', models.CharField(choices=[('CHECKOUT', 'Checkout'), ('PAYMENT', 'Payment'), ('MERCHANT', 'Merchant'), ('DELIVERY', 'Delivery'), ('CANCELLATION', 'Cancellation'), ('SYSTEM', 'System')], max_length=20)),
                ('description', models.CharField(max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='status_events', to='orders.order')),
            ],
            options={'ordering': ('created_at', 'id')},
        ),
        migrations.AddIndex(
            model_name='orderstatusevent',
            index=models.Index(fields=['order', 'created_at'], name='orders_orde_order_i_1e3f4d_idx'),
        ),
        migrations.RunPython(backfill_status_events, migrations.RunPython.noop),
    ]

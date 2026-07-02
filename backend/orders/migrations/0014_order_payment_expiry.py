from datetime import timedelta

from django.db import migrations, models
from django.utils import timezone


def set_existing_payment_deadlines(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    Order.objects.filter(status='PLACED').update(
        payment_expires_at=timezone.now() + timedelta(minutes=15)
    )


class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0013_order_delivery_instructions'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(choices=[('PLACED', 'Placed'), ('CONFIRMED', 'Confirmed'), ('PREPARING', 'Preparing'), ('READY_FOR_PICKUP', 'Ready for Pickup'), ('ON_THE_WAY', 'On the Way'), ('DELIVERED', 'Delivered'), ('CANCELLED', 'Cancelled'), ('EXPIRED', 'Payment Expired')], default='PLACED', max_length=20),
        ),
        migrations.AddField(
            model_name='order',
            name='payment_expires_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(set_existing_payment_deadlines, migrations.RunPython.noop),
    ]

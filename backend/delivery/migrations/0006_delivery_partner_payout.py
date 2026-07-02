from django.db import migrations, models


def backfill_delivery_fees(apps, schema_editor):
    Delivery = apps.get_model('delivery', 'Delivery')
    for delivery in Delivery.objects.select_related('order').all():
        delivery.partner_fee = delivery.order.delivery_fee
        if delivery.status == 'DELIVERED' and delivery.delivery_partner_id:
            delivery.payout_status = 'AVAILABLE'
        delivery.save(update_fields=['partner_fee', 'payout_status'])


class Migration(migrations.Migration):
    dependencies = [
        ('delivery', '0005_partner_availability_location'),
    ]

    operations = [
        migrations.AddField(
            model_name='delivery',
            name='partner_fee',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='delivery',
            name='payout_status',
            field=models.CharField(choices=[('PENDING', 'Pending delivery'), ('AVAILABLE', 'Available for payout'), ('PAID', 'Paid')], default='PENDING', max_length=20),
        ),
        migrations.AddField(
            model_name='delivery',
            name='paid_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_delivery_fees, migrations.RunPython.noop),
    ]

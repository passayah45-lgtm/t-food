from django.db import migrations, models


def backfill_merchant_payouts(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    Order.objects.filter(
        status='DELIVERED',
        payment__status='SUCCESS',
    ).update(merchant_payout_status='AVAILABLE')
    Order.objects.filter(status='CANCELLED').update(
        merchant_payout_status='CANCELLED'
    )


class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0010_supportticket'),
        ('payments', '0004_alter_payment_status_cancelled'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='merchant_payout_status',
            field=models.CharField(choices=[('PENDING', 'Pending delivery'), ('AVAILABLE', 'Available for payout'), ('PAID', 'Paid'), ('CANCELLED', 'Cancelled')], default='PENDING', max_length=20),
        ),
        migrations.AddField(
            model_name='order',
            name='merchant_paid_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_merchant_payouts, migrations.RunPython.noop),
    ]

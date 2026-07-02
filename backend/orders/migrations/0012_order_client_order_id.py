from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0011_order_merchant_payout_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='client_order_id',
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name='order',
            constraint=models.UniqueConstraint(
                condition=models.Q(client_order_id__isnull=False),
                fields=('customer', 'client_order_id'),
                name='unique_customer_client_order_id',
            ),
        ),
    ]

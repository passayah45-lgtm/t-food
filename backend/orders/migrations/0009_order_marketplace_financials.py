from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0008_order_delivery_fee'),
        ('restaurants', '0005_restaurant_commercial_terms'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='merchant_payout',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='order',
            name='platform_fee',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]

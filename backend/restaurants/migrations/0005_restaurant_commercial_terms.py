from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('restaurants', '0004_marketplace_merchant_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='restaurant',
            name='min_order_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='restaurant',
            name='commission_percent',
            field=models.PositiveSmallIntegerField(default=15),
        ),
    ]

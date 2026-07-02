from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0006_offer_order_discount_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(
                choices=[
                    ('PLACED', 'Placed'),
                    ('CONFIRMED', 'Confirmed'),
                    ('PREPARING', 'Preparing'),
                    ('READY_FOR_PICKUP', 'Ready for Pickup'),
                    ('ON_THE_WAY', 'On the Way'),
                    ('DELIVERED', 'Delivered'),
                    ('CANCELLED', 'Cancelled'),
                ],
                default='PLACED',
                max_length=20,
            ),
        ),
    ]

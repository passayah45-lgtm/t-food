from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0015_orderstatusevent'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='delivery_distance_km',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='estimated_delivery_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

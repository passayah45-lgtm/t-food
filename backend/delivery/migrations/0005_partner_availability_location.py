from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('delivery', '0004_deliverypartner_is_verified'),
    ]

    operations = [
        migrations.AddField(
            model_name='deliverypartner',
            name='current_latitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name='deliverypartner',
            name='current_longitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name='deliverypartner',
            name='location_updated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

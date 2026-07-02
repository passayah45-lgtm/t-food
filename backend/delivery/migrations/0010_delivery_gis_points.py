from django.db import migrations
import fooddelivery.gis_fields


class Migration(migrations.Migration):
    dependencies = [
        ('markets', '0003_enable_postgis'),
        ('delivery', '0009_deliverypartner_verification_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='deliverypartner',
            name='current_point',
            field=fooddelivery.gis_fields.PointField(
                blank=True,
                null=True,
                srid=4326,
            ),
        ),
        migrations.AddField(
            model_name='delivery',
            name='current_point',
            field=fooddelivery.gis_fields.PointField(
                blank=True,
                null=True,
                srid=4326,
            ),
        ),
    ]

from django.db import migrations
import fooddelivery.gis_fields


class Migration(migrations.Migration):
    dependencies = [
        ('markets', '0003_enable_postgis'),
        ('customers', '0010_customer_market_deliveryaddress_market'),
    ]

    operations = [
        migrations.AddField(
            model_name='deliveryaddress',
            name='location_point',
            field=fooddelivery.gis_fields.PointField(
                blank=True,
                null=True,
                srid=4326,
            ),
        ),
    ]

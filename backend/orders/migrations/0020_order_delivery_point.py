from django.db import migrations
import fooddelivery.gis_fields


class Migration(migrations.Migration):
    dependencies = [
        ('markets', '0003_enable_postgis'),
        ('orders', '0019_offer_market_order_market'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='delivery_point',
            field=fooddelivery.gis_fields.PointField(
                blank=True,
                null=True,
                srid=4326,
            ),
        ),
    ]

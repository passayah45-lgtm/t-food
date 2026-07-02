from django.db import migrations


def backfill_points(apps, schema_editor):
    from fooddelivery.gis_backfill import backfill_gis_points

    backfill_gis_points(apps=apps)


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0003_enable_postgis'),
        ('restaurants', '0014_restaurant_pickup_point'),
        ('customers', '0011_deliveryaddress_location_point'),
        ('delivery', '0010_delivery_gis_points'),
        ('orders', '0020_order_delivery_point'),
    ]

    operations = [
        migrations.RunPython(backfill_points, migrations.RunPython.noop),
    ]

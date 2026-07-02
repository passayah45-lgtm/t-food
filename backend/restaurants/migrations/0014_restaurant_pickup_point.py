from django.db import migrations
import fooddelivery.gis_fields


class Migration(migrations.Migration):
    dependencies = [
        ('markets', '0003_enable_postgis'),
        ('restaurants', '0013_merchantprofile_verification_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='restaurant',
            name='pickup_point',
            field=fooddelivery.gis_fields.PointField(
                blank=True,
                null=True,
                srid=4326,
            ),
        ),
    ]

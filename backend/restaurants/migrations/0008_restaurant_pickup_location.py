from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('restaurants', '0007_restaurant_and_item_images'),
    ]

    operations = [
        migrations.AddField(
            model_name='restaurant',
            name='pickup_latitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name='restaurant',
            name='pickup_longitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
    ]

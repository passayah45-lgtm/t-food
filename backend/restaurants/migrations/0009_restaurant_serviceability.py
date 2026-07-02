from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('restaurants', '0008_restaurant_pickup_location'),
    ]

    operations = [
        migrations.AddField(
            model_name='restaurant',
            name='delivery_radius_km',
            field=models.DecimalField(decimal_places=2, default=15, max_digits=5, validators=[MinValueValidator(1), MaxValueValidator(50)]),
        ),
        migrations.AddField(
            model_name='restaurant',
            name='estimated_prep_minutes',
            field=models.PositiveSmallIntegerField(default=25, validators=[MinValueValidator(5), MaxValueValidator(180)]),
        ),
    ]

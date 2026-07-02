from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('restaurants', '0005_restaurant_commercial_terms'),
    ]

    operations = [
        migrations.AlterField(
            model_name='restaurant',
            name='commission_percent',
            field=models.PositiveSmallIntegerField(
                default=15,
                validators=[MinValueValidator(0), MaxValueValidator(100)],
            ),
        ),
    ]

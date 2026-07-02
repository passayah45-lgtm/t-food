from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0016_order_serviceability_snapshot'),
    ]

    operations = [
        migrations.AddField(
            model_name='offer',
            name='first_order_only',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='offer',
            name='max_uses_per_customer',
            field=models.PositiveIntegerField(blank=True, default=1, null=True, validators=[MinValueValidator(1)]),
        ),
        migrations.AddField(
            model_name='offer',
            name='max_uses_total',
            field=models.PositiveIntegerField(blank=True, null=True, validators=[MinValueValidator(1)]),
        ),
    ]

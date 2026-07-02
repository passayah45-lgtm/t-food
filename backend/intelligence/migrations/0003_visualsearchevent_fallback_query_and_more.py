# Generated for Visual Product Search and Review Photos Slice 9.

import decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('intelligence', '0002_visualsearchevent'),
    ]

    operations = [
        migrations.AddField(
            model_name='visualsearchevent',
            name='fallback_query',
            field=models.CharField(blank=True, max_length=240),
        ),
        migrations.AddField(
            model_name='visualsearchevent',
            name='latitude',
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                max_digits=9,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(decimal.Decimal('-90')),
                    django.core.validators.MaxValueValidator(decimal.Decimal('90')),
                ],
            ),
        ),
        migrations.AddField(
            model_name='visualsearchevent',
            name='longitude',
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                max_digits=9,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(decimal.Decimal('-180')),
                    django.core.validators.MaxValueValidator(decimal.Decimal('180')),
                ],
            ),
        ),
        migrations.AddField(
            model_name='visualsearchevent',
            name='matched_item_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='visualsearchevent',
            name='matched_merchant_count',
            field=models.PositiveIntegerField(default=0),
        ),
    ]

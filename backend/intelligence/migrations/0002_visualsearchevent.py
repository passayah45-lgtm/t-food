# Generated for Visual Product Search Slice 3.

import decimal

import django.core.validators
import django.db.models.deletion
import markets.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('intelligence', '0001_initial'),
        ('markets', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='VisualSearchEvent',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('provider_code', models.CharField(max_length=60)),
                ('labels', models.JSONField(blank=True, default=list)),
                ('normalized_query', models.CharField(blank=True, max_length=240)),
                (
                    'confidence',
                    models.DecimalField(
                        blank=True,
                        decimal_places=4,
                        max_digits=5,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(decimal.Decimal('0')),
                            django.core.validators.MaxValueValidator(decimal.Decimal('1')),
                        ],
                    ),
                ),
                (
                    'country_code',
                    models.CharField(
                        blank=True,
                        max_length=2,
                        validators=[markets.models.country_code_validator],
                    ),
                ),
                ('category', models.CharField(blank=True, max_length=80)),
                ('result_count', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'market',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='visual_search_events',
                        to='markets.market',
                    ),
                ),
                (
                    'user',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='visual_search_events',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'ordering': ('-created_at',),
                'indexes': [
                    models.Index(
                        fields=['user', '-created_at'],
                        name='intelligenc_user_id_7e9bc1_idx',
                    ),
                    models.Index(
                        fields=['market', '-created_at'],
                        name='intelligenc_market__6c4a09_idx',
                    ),
                    models.Index(
                        fields=['provider_code', '-created_at'],
                        name='intelligenc_provide_2a0d1e_idx',
                    ),
                    models.Index(
                        fields=['country_code', '-created_at'],
                        name='intelligenc_country_a0041d_idx',
                    ),
                ],
            },
        ),
    ]

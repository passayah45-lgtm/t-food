from django.core.validators import MinValueValidator
from django.db import migrations, models
import django.db.models.deletion
import fooddelivery.gis_fields


class Migration(migrations.Migration):
    dependencies = [
        ('markets', '0004_backfill_gis_points'),
    ]

    operations = [
        migrations.CreateModel(
            name='CommerceCity',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('name', models.CharField(max_length=100)),
                ('slug', models.SlugField(max_length=80)),
                (
                    'center_point',
                    fooddelivery.gis_fields.PointField(
                        blank=True,
                        null=True,
                        srid=4326,
                    ),
                ),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'market',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='commerce_cities',
                        to='markets.market',
                    ),
                ),
            ],
            options={
                'verbose_name_plural': 'commerce cities',
                'ordering': ('market__name', 'name'),
            },
        ),
        migrations.CreateModel(
            name='CommerceArea',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('name', models.CharField(max_length=100)),
                ('slug', models.SlugField(max_length=80)),
                (
                    'center_point',
                    fooddelivery.gis_fields.PointField(
                        blank=True,
                        null=True,
                        srid=4326,
                    ),
                ),
                (
                    'service_radius_km',
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=6,
                        null=True,
                        validators=[MinValueValidator(0)],
                    ),
                ),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'city',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='areas',
                        to='markets.commercecity',
                    ),
                ),
                (
                    'market',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='commerce_areas',
                        to='markets.market',
                    ),
                ),
            ],
            options={
                'ordering': ('city__name', 'name'),
            },
        ),
        migrations.AddIndex(
            model_name='commercecity',
            index=models.Index(
                fields=['market', 'is_active', 'name'],
                name='markets_com_market__540263_idx',
            ),
        ),
        migrations.AddConstraint(
            model_name='commercecity',
            constraint=models.UniqueConstraint(
                fields=('market', 'slug'),
                name='unique_commerce_city_slug_per_market',
            ),
        ),
        migrations.AddIndex(
            model_name='commercearea',
            index=models.Index(
                fields=['market', 'is_active', 'name'],
                name='markets_com_market__f4f830_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='commercearea',
            index=models.Index(
                fields=['city', 'is_active', 'name'],
                name='markets_com_city_id_155b7e_idx',
            ),
        ),
        migrations.AddConstraint(
            model_name='commercearea',
            constraint=models.UniqueConstraint(
                fields=('city', 'slug'),
                name='unique_commerce_area_slug_per_city',
            ),
        ),
    ]

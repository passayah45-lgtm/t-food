# Generated manually for Sprint 7 intelligence foundation.

import decimal

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('markets', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='RecommendationEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('surface', models.CharField(max_length=80)),
                ('object_type', models.CharField(max_length=40)),
                ('object_id', models.CharField(max_length=80)),
                ('action', models.CharField(choices=[('impression', 'Impression'), ('click', 'Click'), ('order', 'Order')], max_length=20)),
                ('score', models.DecimalField(blank=True, decimal_places=4, max_digits=8, null=True)),
                ('reason_codes', models.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recommendation_events', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-created_at',),
            },
        ),
        migrations.CreateModel(
            name='SearchEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('query', models.CharField(blank=True, max_length=200)),
                ('category', models.CharField(blank=True, max_length=80)),
                ('latitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, validators=[django.core.validators.MinValueValidator(decimal.Decimal('-90')), django.core.validators.MaxValueValidator(decimal.Decimal('90'))])),
                ('longitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, validators=[django.core.validators.MinValueValidator(decimal.Decimal('-180')), django.core.validators.MaxValueValidator(decimal.Decimal('180'))])),
                ('result_count', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('market', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='search_events', to='markets.market')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='search_events', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-created_at',),
            },
        ),
        migrations.AddIndex(
            model_name='recommendationevent',
            index=models.Index(fields=['user', '-created_at'], name='intelligenc_user_id_fadf7f_idx'),
        ),
        migrations.AddIndex(
            model_name='recommendationevent',
            index=models.Index(fields=['surface', 'action', '-created_at'], name='intelligenc_surface_6ad90a_idx'),
        ),
        migrations.AddIndex(
            model_name='recommendationevent',
            index=models.Index(fields=['object_type', 'object_id', '-created_at'], name='intelligenc_object__ccea25_idx'),
        ),
        migrations.AddIndex(
            model_name='searchevent',
            index=models.Index(fields=['user', '-created_at'], name='intelligenc_user_id_3ea1e2_idx'),
        ),
        migrations.AddIndex(
            model_name='searchevent',
            index=models.Index(fields=['market', '-created_at'], name='intelligenc_market__f3c85c_idx'),
        ),
        migrations.AddIndex(
            model_name='searchevent',
            index=models.Index(fields=['query', '-created_at'], name='intelligenc_query_d96673_idx'),
        ),
    ]

# Generated manually for Sprint 1 market foundation.

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Currency',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(help_text='ISO 4217 currency code, for example INR or USD.', max_length=3, unique=True, validators=[django.core.validators.RegexValidator(message='Currency code must be a three-letter ISO 4217 code.', regex='^[A-Z]{3}$')])),
                ('numeric_code', models.CharField(blank=True, max_length=3, validators=[django.core.validators.RegexValidator(message='Numeric code must be a three-digit ISO 4217 code.', regex='^\\d{3}$')])),
                ('name', models.CharField(max_length=80)),
                ('symbol', models.CharField(blank=True, max_length=8)),
                ('minor_unit', models.PositiveSmallIntegerField(default=2, help_text='Number of decimal places used by this currency.', validators=[django.core.validators.MaxValueValidator(6)])),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name_plural': 'currencies',
                'ordering': ('code',),
            },
        ),
        migrations.CreateModel(
            name='Market',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(help_text='Stable API-safe market identifier, for example india.', max_length=60, unique=True)),
                ('name', models.CharField(max_length=100)),
                ('country_code', models.CharField(help_text='ISO 3166-1 alpha-2 country code, for example IN.', max_length=2, validators=[django.core.validators.RegexValidator(message='Country code must be a two-letter ISO 3166-1 alpha-2 code.', regex='^[A-Z]{2}$')])),
                ('timezone', models.CharField(default='Asia/Kolkata', help_text='IANA time zone used for local business rules.', max_length=64)),
                ('phone_country_code', models.CharField(blank=True, help_text='Dialing prefix, for example +91.', max_length=8)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('default_currency', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='markets', to='markets.currency')),
            ],
            options={
                'ordering': ('name',),
            },
        ),
        migrations.AddIndex(
            model_name='currency',
            index=models.Index(fields=['is_active', 'code'], name='markets_cur_is_acti_af816d_idx'),
        ),
        migrations.AddIndex(
            model_name='market',
            index=models.Index(fields=['is_active', 'country_code'], name='markets_mar_is_acti_acef4d_idx'),
        ),
        migrations.AddIndex(
            model_name='market',
            index=models.Index(fields=['slug', 'is_active'], name='markets_mar_slug_e4db69_idx'),
        ),
        migrations.AddConstraint(
            model_name='market',
            constraint=models.UniqueConstraint(condition=models.Q(('is_active', True)), fields=('country_code',), name='unique_active_market_per_country'),
        ),
    ]

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import markets.models


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0004_backfill_gis_points'),
        ('payments', '0009_merchantpayoutaudit_partnerpayoutaudit'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentProviderConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('country_code', models.CharField(max_length=2, validators=[markets.models.country_code_validator])),
                ('currency', models.CharField(max_length=3, validators=[markets.models.currency_code_validator])),
                ('provider_code', models.CharField(max_length=40)),
                ('payment_method', models.CharField(choices=[('COD', 'Cash on Delivery'), ('CARD', 'Card'), ('MOBILE_MONEY', 'Mobile Money'), ('UPI', 'UPI'), ('WALLET', 'Wallet'), ('BANK_TRANSFER', 'Bank Transfer'), ('QR_PAYMENT', 'QR Payment')], max_length=30)),
                ('is_active', models.BooleanField(default=False)),
                ('is_preferred', models.BooleanField(default=False)),
                ('priority', models.PositiveSmallIntegerField(default=100)),
                ('supports_refund', models.BooleanField(default=False)),
                ('supports_webhook', models.BooleanField(default=False)),
                ('supports_partial_refund', models.BooleanField(default=False)),
                ('credentials_present', models.BooleanField(default=False)),
                ('config_metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('market', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='payment_provider_configs', to='markets.market')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='updated_payment_provider_configs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('country_code', 'payment_method', 'priority', 'provider_code'),
                'indexes': [
                    models.Index(fields=['country_code', 'currency', 'payment_method'], name='payments_pa_country_c5f027_idx'),
                    models.Index(fields=['market', 'payment_method'], name='payments_pa_market__38a722_idx'),
                    models.Index(fields=['provider_code', 'is_active'], name='payments_pa_provide_a98a79_idx'),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name='paymentproviderconfig',
            constraint=models.UniqueConstraint(fields=('market', 'provider_code', 'payment_method'), name='unique_provider_config_per_market_method'),
        ),
        migrations.AddConstraint(
            model_name='paymentproviderconfig',
            constraint=models.UniqueConstraint(condition=models.Q(('is_preferred', True)), fields=('market', 'payment_method'), name='unique_preferred_provider_per_market_method'),
        ),
    ]

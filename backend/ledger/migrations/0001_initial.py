# Generated for Sprint 10 ledger foundation.

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('delivery', '0012_merchantriderinvite_home_restaurant'),
        ('markets', '0004_backfill_gis_points'),
        ('orders', '0020_order_delivery_point'),
        ('payments', '0007_payment_market_paymentwebhookevent_market'),
        ('restaurants', '0017_merchantfulfillmentrequestevent_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='LedgerAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('country_code', models.CharField(max_length=2, validators=[django.core.validators.RegexValidator(message='Country code must be a two-letter ISO 3166-1 alpha-2 code.', regex='^[A-Z]{2}$')])),
                ('currency', models.CharField(max_length=3, validators=[django.core.validators.RegexValidator(message='Currency code must be a three-letter ISO 4217 code.', regex='^[A-Z]{3}$')])),
                ('account_type', models.CharField(choices=[('CUSTOMER', 'Customer'), ('MERCHANT', 'Merchant'), ('PARTNER', 'Delivery partner'), ('PLATFORM', 'Platform'), ('PAYMENT_PROVIDER', 'Payment provider'), ('CASH_CLEARING', 'Cash clearing'), ('REFUND_CLEARING', 'Refund clearing'), ('FULFILLMENT_CLEARING', 'Fulfillment clearing')], max_length=30)),
                ('name', models.CharField(max_length=120)),
                ('provider_code', models.CharField(blank=True, max_length=40)),
                ('external_reference', models.CharField(blank=True, max_length=120)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('market', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='ledger_accounts', to='markets.market')),
                ('merchant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='ledger_accounts', to='restaurants.merchantprofile')),
                ('partner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='ledger_accounts', to='delivery.deliverypartner')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='ledger_accounts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('account_type', 'name', 'id'),
            },
        ),
        migrations.CreateModel(
            name='LedgerTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('country_code', models.CharField(max_length=2, validators=[django.core.validators.RegexValidator(message='Country code must be a two-letter ISO 3166-1 alpha-2 code.', regex='^[A-Z]{2}$')])),
                ('currency', models.CharField(max_length=3, validators=[django.core.validators.RegexValidator(message='Currency code must be a three-letter ISO 4217 code.', regex='^[A-Z]{3}$')])),
                ('provider_code', models.CharField(max_length=40)),
                ('transaction_type', models.CharField(choices=[('ORDER_GROSS', 'Order gross amount'), ('PLATFORM_FEE', 'Platform fee'), ('MERCHANT_PAYOUT', 'Merchant payout'), ('PARTNER_DELIVERY_FEE', 'Partner delivery fee'), ('REFUND', 'Refund'), ('PAYOUT_SETTLEMENT', 'Payout settlement'), ('FULFILLMENT_PREVIEW', 'Cross-merchant settlement preview'), ('FULFILLMENT_SETTLEMENT', 'Cross-merchant settlement'), ('ADJUSTMENT', 'Adjustment'), ('REVERSAL', 'Reversal')], max_length=40)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=14)),
                ('debit_total', models.DecimalField(decimal_places=2, max_digits=14)),
                ('credit_total', models.DecimalField(decimal_places=2, max_digits=14)),
                ('idempotency_key', models.CharField(max_length=160, unique=True)),
                ('source_type', models.CharField(blank=True, max_length=80)),
                ('source_id', models.CharField(blank=True, max_length=80)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='created_ledger_transactions', to=settings.AUTH_USER_MODEL)),
                ('delivery', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='ledger_transactions', to='delivery.delivery')),
                ('fulfillment_request', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='ledger_transactions', to='restaurants.merchantfulfillmentrequest')),
                ('market', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='ledger_transactions', to='markets.market')),
                ('order', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='ledger_transactions', to='orders.order')),
                ('payment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='ledger_transactions', to='payments.payment')),
            ],
            options={
                'ordering': ('-created_at', '-id'),
            },
        ),
        migrations.CreateModel(
            name='LedgerEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('direction', models.CharField(choices=[('DEBIT', 'Debit'), ('CREDIT', 'Credit')], max_length=6)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=14)),
                ('currency', models.CharField(max_length=3, validators=[django.core.validators.RegexValidator(message='Currency code must be a three-letter ISO 4217 code.', regex='^[A-Z]{3}$')])),
                ('memo', models.CharField(blank=True, max_length=240)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='ledger_entries', to='ledger.ledgeraccount')),
                ('transaction', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='entries', to='ledger.ledgertransaction')),
            ],
            options={
                'ordering': ('transaction_id', 'id'),
            },
        ),
        migrations.AddIndex(
            model_name='ledgeraccount',
            index=models.Index(fields=['market', 'currency', 'account_type'], name='ledger_ledg_market__da28f9_idx'),
        ),
        migrations.AddIndex(
            model_name='ledgeraccount',
            index=models.Index(fields=['provider_code', 'external_reference'], name='ledger_ledg_provide_642076_idx'),
        ),
        migrations.AddIndex(
            model_name='ledgertransaction',
            index=models.Index(fields=['market', 'currency', 'transaction_type'], name='ledger_ledg_market__0bb7ee_idx'),
        ),
        migrations.AddIndex(
            model_name='ledgertransaction',
            index=models.Index(fields=['provider_code', 'transaction_type'], name='ledger_ledg_provide_41d42c_idx'),
        ),
        migrations.AddIndex(
            model_name='ledgertransaction',
            index=models.Index(fields=['source_type', 'source_id'], name='ledger_ledg_source__445fb5_idx'),
        ),
        migrations.AddIndex(
            model_name='ledgertransaction',
            index=models.Index(fields=['order', 'transaction_type'], name='ledger_ledg_order_i_63724d_idx'),
        ),
        migrations.AddIndex(
            model_name='ledgerentry',
            index=models.Index(fields=['transaction', 'direction'], name='ledger_ledg_transac_dbf3b7_idx'),
        ),
        migrations.AddIndex(
            model_name='ledgerentry',
            index=models.Index(fields=['account', 'currency'], name='ledger_ledg_account_561d5a_idx'),
        ),
    ]

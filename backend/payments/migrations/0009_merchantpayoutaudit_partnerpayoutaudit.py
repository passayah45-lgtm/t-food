import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('delivery', '0012_merchantriderinvite_home_restaurant'),
        ('markets', '0004_backfill_gis_points'),
        ('payments', '0008_refundaudit'),
        ('restaurants', '0017_merchantfulfillmentrequestevent_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MerchantPayoutAudit',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=14)),
                ('currency', models.CharField(max_length=3)),
                ('country_code', models.CharField(max_length=2)),
                ('status', models.CharField(choices=[('AVAILABLE', 'Available'), ('PAID', 'Paid'), ('FAILED', 'Failed'), ('REVERSED', 'Reversed')], max_length=20)),
                ('paid_at', models.DateTimeField(blank=True, null=True)),
                ('idempotency_key', models.CharField(max_length=160, unique=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ledger_transaction', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='merchant_payout_audits', to='ledger.ledgertransaction')),
                ('marked_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='marked_merchant_payout_audits', to=settings.AUTH_USER_MODEL)),
                ('market', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='merchant_payout_audits', to='markets.market')),
                ('merchant', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='payout_audits', to='restaurants.merchantprofile')),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='merchant_payout_audits', to='orders.order')),
            ],
            options={
                'ordering': ('-created_at', '-id'),
                'indexes': [
                    models.Index(fields=['merchant', 'status'], name='payments_me_merchan_e3ebc0_idx'),
                    models.Index(fields=['order', 'status'], name='payments_me_order_i_0876d9_idx'),
                    models.Index(fields=['market', 'status'], name='payments_me_market__ab9a6d_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='PartnerPayoutAudit',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=14)),
                ('currency', models.CharField(max_length=3)),
                ('country_code', models.CharField(max_length=2)),
                ('status', models.CharField(choices=[('AVAILABLE', 'Available'), ('PAID', 'Paid'), ('FAILED', 'Failed'), ('REVERSED', 'Reversed')], max_length=20)),
                ('paid_at', models.DateTimeField(blank=True, null=True)),
                ('idempotency_key', models.CharField(max_length=160, unique=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('delivery', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='partner_payout_audits', to='delivery.delivery')),
                ('ledger_transaction', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='partner_payout_audits', to='ledger.ledgertransaction')),
                ('marked_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='marked_partner_payout_audits', to=settings.AUTH_USER_MODEL)),
                ('market', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='partner_payout_audits', to='markets.market')),
                ('partner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='payout_audits', to='delivery.deliverypartner')),
            ],
            options={
                'ordering': ('-created_at', '-id'),
                'indexes': [
                    models.Index(fields=['partner', 'status'], name='payments_pa_partner_0390cf_idx'),
                    models.Index(fields=['delivery', 'status'], name='payments_pa_deliver_b2f971_idx'),
                    models.Index(fields=['market', 'status'], name='payments_pa_market__39c3a2_idx'),
                ],
            },
        ),
    ]

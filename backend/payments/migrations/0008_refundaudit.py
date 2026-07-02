import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ledger', '0001_initial'),
        ('orders', '0020_order_delivery_point'),
        ('payments', '0007_payment_market_paymentwebhookevent_market'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RefundAudit',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=14)),
                ('currency', models.CharField(max_length=3)),
                ('reason', models.TextField(blank=True)),
                ('provider_code', models.CharField(max_length=40)),
                ('provider_refund_id', models.CharField(blank=True, max_length=120, null=True)),
                ('status', models.CharField(choices=[('REQUESTED', 'Requested'), ('APPROVED', 'Approved'), ('PROCESSING', 'Processing'), ('SUCCEEDED', 'Succeeded'), ('FAILED', 'Failed'), ('CANCELLED', 'Cancelled')], default='REQUESTED', max_length=20)),
                ('idempotency_key', models.CharField(max_length=160, unique=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('initiated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='initiated_refund_audits', to=settings.AUTH_USER_MODEL)),
                ('ledger_transaction', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='refund_audits', to='ledger.ledgertransaction')),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='refund_audits', to='orders.order')),
                ('payment', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='refund_audits', to='payments.payment')),
                ('support_ticket', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='refund_audits', to='orders.supportticket')),
            ],
            options={
                'ordering': ('-created_at', '-id'),
                'indexes': [
                    models.Index(fields=['order', 'status'], name='payments_re_order_i_0fc69a_idx'),
                    models.Index(fields=['payment', 'status'], name='payments_re_payment_b35422_idx'),
                    models.Index(fields=['provider_code', 'status'], name='payments_re_provide_f5c532_idx'),
                ],
            },
        ),
    ]

import django.db.models.deletion
from django.db import migrations, models


def backfill_market(apps, schema_editor):
    Market = apps.get_model('markets', 'Market')
    Payment = apps.get_model('payments', 'Payment')
    PaymentWebhookEvent = apps.get_model('payments', 'PaymentWebhookEvent')
    market = Market.objects.get(slug='india')
    Payment.objects.filter(market__isnull=True).update(market=market)
    PaymentWebhookEvent.objects.filter(market__isnull=True).update(market=market)


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0002_seed_india_market'),
        ('payments', '0006_paymentwebhookevent'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='market',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='payments', to='markets.market'),
        ),
        migrations.AddField(
            model_name='paymentwebhookevent',
            name='market',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='payment_webhook_events', to='markets.market'),
        ),
        migrations.RunPython(backfill_market, migrations.RunPython.noop),
    ]


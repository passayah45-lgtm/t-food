import django.db.models.deletion
from django.db import migrations, models


def backfill_market(apps, schema_editor):
    Market = apps.get_model('markets', 'Market')
    Offer = apps.get_model('orders', 'Offer')
    Order = apps.get_model('orders', 'Order')
    market = Market.objects.get(slug='india')
    Offer.objects.filter(market__isnull=True).update(market=market)
    Order.objects.filter(market__isnull=True).update(market=market)


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0002_seed_india_market'),
        ('orders', '0018_order_item_customizations'),
    ]

    operations = [
        migrations.AddField(
            model_name='offer',
            name='market',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='offers', to='markets.market'),
        ),
        migrations.AddField(
            model_name='order',
            name='market',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='orders', to='markets.market'),
        ),
        migrations.RunPython(backfill_market, migrations.RunPython.noop),
    ]


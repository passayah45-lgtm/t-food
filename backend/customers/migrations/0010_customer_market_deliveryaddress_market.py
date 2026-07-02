import django.db.models.deletion
from django.db import migrations, models


def backfill_market(apps, schema_editor):
    Market = apps.get_model('markets', 'Market')
    Customer = apps.get_model('customers', 'Customer')
    DeliveryAddress = apps.get_model('customers', 'DeliveryAddress')
    market = Market.objects.get(slug='india')
    Customer.objects.filter(market__isnull=True).update(market=market)
    DeliveryAddress.objects.filter(market__isnull=True).update(market=market)


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0002_seed_india_market'),
        ('customers', '0009_deliveryaddress'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='market',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='customers', to='markets.market'),
        ),
        migrations.AddField(
            model_name='deliveryaddress',
            name='market',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='delivery_addresses', to='markets.market'),
        ),
        migrations.RunPython(backfill_market, migrations.RunPython.noop),
    ]


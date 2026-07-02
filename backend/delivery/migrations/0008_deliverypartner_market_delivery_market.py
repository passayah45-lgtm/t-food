import django.db.models.deletion
from django.db import migrations, models


def backfill_market(apps, schema_editor):
    Market = apps.get_model('markets', 'Market')
    DeliveryPartner = apps.get_model('delivery', 'DeliveryPartner')
    Delivery = apps.get_model('delivery', 'Delivery')
    market = Market.objects.get(slug='india')
    DeliveryPartner.objects.filter(market__isnull=True).update(market=market)
    Delivery.objects.filter(market__isnull=True).update(market=market)


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0002_seed_india_market'),
        ('delivery', '0007_delivery_confirmation_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='deliverypartner',
            name='market',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='delivery_partners', to='markets.market'),
        ),
        migrations.AddField(
            model_name='delivery',
            name='market',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='deliveries', to='markets.market'),
        ),
        migrations.RunPython(backfill_market, migrations.RunPython.noop),
    ]


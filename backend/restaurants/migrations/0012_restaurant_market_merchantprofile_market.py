import django.db.models.deletion
from django.db import migrations, models


def backfill_market(apps, schema_editor):
    Market = apps.get_model('markets', 'Market')
    Restaurant = apps.get_model('restaurants', 'Restaurant')
    MerchantProfile = apps.get_model('restaurants', 'MerchantProfile')
    market = Market.objects.get(slug='india')
    Restaurant.objects.filter(market__isnull=True).update(market=market)
    MerchantProfile.objects.filter(market__isnull=True).update(market=market)


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0002_seed_india_market'),
        ('restaurants', '0011_food_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='restaurant',
            name='market',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='restaurants', to='markets.market'),
        ),
        migrations.AddField(
            model_name='merchantprofile',
            name='market',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='merchant_profiles', to='markets.market'),
        ),
        migrations.RunPython(backfill_market, migrations.RunPython.noop),
    ]


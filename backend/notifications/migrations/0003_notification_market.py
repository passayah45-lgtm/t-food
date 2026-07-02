import django.db.models.deletion
from django.db import migrations, models


def backfill_market(apps, schema_editor):
    Market = apps.get_model('markets', 'Market')
    Notification = apps.get_model('notifications', 'Notification')
    market = Market.objects.get(slug='india')
    Notification.objects.filter(market__isnull=True).update(market=market)


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0002_seed_india_market'),
        ('notifications', '0002_rename_notification_unread_index'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='market',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='notifications', to='markets.market'),
        ),
        migrations.RunPython(backfill_market, migrations.RunPython.noop),
    ]


from django.db import migrations, models


def backfill_base_prices(apps, schema_editor):
    OrderItem = apps.get_model('orders', 'OrderItem')
    for item in OrderItem.objects.only('id', 'price').iterator():
        OrderItem.objects.filter(id=item.id).update(base_price=item.price)


class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0017_offer_usage_limits'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderitem',
            name='base_price',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=8),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='selected_options',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(backfill_base_prices, migrations.RunPython.noop),
    ]

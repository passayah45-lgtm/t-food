from django.db import migrations, models
import django.db.models.deletion


def backfill_pickup_branch(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    OrderItem = apps.get_model('orders', 'OrderItem')

    orders = Order.objects.filter(pickup_branch__isnull=True).only('id').iterator()
    for order in orders:
        first_item = (
            OrderItem.objects
            .filter(order_id=order.id, food__restaurant__isnull=False)
            .select_related('food__restaurant')
            .order_by('id')
            .first()
        )
        if first_item and first_item.food.restaurant_id:
            Order.objects.filter(id=order.id, pickup_branch__isnull=True).update(
                pickup_branch_id=first_item.food.restaurant_id
            )


class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0020_order_delivery_point'),
        ('restaurants', '0018_branch_foundation'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='pickup_branch',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='branch_orders',
                to='restaurants.restaurant',
            ),
        ),
        migrations.RunPython(backfill_pickup_branch, migrations.RunPython.noop),
    ]

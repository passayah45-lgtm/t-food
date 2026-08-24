import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.db import migrations
from django.db.models import Max, Q
from django.utils import timezone


def _branch_order_prefix(branch):
    source = getattr(branch, 'branch_name', '') or getattr(branch, 'rest_name', '') or 'TFOO'
    cleaned = re.sub(r'[^A-Za-z0-9]', '', source).upper()
    return (cleaned or 'TFOO')[:4]


def _branch_local_date(order, branch):
    timezone_name = getattr(getattr(branch, 'market', None), 'timezone', '') or settings.TIME_ZONE
    try:
        tzinfo = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        tzinfo = ZoneInfo(settings.TIME_ZONE)
    return timezone.localtime(order.created_at, tzinfo).date()


def backfill_merchant_order_codes(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    OrderItem = apps.get_model('orders', 'OrderItem')

    missing_branch_orders = Order.objects.filter(pickup_branch__isnull=True).only('id').iterator()
    for order in missing_branch_orders:
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

    next_sequences = {}
    orders = (
        Order.objects
        .filter(Q(merchant_order_code='') | Q(merchant_order_code__isnull=True))
        .exclude(pickup_branch__isnull=True)
        .select_related('pickup_branch', 'pickup_branch__market')
        .order_by('created_at', 'id')
    )
    for order in orders:
        branch = order.pickup_branch
        sequence_date = _branch_local_date(order, branch)
        key = (branch.id, sequence_date)
        if key not in next_sequences:
            next_sequences[key] = (
                Order.objects.filter(
                    pickup_branch_id=branch.id,
                    merchant_sequence_date=sequence_date,
                )
                .exclude(id=order.id)
                .aggregate(value=Max('merchant_daily_sequence'))['value']
                or 0
            )
        next_sequences[key] += 1
        daily_sequence = next_sequences[key]
        Order.objects.filter(id=order.id).update(
            merchant_sequence_date=sequence_date,
            merchant_daily_sequence=daily_sequence,
            merchant_order_code=(
                f'{_branch_order_prefix(branch)}-{branch.id}-{sequence_date:%Y%m%d}-{daily_sequence:03d}'
            ),
        )


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0022_order_merchant_daily_code'),
    ]

    operations = [
        migrations.RunPython(backfill_merchant_order_codes, migrations.RunPython.noop),
    ]

from django.db import migrations, models
from secrets import randbelow


def backfill_active_confirmation_codes(apps, schema_editor):
    Delivery = apps.get_model('delivery', 'Delivery')
    for delivery in Delivery.objects.filter(
        delivery_partner__isnull=False
    ).exclude(status='DELIVERED').iterator():
        delivery.confirmation_code = f'{randbelow(1000000):06d}'
        delivery.save(update_fields=['confirmation_code'])


class Migration(migrations.Migration):
    dependencies = [
        ('delivery', '0006_delivery_partner_payout'),
    ]

    operations = [
        migrations.AddField(
            model_name='delivery',
            name='confirmation_code',
            field=models.CharField(blank=True, max_length=6),
        ),
        migrations.AddField(
            model_name='delivery',
            name='confirmation_verified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(
            backfill_active_confirmation_codes,
            migrations.RunPython.noop,
        ),
    ]

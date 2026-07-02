from django.db import migrations


def seed_india_market(apps, schema_editor):
    Currency = apps.get_model('markets', 'Currency')
    Market = apps.get_model('markets', 'Market')

    inr, _ = Currency.objects.update_or_create(
        code='INR',
        defaults={
            'numeric_code': '356',
            'name': 'Indian Rupee',
            'symbol': 'Rs.',
            'minor_unit': 2,
            'is_active': True,
        },
    )
    Market.objects.update_or_create(
        slug='india',
        defaults={
            'name': 'India',
            'country_code': 'IN',
            'default_currency': inr,
            'timezone': 'Asia/Kolkata',
            'phone_country_code': '+91',
            'is_active': True,
        },
    )


def unseed_india_market(apps, schema_editor):
    Market = apps.get_model('markets', 'Market')
    Currency = apps.get_model('markets', 'Currency')
    Market.objects.filter(slug='india').delete()
    Currency.objects.filter(code='INR').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_india_market, unseed_india_market),
    ]


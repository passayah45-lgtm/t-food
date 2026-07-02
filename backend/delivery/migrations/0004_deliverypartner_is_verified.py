from django.db import migrations, models


def verify_existing_partners(apps, schema_editor):
    DeliveryPartner = apps.get_model('delivery', 'DeliveryPartner')
    DeliveryPartner.objects.update(is_verified=True)


class Migration(migrations.Migration):
    dependencies = [
        ('delivery', '0003_delivery_current_latitude_delivery_current_longitude'),
    ]

    operations = [
        migrations.AddField(
            model_name='deliverypartner',
            name='is_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(verify_existing_partners, migrations.RunPython.noop),
    ]

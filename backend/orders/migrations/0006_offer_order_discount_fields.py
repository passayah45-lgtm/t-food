from django.db import migrations, models
import django.db.models.deletion


def create_welcome_offer(apps, schema_editor):
    Offer = apps.get_model('orders', 'Offer')
    Offer.objects.get_or_create(
        code='WELCOME10',
        defaults={
            'discount_percent': 10,
            'min_order_amount': 100,
            'is_active': True,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0005_order_delivery_address_order_contact_phone'),
    ]

    operations = [
        migrations.CreateModel(
            name='Offer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=30, unique=True)),
                ('discount_percent', models.PositiveSmallIntegerField()),
                ('min_order_amount', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('is_active', models.BooleanField(default=True)),
                ('valid_until', models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.AddField(
            model_name='order',
            name='discount_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='order',
            name='loyalty_points_awarded',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='order',
            name='offer',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='orders',
                to='orders.offer',
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='subtotal_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.RunPython(create_welcome_offer, migrations.RunPython.noop),
    ]

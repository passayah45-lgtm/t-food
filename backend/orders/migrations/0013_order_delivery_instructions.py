from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0012_order_client_order_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='delivery_instructions',
            field=models.CharField(blank=True, max_length=300),
        ),
    ]

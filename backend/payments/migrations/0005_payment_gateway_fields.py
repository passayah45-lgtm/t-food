from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('payments', '0004_alter_payment_status_cancelled'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='provider',
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name='payment',
            name='provider_order_id',
            field=models.CharField(blank=True, max_length=100, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='payment',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]

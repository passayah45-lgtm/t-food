from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('payments', '0005_payment_gateway_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentWebhookEvent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_id', models.CharField(max_length=100, unique=True)),
                ('event_type', models.CharField(max_length=100)),
                ('payload_hash', models.CharField(max_length=64)),
                ('processed', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={'ordering': ('-created_at',)},
        ),
    ]

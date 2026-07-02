from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('customers', '0008_favoriterestaurant'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DeliveryAddress',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(choices=[('HOME', 'Home'), ('WORK', 'Work'), ('OTHER', 'Other')], default='HOME', max_length=10)),
                ('recipient_name', models.CharField(max_length=100)),
                ('phone', models.CharField(max_length=15)),
                ('address', models.TextField(max_length=500)),
                ('instructions', models.CharField(blank=True, max_length=300)),
                ('latitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('longitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('is_default', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='delivery_addresses', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ('-is_default', '-updated_at')},
        ),
        migrations.AddConstraint(
            model_name='deliveryaddress',
            constraint=models.UniqueConstraint(condition=models.Q(is_default=True), fields=('user',), name='one_default_delivery_address_per_user'),
        ),
    ]

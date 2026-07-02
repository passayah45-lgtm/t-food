from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('orders', '0009_order_marketplace_financials'),
    ]

    operations = [
        migrations.CreateModel(
            name='SupportTicket',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(choices=[('MISSING_ITEMS', 'Missing items'), ('QUALITY', 'Food quality'), ('DELIVERY', 'Delivery issue'), ('PAYMENT', 'Payment issue'), ('OTHER', 'Other')], max_length=20)),
                ('description', models.TextField(max_length=2000)),
                ('status', models.CharField(choices=[('OPEN', 'Open'), ('IN_REVIEW', 'In review'), ('RESOLVED', 'Resolved'), ('REJECTED', 'Rejected')], default='OPEN', max_length=20)),
                ('refund_status', models.CharField(choices=[('NONE', 'Not requested'), ('REQUESTED', 'Requested'), ('APPROVED', 'Approved'), ('REJECTED', 'Rejected')], default='NONE', max_length=20)),
                ('refunded_amount', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('resolution', models.TextField(blank=True, max_length=2000)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='support_tickets', to=settings.AUTH_USER_MODEL)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='support_tickets', to='orders.order')),
            ],
            options={'ordering': ('-created_at',)},
        ),
        migrations.AddIndex(
            model_name='supportticket',
            index=models.Index(fields=['status', '-created_at'], name='orders_supp_status_03086d_idx'),
        ),
    ]

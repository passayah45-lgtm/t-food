from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('orders', '0020_order_delivery_point'),
        ('restaurants', '0015_merchantnetworkrelationship'),
    ]

    operations = [
        migrations.CreateModel(
            name='MerchantFulfillmentRequest',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('REQUESTED', 'Requested'),
                            ('ACCEPTED', 'Accepted'),
                            ('REJECTED', 'Rejected'),
                            ('CANCELLED', 'Cancelled'),
                        ],
                        default='REQUESTED',
                        max_length=20,
                    ),
                ),
                ('notes', models.TextField(blank=True)),
                ('requested_at', models.DateTimeField(auto_now_add=True)),
                ('responded_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'fulfilling_merchant',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='incoming_fulfillment_requests',
                        to='restaurants.merchantprofile',
                    ),
                ),
                (
                    'order',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='merchant_fulfillment_requests',
                        to='orders.order',
                    ),
                ),
                (
                    'relationship',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='fulfillment_requests',
                        to='restaurants.merchantnetworkrelationship',
                    ),
                ),
                (
                    'requested_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='requested_merchant_fulfillment_requests',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'requesting_merchant',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='outgoing_fulfillment_requests',
                        to='restaurants.merchantprofile',
                    ),
                ),
                (
                    'responded_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='responded_merchant_fulfillment_requests',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'ordering': ('-created_at', '-id'),
                'indexes': [
                    models.Index(
                        fields=['order', 'status'],
                        name='restaurants_order_i_2e4cf9_idx',
                    ),
                    models.Index(
                        fields=['requesting_merchant', 'status'],
                        name='restaurants_request_9f8ffe_idx',
                    ),
                    models.Index(
                        fields=['fulfilling_merchant', 'status'],
                        name='restaurants_fulfill_07c111_idx',
                    ),
                ],
            },
        ),
    ]

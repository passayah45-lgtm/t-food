from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('restaurants', '0014_restaurant_pickup_point'),
    ]

    operations = [
        migrations.CreateModel(
            name='MerchantNetworkRelationship',
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
                            ('ACTIVE', 'Active'),
                            ('PAUSED', 'Paused'),
                            ('BLOCKED', 'Blocked'),
                        ],
                        default='REQUESTED',
                        max_length=20,
                    ),
                ),
                ('requested_at', models.DateTimeField(auto_now_add=True)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('notes', models.TextField(blank=True)),
                (
                    'distance_km',
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=7,
                        null=True,
                    ),
                ),
                (
                    'approved_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='approved_merchant_network_relationships',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'from_merchant',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='outgoing_network_relationships',
                        to='restaurants.merchantprofile',
                    ),
                ),
                (
                    'requested_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='requested_merchant_network_relationships',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'to_merchant',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='incoming_network_relationships',
                        to='restaurants.merchantprofile',
                    ),
                ),
            ],
            options={
                'ordering': ('-requested_at', '-id'),
                'indexes': [
                    models.Index(
                        fields=['from_merchant', 'status'],
                        name='restaurants_from_me_d72f54_idx',
                    ),
                    models.Index(
                        fields=['to_merchant', 'status'],
                        name='restaurants_to_merc_786011_idx',
                    ),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name='merchantnetworkrelationship',
            constraint=models.UniqueConstraint(
                fields=('from_merchant', 'to_merchant'),
                name='unique_directional_merchant_network_relationship',
            ),
        ),
        migrations.AddConstraint(
            model_name='merchantnetworkrelationship',
            constraint=models.CheckConstraint(
                check=~models.Q(('from_merchant', models.F('to_merchant'))),
                name='merchant_network_no_self_relationship',
            ),
        ),
    ]

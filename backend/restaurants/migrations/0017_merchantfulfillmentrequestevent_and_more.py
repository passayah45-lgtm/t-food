from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('restaurants', '0016_merchantfulfillmentrequest'),
    ]

    operations = [
        migrations.AddField(
            model_name='merchantfulfillmentrequest',
            name='blocked_reason',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='merchantfulfillmentrequest',
            name='cancelled_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='merchantfulfillmentrequest',
            name='cancelled_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='cancelled_merchant_fulfillment_requests',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='merchantfulfillmentrequest',
            name='internal_status',
            field=models.CharField(
                choices=[
                    ('PENDING', 'Pending'),
                    ('ACCEPTED', 'Accepted'),
                    ('IN_PROGRESS', 'In progress'),
                    ('READY_FOR_HANDOFF', 'Ready for handoff'),
                    ('UNABLE_TO_FULFILL', 'Unable to fulfill'),
                    ('RESOLVED', 'Resolved'),
                    ('REJECTED', 'Rejected'),
                    ('CANCELLED', 'Cancelled'),
                ],
                default='PENDING',
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name='merchantfulfillmentrequest',
            name='operations_note',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='merchantfulfillmentrequest',
            name='preparation_started_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='merchantfulfillmentrequest',
            name='ready_for_handoff_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='merchantfulfillmentrequest',
            name='resolved_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='merchantfulfillmentrequest',
            name='resolved_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='resolved_merchant_fulfillment_requests',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='merchantfulfillmentrequest',
            name='settlement_preview',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddIndex(
            model_name='merchantfulfillmentrequest',
            index=models.Index(
                fields=['internal_status', 'updated_at'],
                name='restaurants_interna_843c6a_idx',
            ),
        ),
        migrations.CreateModel(
            name='MerchantFulfillmentRequestEvent',
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
                    'event_type',
                    models.CharField(
                        choices=[
                            ('CREATED', 'Created'),
                            ('STATUS_CHANGED', 'Status changed'),
                            (
                                'INTERNAL_STATUS_CHANGED',
                                'Internal status changed',
                            ),
                            (
                                'SETTLEMENT_PREVIEWED',
                                'Settlement previewed',
                            ),
                            ('NOTE_ADDED', 'Note added'),
                        ],
                        max_length=40,
                    ),
                ),
                ('from_status', models.CharField(blank=True, max_length=40)),
                ('to_status', models.CharField(blank=True, max_length=40)),
                ('note', models.TextField(blank=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'actor',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='merchant_fulfillment_events',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'fulfillment_request',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='events',
                        to='restaurants.merchantfulfillmentrequest',
                    ),
                ),
            ],
            options={
                'ordering': ('created_at', 'id'),
            },
        ),
        migrations.AddIndex(
            model_name='merchantfulfillmentrequestevent',
            index=models.Index(
                fields=['fulfillment_request', 'created_at'],
                name='restaurants_fulfill_0dd6a3_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='merchantfulfillmentrequestevent',
            index=models.Index(
                fields=['event_type', 'created_at'],
                name='restaurants_event_t_f505a7_idx',
            ),
        ),
    ]

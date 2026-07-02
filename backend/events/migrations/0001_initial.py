# Generated manually for Sprint 1 transactional event foundation.

import django.utils.timezone
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='InboxEvent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_id', models.UUIDField()),
                ('consumer', models.CharField(max_length=100)),
                ('event_name', models.CharField(max_length=100)),
                ('event_version', models.PositiveSmallIntegerField(default=1)),
                ('payload_hash', models.CharField(max_length=64)),
                ('payload', models.JSONField(default=dict)),
                ('headers', models.JSONField(blank=True, default=dict)),
                ('status', models.CharField(choices=[('RECEIVED', 'Received'), ('PROCESSED', 'Processed'), ('FAILED', 'Failed')], default='RECEIVED', max_length=20)),
                ('attempts', models.PositiveSmallIntegerField(default=0)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
                ('last_error', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ('-created_at',),
            },
        ),
        migrations.CreateModel(
            name='OutboxEvent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('event_name', models.CharField(max_length=100)),
                ('event_version', models.PositiveSmallIntegerField(default=1)),
                ('aggregate_type', models.CharField(max_length=80)),
                ('aggregate_id', models.CharField(max_length=80)),
                ('payload', models.JSONField(default=dict)),
                ('headers', models.JSONField(blank=True, default=dict)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('PUBLISHED', 'Published'), ('FAILED', 'Failed')], default='PENDING', max_length=20)),
                ('attempts', models.PositiveSmallIntegerField(default=0)),
                ('available_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('published_at', models.DateTimeField(blank=True, null=True)),
                ('last_error', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ('created_at', 'id'),
            },
        ),
        migrations.AddIndex(
            model_name='inboxevent',
            index=models.Index(fields=['consumer', 'status', 'created_at'], name='events_inbo_consume_e9b2c5_idx'),
        ),
        migrations.AddIndex(
            model_name='inboxevent',
            index=models.Index(fields=['event_name', 'event_version'], name='events_inbo_event_n_5b149a_idx'),
        ),
        migrations.AddIndex(
            model_name='outboxevent',
            index=models.Index(fields=['status', 'available_at', 'id'], name='events_outb_status_467689_idx'),
        ),
        migrations.AddIndex(
            model_name='outboxevent',
            index=models.Index(fields=['aggregate_type', 'aggregate_id'], name='events_outb_aggrega_11f4b9_idx'),
        ),
        migrations.AddIndex(
            model_name='outboxevent',
            index=models.Index(fields=['event_name', 'event_version'], name='events_outb_event_n_a3e19b_idx'),
        ),
        migrations.AddConstraint(
            model_name='inboxevent',
            constraint=models.UniqueConstraint(fields=('event_id', 'consumer'), name='unique_inbox_event_per_consumer'),
        ),
    ]

from django.db import migrations, models
import django.db.models.deletion


def backfill_notification_compatibility(apps, schema_editor):
    Notification = apps.get_model('notifications', 'Notification')
    Notification.objects.filter(is_read=True).update(status='READ')
    Notification.objects.filter(is_read=False).update(status='UNREAD')
    for kind in ('ORDER', 'PAYMENT', 'DELIVERY'):
        Notification.objects.filter(kind=kind, category='SYSTEM').update(category=kind)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('markets', '0005_commercecity_commercearea_and_more'),
        ('notifications', '0003_notification_market'),
        ('restaurants', '0019_restaurant_timestamps'),
    ]

    operations = [
        migrations.CreateModel(
            name='NotificationDeliveryAttempt',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('channel', models.CharField(choices=[('IN_APP', 'In-app'), ('REALTIME', 'Realtime'), ('EMAIL', 'Email'), ('SMS', 'SMS'), ('PUSH', 'Push'), ('WHATSAPP', 'WhatsApp'), ('TELEGRAM', 'Telegram')], max_length=20)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('SENT', 'Sent'), ('FAILED', 'Failed'), ('SKIPPED', 'Skipped')], default='PENDING', max_length=20)),
                ('provider_code', models.CharField(blank=True, max_length=60, null=True)),
                ('error_message', models.TextField(blank=True, null=True)),
                ('attempted_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ('-created_at',),
            },
        ),
        migrations.CreateModel(
            name='NotificationTemplate',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=120)),
                ('category', models.CharField(choices=[('ORDER', 'Order'), ('PAYMENT', 'Payment'), ('DELIVERY', 'Delivery'), ('MERCHANT', 'Merchant'), ('STAFF', 'Staff'), ('RIDER', 'Rider'), ('SUPPORT', 'Support'), ('VERIFICATION', 'Verification'), ('DISPATCH', 'Dispatch'), ('INTELLIGENCE', 'Intelligence'), ('SYSTEM', 'System')], max_length=30)),
                ('event_type', models.CharField(blank=True, max_length=80)),
                ('language', models.CharField(default='en', max_length=12)),
                ('title_template', models.CharField(max_length=200)),
                ('message_template', models.TextField()),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ('code', 'language'),
            },
        ),
        migrations.AddField(
            model_name='notification',
            name='action_url',
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='notification',
            name='area',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='notifications', to='markets.commercearea'),
        ),
        migrations.AddField(
            model_name='notification',
            name='auto_archive_after',
            field=models.DurationField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='notification',
            name='branch',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='notifications', to='restaurants.restaurant'),
        ),
        migrations.AddField(
            model_name='notification',
            name='category',
            field=models.CharField(choices=[('ORDER', 'Order'), ('PAYMENT', 'Payment'), ('DELIVERY', 'Delivery'), ('MERCHANT', 'Merchant'), ('STAFF', 'Staff'), ('RIDER', 'Rider'), ('SUPPORT', 'Support'), ('VERIFICATION', 'Verification'), ('DISPATCH', 'Dispatch'), ('INTELLIGENCE', 'Intelligence'), ('SYSTEM', 'System')], default='SYSTEM', max_length=30),
        ),
        migrations.AddField(
            model_name='notification',
            name='city',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='notifications', to='markets.commercecity'),
        ),
        migrations.AddField(
            model_name='notification',
            name='country_code',
            field=models.CharField(blank=True, max_length=2, null=True),
        ),
        migrations.AddField(
            model_name='notification',
            name='event_type',
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name='notification',
            name='expires_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='notification',
            name='idempotency_key',
            field=models.CharField(blank=True, max_length=160, null=True),
        ),
        migrations.AddField(
            model_name='notification',
            name='metadata',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='notification',
            name='priority',
            field=models.CharField(choices=[('LOW', 'Low'), ('NORMAL', 'Normal'), ('HIGH', 'High'), ('CRITICAL', 'Critical')], default='NORMAL', max_length=20),
        ),
        migrations.AddField(
            model_name='notification',
            name='recipient_type',
            field=models.CharField(choices=[('CUSTOMER', 'Customer'), ('MERCHANT_OWNER', 'Merchant owner'), ('MERCHANT_STAFF', 'Merchant staff'), ('DELIVERY_PARTNER', 'Delivery partner'), ('OPERATIONS', 'Operations'), ('GLOBAL_ADMIN', 'Global admin'), ('COUNTRY_ADMIN', 'Country admin'), ('CITY_ADMIN', 'City admin'), ('AREA_ADMIN', 'Area admin'), ('SYSTEM', 'System')], default='SYSTEM', max_length=30),
        ),
        migrations.AddField(
            model_name='notification',
            name='status',
            field=models.CharField(choices=[('UNREAD', 'Unread'), ('READ', 'Read'), ('ARCHIVED', 'Archived'), ('DISMISSED', 'Dismissed')], default='UNREAD', max_length=20),
        ),
        migrations.RunPython(backfill_notification_compatibility, migrations.RunPython.noop),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['user', 'status', '-created_at'], name='notificatio_user_id_eebdc7_idx'),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['category', 'priority', '-created_at'], name='notificatio_categor_7e8f36_idx'),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['market', 'country_code', '-created_at'], name='notificatio_market__c72a03_idx'),
        ),
        migrations.AddConstraint(
            model_name='notification',
            constraint=models.UniqueConstraint(condition=models.Q(('idempotency_key__isnull', False)), fields=('idempotency_key',), name='unique_notification_idempotency_key'),
        ),
        migrations.AddField(
            model_name='notificationdeliveryattempt',
            name='notification',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='delivery_attempts', to='notifications.notification'),
        ),
        migrations.AddConstraint(
            model_name='notificationtemplate',
            constraint=models.UniqueConstraint(fields=('code', 'language'), name='unique_notification_template_code_language'),
        ),
        migrations.AddIndex(
            model_name='notificationdeliveryattempt',
            index=models.Index(fields=['channel', 'status', '-created_at'], name='notificatio_channel_1cbde2_idx'),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0021_order_pickup_branch'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='merchant_daily_sequence',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='merchant_order_code',
            field=models.CharField(blank=True, db_index=True, max_length=80),
        ),
        migrations.AddField(
            model_name='order',
            name='merchant_sequence_date',
            field=models.DateField(blank=True, db_index=True, null=True),
        ),
        migrations.AddIndex(
            model_name='order',
            index=models.Index(fields=['pickup_branch', 'merchant_sequence_date'], name='orders_orde_pickup__6f7861_idx'),
        ),
        migrations.AddConstraint(
            model_name='order',
            constraint=models.UniqueConstraint(condition=models.Q(('merchant_daily_sequence__isnull', False)), fields=('pickup_branch', 'merchant_sequence_date', 'merchant_daily_sequence'), name='unique_branch_daily_order_sequence'),
        ),
    ]

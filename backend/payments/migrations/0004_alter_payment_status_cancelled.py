from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0003_alter_payment_status_refunded'),
    ]

    operations = [
        migrations.AlterField(
            model_name='payment',
            name='status',
            field=models.CharField(
                choices=[
                    ('PENDING', 'Pending'),
                    ('SUCCESS', 'Success'),
                    ('FAILED', 'Failed'),
                    ('REFUNDED', 'Refunded'),
                    ('CANCELLED', 'Cancelled'),
                ],
                default='PENDING',
                max_length=10,
            ),
        ),
    ]

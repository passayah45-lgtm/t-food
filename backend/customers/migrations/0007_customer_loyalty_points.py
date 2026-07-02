from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0006_alter_customer_phone'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='loyalty_points',
            field=models.PositiveIntegerField(default=0),
        ),
    ]

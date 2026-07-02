from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('customers', '0003_link_customer_to_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='avatar',
            field=models.ImageField(blank=True, null=True, upload_to='avatars/'),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('restaurants', '0006_alter_restaurant_commission_percent'),
    ]

    operations = [
        migrations.AddField(
            model_name='restaurant',
            name='cover_image',
            field=models.ImageField(blank=True, null=True, upload_to='restaurants/covers/'),
        ),
        migrations.AddField(
            model_name='fooditem',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='restaurants/items/'),
        ),
    ]

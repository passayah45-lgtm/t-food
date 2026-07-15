from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_preferences', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='userpreference',
            name='avatar',
            field=models.ImageField(blank=True, null=True, upload_to='avatars/'),
        ),
    ]

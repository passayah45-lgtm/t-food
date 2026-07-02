from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('restaurants', '0018_branch_foundation'),
    ]

    operations = [
        migrations.AddField(
            model_name='restaurant',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name='restaurant',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, null=True),
        ),
    ]

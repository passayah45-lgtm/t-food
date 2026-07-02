from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('markets', '0005_commercecity_commercearea_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserPreference',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('language', models.CharField(choices=[('en', 'English'), ('fr', 'French'), ('ar', 'Arabic'), ('hi', 'Hindi'), ('es', 'Spanish'), ('pt', 'Portuguese'), ('zh', 'Chinese'), ('de', 'German'), ('ru', 'Russian'), ('ja', 'Japanese'), ('ko', 'Korean')], default='en', max_length=12)),
                ('preferred_country', models.CharField(blank=True, max_length=2)),
                ('theme', models.CharField(choices=[('LIGHT', 'Light'), ('DARK', 'Dark'), ('SYSTEM', 'System')], default='SYSTEM', max_length=12)),
                ('accent_color', models.CharField(choices=[('ORANGE', 'Orange'), ('BLUE', 'Blue'), ('GREEN', 'Green'), ('PURPLE', 'Purple'), ('RED', 'Red'), ('PINK', 'Pink'), ('TEAL', 'Teal')], default='ORANGE', max_length=20)),
                ('timezone', models.CharField(blank=True, max_length=64)),
                ('date_format', models.CharField(choices=[('AUTO', 'Automatic'), ('DD_MM_YYYY', 'DD/MM/YYYY'), ('MM_DD_YYYY', 'MM/DD/YYYY'), ('YYYY_MM_DD', 'YYYY-MM-DD')], default='AUTO', max_length=20)),
                ('time_format', models.CharField(choices=[('AUTO', 'Automatic'), ('H_12', '12-hour'), ('H_24', '24-hour')], default='AUTO', max_length=12)),
                ('number_format', models.CharField(choices=[('AUTO', 'Automatic'), ('EN', 'English'), ('FR', 'French'), ('HI', 'Hindi'), ('AR', 'Arabic')], default='AUTO', max_length=12)),
                ('currency_display', models.CharField(choices=[('SYMBOL', 'Symbol'), ('CODE', 'Code'), ('NAME', 'Name')], default='SYMBOL', max_length=12)),
                ('large_text', models.BooleanField(default=False)),
                ('high_contrast', models.BooleanField(default=False)),
                ('reduced_motion', models.BooleanField(default=False)),
                ('keyboard_focus_enhanced', models.BooleanField(default=False)),
                ('preference_version', models.PositiveIntegerField(default=1)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('preferred_currency', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='user_preferences', to='markets.currency')),
                ('preferred_market', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='user_preferences', to='markets.market')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='preference_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('user__username', 'id'),
            },
        ),
        migrations.AddIndex(
            model_name='userpreference',
            index=models.Index(fields=['language'], name='user_pref_language_idx'),
        ),
        migrations.AddIndex(
            model_name='userpreference',
            index=models.Index(fields=['theme', 'accent_color'], name='user_pref_theme_accent_idx'),
        ),
        migrations.AddIndex(
            model_name='userpreference',
            index=models.Index(fields=['preferred_country'], name='user_pref_country_idx'),
        ),
    ]

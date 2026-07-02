from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('restaurants', '0009_restaurant_serviceability'),
    ]

    operations = [
        migrations.CreateModel(
            name='RestaurantOperatingHour',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day_of_week', models.PositiveSmallIntegerField(choices=[(0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')])),
                ('is_closed', models.BooleanField(default=False)),
                ('opens_at', models.TimeField(default='09:00')),
                ('closes_at', models.TimeField(default='22:00')),
                ('restaurant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='operating_hours', to='restaurants.restaurant')),
            ],
            options={'ordering': ('day_of_week',)},
        ),
        migrations.AddConstraint(
            model_name='restaurantoperatinghour',
            constraint=models.UniqueConstraint(fields=('restaurant', 'day_of_week'), name='unique_restaurant_operating_day'),
        ),
    ]

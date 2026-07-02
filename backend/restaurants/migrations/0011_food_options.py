from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('restaurants', '0010_restaurantoperatinghour'),
    ]

    operations = [
        migrations.CreateModel(
            name='FoodOptionGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=80)),
                ('min_select', models.PositiveSmallIntegerField(default=0)),
                ('max_select', models.PositiveSmallIntegerField(default=1)),
                ('ordering', models.PositiveSmallIntegerField(default=0)),
                ('food', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='option_groups', to='restaurants.fooditem')),
            ],
            options={'ordering': ('ordering', 'id')},
        ),
        migrations.CreateModel(
            name='FoodOption',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=80)),
                ('price_delta', models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('is_available', models.BooleanField(default=True)),
                ('ordering', models.PositiveSmallIntegerField(default=0)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='options', to='restaurants.foodoptiongroup')),
            ],
            options={'ordering': ('ordering', 'id')},
        ),
    ]

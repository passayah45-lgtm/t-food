from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import markets.models


def backfill_branch_identity(apps, schema_editor):
    Restaurant = apps.get_model('restaurants', 'Restaurant')
    for restaurant in Restaurant.objects.select_related('market').iterator():
        updates = []
        if not restaurant.branch_name:
            restaurant.branch_name = restaurant.rest_name
            updates.append('branch_name')
        if not restaurant.country_code and restaurant.market_id:
            restaurant.country_code = restaurant.market.country_code
            updates.append('country_code')
        if updates:
            restaurant.save(update_fields=updates)


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('markets', '0005_commercecity_commercearea_and_more'),
        ('restaurants', '0017_merchantfulfillmentrequestevent_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='restaurant',
            name='branch_code',
            field=models.CharField(blank=True, max_length=40, null=True),
        ),
        migrations.AddField(
            model_name='restaurant',
            name='branch_name',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='restaurant',
            name='branch_type',
            field=models.CharField(
                choices=[
                    ('FOOD', 'Food'),
                    ('GROCERY', 'Grocery'),
                    ('PHARMACY', 'Pharmacy'),
                    ('RETAIL', 'Retail'),
                    ('COURIER', 'Courier'),
                    ('LOCAL_COMMERCE', 'Local commerce'),
                ],
                default='FOOD',
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name='restaurant',
            name='country_code',
            field=models.CharField(
                blank=True,
                max_length=2,
                validators=[markets.models.country_code_validator],
            ),
        ),
        migrations.AddField(
            model_name='restaurant',
            name='area_ref',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='branches',
                to='markets.commercearea',
            ),
        ),
        migrations.AddField(
            model_name='restaurant',
            name='branch_manager',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='managed_branches',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='restaurant',
            name='city_ref',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='branches',
                to='markets.commercecity',
            ),
        ),
        migrations.RunPython(
            backfill_branch_identity,
            migrations.RunPython.noop,
        ),
    ]

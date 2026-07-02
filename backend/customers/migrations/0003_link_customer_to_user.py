from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import migrations, models
import django.db.models.deletion


def create_users_for_legacy_customers(apps, schema_editor):
    Customer = apps.get_model('customers', 'Customer')
    User = apps.get_model('auth', 'User')

    for customer in Customer.objects.all():
        email = getattr(customer, 'cust_email', '') or ''
        full_name = (getattr(customer, 'cust_name', '') or '').strip()
        first_name, _, last_name = full_name.partition(' ')
        base_username = (email.split('@')[0] if email else f'customer{customer.pk}') or f'customer{customer.pk}'
        username = base_username[:150]
        suffix = 1

        while User.objects.filter(username=username).exists():
            tail = f'{suffix}'
            username = f'{base_username[:150 - len(tail)]}{tail}'
            suffix += 1

        user = User.objects.create(
            username=username,
            email=email,
            first_name=first_name[:150],
            last_name=last_name[:150],
            is_active=True,
        )
        user.password = make_password(None)
        user.save(update_fields=['password'])
        customer.user_id = user.pk
        customer.save(update_fields=['user'])


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0002_alter_customer_id'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='user',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='customer_profile',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RenameField(
            model_name='customer',
            old_name='cust_phone',
            new_name='phone',
        ),
        migrations.RenameField(
            model_name='customer',
            old_name='cust_address',
            new_name='address',
        ),
        migrations.RunPython(create_users_for_legacy_customers, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='customer',
            name='cust_name',
        ),
        migrations.RemoveField(
            model_name='customer',
            name='cust_email',
        ),
        migrations.AlterField(
            model_name='customer',
            name='user',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='customer_profile',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]

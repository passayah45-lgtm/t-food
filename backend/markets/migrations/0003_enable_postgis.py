from django.db import migrations


def enable_postgis(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute('CREATE EXTENSION IF NOT EXISTS postgis')


class Migration(migrations.Migration):
    dependencies = [
        ('markets', '0002_seed_india_market'),
    ]

    operations = [
        migrations.RunPython(enable_postgis, migrations.RunPython.noop),
    ]

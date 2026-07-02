from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('restaurants', '0012_restaurant_market_merchantprofile_market'),
        ('verifications', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='merchantprofile',
            name='verification_rejection_reason',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='merchantprofile',
            name='verification_reviewed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='merchantprofile',
            name='verification_reviewed_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_merchant_profiles', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='merchantprofile',
            name='verification_status',
            field=models.CharField(choices=[('PENDING', 'Pending documents'), ('SUBMITTED', 'Submitted for review'), ('APPROVED', 'Approved'), ('REJECTED', 'Rejected'), ('SUSPENDED', 'Suspended')], default='PENDING', max_length=20),
        ),
        migrations.AddField(
            model_name='merchantprofile',
            name='verification_submitted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

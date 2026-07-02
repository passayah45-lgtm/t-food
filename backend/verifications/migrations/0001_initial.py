from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import verifications.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='VerificationDocument',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subject_type', models.CharField(choices=[('MERCHANT', 'Merchant'), ('PARTNER', 'Delivery partner')], max_length=20)),
                ('document_type', models.CharField(choices=[('BUSINESS_DOCUMENT', 'Business document'), ('DRIVING_LICENSE', 'Driving license'), ('NATIONAL_ID', 'National ID'), ('OWNER_PROFILE_PHOTO', 'Owner profile photo'), ('PARTNER_PROFILE_PHOTO', 'Partner profile photo'), ('PASSPORT', 'Passport'), ('RESTAURANT_PHOTO', 'Restaurant photo'), ('VEHICLE_DOCUMENT', 'Vehicle document'), ('VOTER_CARD', 'Voter card')], max_length=40)),
                ('file', models.FileField(upload_to=verifications.models.verification_upload_path)),
                ('status', models.CharField(choices=[('PENDING', 'Pending review'), ('APPROVED', 'Approved'), ('REJECTED', 'Rejected')], default='PENDING', max_length=20)),
                ('notes', models.TextField(blank=True)),
                ('rejection_reason', models.TextField(blank=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_verification_documents', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='verification_documents', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-created_at',),
            },
        ),
        migrations.AddIndex(
            model_name='verificationdocument',
            index=models.Index(fields=['subject_type', 'status'], name='verificatio_subject_8e4bac_idx'),
        ),
        migrations.AddIndex(
            model_name='verificationdocument',
            index=models.Index(fields=['user', 'subject_type'], name='verificatio_user_id_2f455b_idx'),
        ),
    ]

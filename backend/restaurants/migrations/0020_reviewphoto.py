# Generated for Visual Product Search and Review Photos Slice 5.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('restaurants', '0019_restaurant_timestamps'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ReviewPhoto',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('image', models.ImageField(upload_to='reviews/photos/')),
                ('caption', models.CharField(blank=True, max_length=240)),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('PENDING', 'Pending'),
                            ('APPROVED', 'Approved'),
                            ('REJECTED', 'Rejected'),
                            ('HIDDEN', 'Hidden'),
                        ],
                        default='PENDING',
                        max_length=20,
                    ),
                ),
                ('moderation_reason', models.TextField(blank=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'review',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='photos',
                        to='restaurants.restaurantreview',
                    ),
                ),
                (
                    'reviewed_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='reviewed_review_photos',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'uploaded_by',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='review_photos',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'ordering': ('-created_at', '-id'),
                'indexes': [
                    models.Index(fields=['review', 'status'], name='restaurants_review__cbdfff_idx'),
                    models.Index(fields=['uploaded_by', '-created_at'], name='restaurants_uploade_f1c912_idx'),
                    models.Index(fields=['status', '-created_at'], name='restaurants_status_b4b7df_idx'),
                ],
            },
        ),
    ]

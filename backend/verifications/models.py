from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from fooddelivery.media_storage import attach_private_upload, safe_media_name
from fooddelivery.upload_validation import prepare_private_document_upload

from .constants import (
    ALL_DOCUMENT_TYPES,
    DOCUMENT_STATUS_CHOICES,
    STATUS_PENDING,
    SUBJECT_MERCHANT,
    SUBJECT_MERCHANT_STAFF,
    SUBJECT_PARTNER,
)


def verification_upload_path(instance, filename):
    subject = instance.subject_type.lower()
    return safe_media_name(f'verifications/{subject}/{instance.user_id}', filename)


class VerificationDocument(models.Model):
    SUBJECT_CHOICES = [
        (SUBJECT_MERCHANT, 'Merchant'),
        (SUBJECT_PARTNER, 'Delivery partner'),
        (SUBJECT_MERCHANT_STAFF, 'Merchant staff'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='verification_documents',
    )
    subject_type = models.CharField(max_length=20, choices=SUBJECT_CHOICES)
    document_type = models.CharField(max_length=40, choices=ALL_DOCUMENT_TYPES)
    file = models.FileField(upload_to=verification_upload_path)
    status = models.CharField(
        max_length=20,
        choices=DOCUMENT_STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_verification_documents',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=('subject_type', 'status')),
            models.Index(fields=('user', 'subject_type')),
        ]

    def __str__(self):
        return f'{self.user} - {self.subject_type} - {self.document_type}'

    def clean(self):
        super().clean()
        if self.file and not getattr(self.file, '_committed', True):
            try:
                prepare_private_document_upload(self.file)
            except ValidationError as exc:
                raise ValidationError({'file': exc})

    def save(self, *args, **kwargs):
        if self.file and not getattr(self.file, '_committed', True):
            self.file = prepare_private_document_upload(self.file)
        attach_private_upload(
            self,
            'file',
            f'verifications/{self.subject_type.lower()}/{self.user_id or "pending"}',
        )
        super().save(*args, **kwargs)


class VerificationDocumentRequirement(models.Model):
    market = models.ForeignKey(
        'markets.Market',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='verification_document_requirements',
    )
    subject_type = models.CharField(
        max_length=20,
        choices=VerificationDocument.SUBJECT_CHOICES,
    )
    document_type = models.CharField(max_length=40, choices=ALL_DOCUMENT_TYPES)
    is_required = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    display_name = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('market__name', 'subject_type', 'display_name')
        constraints = [
            models.UniqueConstraint(
                fields=('market', 'subject_type', 'document_type'),
                condition=models.Q(market__isnull=False),
                name='unique_verification_requirement_per_market_subject_doc',
            ),
            models.UniqueConstraint(
                fields=('subject_type', 'document_type'),
                condition=models.Q(market__isnull=True),
                name='unique_global_verification_requirement_subject_doc',
            ),
        ]
        indexes = [
            models.Index(fields=('market', 'subject_type', 'is_active')),
            models.Index(fields=('subject_type', 'is_required', 'is_active')),
        ]

    def __str__(self):
        market = self.market.slug if self.market_id else 'global'
        return f'{market} - {self.subject_type} - {self.document_type}'

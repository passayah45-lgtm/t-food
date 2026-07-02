from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from markets.models import country_code_validator


class SearchEvent(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='search_events',
    )
    market = models.ForeignKey(
        'markets.Market',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='search_events',
    )
    query = models.CharField(max_length=200, blank=True)
    category = models.CharField(max_length=80, blank=True)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal('-90')),
            MaxValueValidator(Decimal('90')),
        ],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal('-180')),
            MaxValueValidator(Decimal('180')),
        ],
    )
    result_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=('user', '-created_at')),
            models.Index(fields=('market', '-created_at')),
            models.Index(fields=('query', '-created_at')),
        ]

    def __str__(self):
        return f'SearchEvent #{self.id}: {self.query or "(empty)"}'


class RecommendationEvent(models.Model):
    ACTION_IMPRESSION = 'impression'
    ACTION_CLICK = 'click'
    ACTION_ORDER = 'order'
    ACTION_CHOICES = [
        (ACTION_IMPRESSION, 'Impression'),
        (ACTION_CLICK, 'Click'),
        (ACTION_ORDER, 'Order'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recommendation_events',
    )
    surface = models.CharField(max_length=80)
    object_type = models.CharField(max_length=40)
    object_id = models.CharField(max_length=80)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    score = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
    )
    reason_codes = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=('user', '-created_at')),
            models.Index(fields=('surface', 'action', '-created_at')),
            models.Index(fields=('object_type', 'object_id', '-created_at')),
        ]

    def __str__(self):
        return f'{self.action}: {self.surface}/{self.object_type}/{self.object_id}'


class VisualSearchEvent(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='visual_search_events',
    )
    provider_code = models.CharField(max_length=60)
    labels = models.JSONField(default=list, blank=True)
    normalized_query = models.CharField(max_length=240, blank=True)
    fallback_query = models.CharField(max_length=240, blank=True)
    confidence = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal('0')),
            MaxValueValidator(Decimal('1')),
        ],
    )
    market = models.ForeignKey(
        'markets.Market',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='visual_search_events',
    )
    country_code = models.CharField(
        max_length=2,
        blank=True,
        validators=[country_code_validator],
    )
    category = models.CharField(max_length=80, blank=True)
    result_count = models.PositiveIntegerField(default=0)
    matched_item_count = models.PositiveIntegerField(default=0)
    matched_merchant_count = models.PositiveIntegerField(default=0)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal('-90')),
            MaxValueValidator(Decimal('90')),
        ],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal('-180')),
            MaxValueValidator(Decimal('180')),
        ],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=('user', '-created_at')),
            models.Index(fields=('market', '-created_at')),
            models.Index(fields=('provider_code', '-created_at')),
            models.Index(fields=('country_code', '-created_at')),
        ]

    def __str__(self):
        return f'VisualSearchEvent #{self.id}: {self.normalized_query or "(empty)"}'

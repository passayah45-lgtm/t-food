from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.utils.text import slugify

from fooddelivery.gis_fields import PointField


currency_code_validator = RegexValidator(
    regex=r'^[A-Z]{3}$',
    message='Currency code must be a three-letter ISO 4217 code.',
)

country_code_validator = RegexValidator(
    regex=r'^[A-Z]{2}$',
    message='Country code must be a two-letter ISO 3166-1 alpha-2 code.',
)


class Currency(models.Model):
    code = models.CharField(
        max_length=3,
        unique=True,
        validators=[currency_code_validator],
        help_text='ISO 4217 currency code, for example INR or USD.',
    )
    numeric_code = models.CharField(
        max_length=3,
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^\d{3}$',
                message='Numeric code must be a three-digit ISO 4217 code.',
            )
        ],
    )
    name = models.CharField(max_length=80)
    symbol = models.CharField(max_length=8, blank=True)
    minor_unit = models.PositiveSmallIntegerField(
        default=2,
        validators=[MaxValueValidator(6)],
        help_text='Number of decimal places used by this currency.',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('code',)
        indexes = [
            models.Index(fields=('is_active', 'code')),
        ]
        verbose_name_plural = 'currencies'

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.code} - {self.name}'


class Market(models.Model):
    slug = models.SlugField(
        max_length=60,
        unique=True,
        help_text='Stable API-safe market identifier, for example india.',
    )
    name = models.CharField(max_length=100)
    country_code = models.CharField(
        max_length=2,
        validators=[country_code_validator],
        help_text='ISO 3166-1 alpha-2 country code, for example IN.',
    )
    default_currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='markets',
    )
    timezone = models.CharField(
        max_length=64,
        default='Asia/Kolkata',
        help_text='IANA time zone used for local business rules.',
    )
    phone_country_code = models.CharField(
        max_length=8,
        blank=True,
        help_text='Dialing prefix, for example +91.',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('name',)
        indexes = [
            models.Index(fields=('is_active', 'country_code')),
            models.Index(fields=('slug', 'is_active')),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=('country_code',),
                condition=models.Q(is_active=True),
                name='unique_active_market_per_country',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.country_code:
            self.country_code = self.country_code.upper()
        if not self.slug and self.name:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class CommerceCity(models.Model):
    market = models.ForeignKey(
        Market,
        on_delete=models.PROTECT,
        related_name='commerce_cities',
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=80)
    center_point = PointField(srid=4326, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('market__name', 'name')
        constraints = [
            models.UniqueConstraint(
                fields=('market', 'slug'),
                name='unique_commerce_city_slug_per_market',
            ),
        ]
        indexes = [
            models.Index(fields=('market', 'is_active', 'name')),
        ]
        verbose_name_plural = 'commerce cities'

    def save(self, *args, **kwargs):
        if not self.slug and self.name:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.name}, {self.market.name}'


class CommerceArea(models.Model):
    market = models.ForeignKey(
        Market,
        on_delete=models.PROTECT,
        related_name='commerce_areas',
    )
    city = models.ForeignKey(
        CommerceCity,
        on_delete=models.PROTECT,
        related_name='areas',
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=80)
    center_point = PointField(srid=4326, null=True, blank=True)
    service_radius_km = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('city__name', 'name')
        constraints = [
            models.UniqueConstraint(
                fields=('city', 'slug'),
                name='unique_commerce_area_slug_per_city',
            ),
        ]
        indexes = [
            models.Index(fields=('market', 'is_active', 'name')),
            models.Index(fields=('city', 'is_active', 'name')),
        ]

    def save(self, *args, **kwargs):
        if self.city_id:
            self.market = self.city.market
        if not self.slug and self.name:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.name}, {self.city.name}'

from django.conf import settings
from django.db import models


class UserPreference(models.Model):
    LANGUAGE_ENGLISH = 'en'
    LANGUAGE_FRENCH = 'fr'
    LANGUAGE_ARABIC = 'ar'
    LANGUAGE_HINDI = 'hi'
    LANGUAGE_SPANISH = 'es'
    LANGUAGE_PORTUGUESE = 'pt'
    LANGUAGE_CHINESE = 'zh'
    LANGUAGE_GERMAN = 'de'
    LANGUAGE_RUSSIAN = 'ru'
    LANGUAGE_JAPANESE = 'ja'
    LANGUAGE_KOREAN = 'ko'
    LANGUAGE_CHOICES = [
        (LANGUAGE_ENGLISH, 'English'),
        (LANGUAGE_FRENCH, 'French'),
        (LANGUAGE_ARABIC, 'Arabic'),
        (LANGUAGE_HINDI, 'Hindi'),
        (LANGUAGE_SPANISH, 'Spanish'),
        (LANGUAGE_PORTUGUESE, 'Portuguese'),
        (LANGUAGE_CHINESE, 'Chinese'),
        (LANGUAGE_GERMAN, 'German'),
        (LANGUAGE_RUSSIAN, 'Russian'),
        (LANGUAGE_JAPANESE, 'Japanese'),
        (LANGUAGE_KOREAN, 'Korean'),
    ]

    THEME_LIGHT = 'LIGHT'
    THEME_DARK = 'DARK'
    THEME_SYSTEM = 'SYSTEM'
    THEME_CHOICES = [
        (THEME_LIGHT, 'Light'),
        (THEME_DARK, 'Dark'),
        (THEME_SYSTEM, 'System'),
    ]

    ACCENT_ORANGE = 'ORANGE'
    ACCENT_BLUE = 'BLUE'
    ACCENT_GREEN = 'GREEN'
    ACCENT_PURPLE = 'PURPLE'
    ACCENT_RED = 'RED'
    ACCENT_PINK = 'PINK'
    ACCENT_TEAL = 'TEAL'
    ACCENT_CHOICES = [
        (ACCENT_ORANGE, 'Orange'),
        (ACCENT_BLUE, 'Blue'),
        (ACCENT_GREEN, 'Green'),
        (ACCENT_PURPLE, 'Purple'),
        (ACCENT_RED, 'Red'),
        (ACCENT_PINK, 'Pink'),
        (ACCENT_TEAL, 'Teal'),
    ]

    DATE_AUTO = 'AUTO'
    DATE_DD_MM_YYYY = 'DD_MM_YYYY'
    DATE_MM_DD_YYYY = 'MM_DD_YYYY'
    DATE_YYYY_MM_DD = 'YYYY_MM_DD'
    DATE_FORMAT_CHOICES = [
        (DATE_AUTO, 'Automatic'),
        (DATE_DD_MM_YYYY, 'DD/MM/YYYY'),
        (DATE_MM_DD_YYYY, 'MM/DD/YYYY'),
        (DATE_YYYY_MM_DD, 'YYYY-MM-DD'),
    ]

    TIME_AUTO = 'AUTO'
    TIME_12 = 'H_12'
    TIME_24 = 'H_24'
    TIME_FORMAT_CHOICES = [
        (TIME_AUTO, 'Automatic'),
        (TIME_12, '12-hour'),
        (TIME_24, '24-hour'),
    ]

    NUMBER_AUTO = 'AUTO'
    NUMBER_EN = 'EN'
    NUMBER_FR = 'FR'
    NUMBER_HI = 'HI'
    NUMBER_AR = 'AR'
    NUMBER_FORMAT_CHOICES = [
        (NUMBER_AUTO, 'Automatic'),
        (NUMBER_EN, 'English'),
        (NUMBER_FR, 'French'),
        (NUMBER_HI, 'Hindi'),
        (NUMBER_AR, 'Arabic'),
    ]

    CURRENCY_DISPLAY_SYMBOL = 'SYMBOL'
    CURRENCY_DISPLAY_CODE = 'CODE'
    CURRENCY_DISPLAY_NAME = 'NAME'
    CURRENCY_DISPLAY_CHOICES = [
        (CURRENCY_DISPLAY_SYMBOL, 'Symbol'),
        (CURRENCY_DISPLAY_CODE, 'Code'),
        (CURRENCY_DISPLAY_NAME, 'Name'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='preference_profile',
    )
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    language = models.CharField(
        max_length=12,
        choices=LANGUAGE_CHOICES,
        default=LANGUAGE_ENGLISH,
    )
    preferred_country = models.CharField(max_length=2, blank=True)
    preferred_market = models.ForeignKey(
        'markets.Market',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_preferences',
    )
    theme = models.CharField(
        max_length=12,
        choices=THEME_CHOICES,
        default=THEME_SYSTEM,
    )
    accent_color = models.CharField(
        max_length=20,
        choices=ACCENT_CHOICES,
        default=ACCENT_ORANGE,
    )
    timezone = models.CharField(max_length=64, blank=True)
    date_format = models.CharField(
        max_length=20,
        choices=DATE_FORMAT_CHOICES,
        default=DATE_AUTO,
    )
    time_format = models.CharField(
        max_length=12,
        choices=TIME_FORMAT_CHOICES,
        default=TIME_AUTO,
    )
    number_format = models.CharField(
        max_length=12,
        choices=NUMBER_FORMAT_CHOICES,
        default=NUMBER_AUTO,
    )
    preferred_currency = models.ForeignKey(
        'markets.Currency',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_preferences',
    )
    currency_display = models.CharField(
        max_length=12,
        choices=CURRENCY_DISPLAY_CHOICES,
        default=CURRENCY_DISPLAY_SYMBOL,
    )
    large_text = models.BooleanField(default=False)
    high_contrast = models.BooleanField(default=False)
    reduced_motion = models.BooleanField(default=False)
    keyboard_focus_enhanced = models.BooleanField(default=False)
    preference_version = models.PositiveIntegerField(default=1)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('user__username', 'id')
        indexes = [
            models.Index(
                fields=('language',),
                name='user_pref_language_idx',
            ),
            models.Index(
                fields=('theme', 'accent_color'),
                name='user_pref_theme_accent_idx',
            ),
            models.Index(
                fields=('preferred_country',),
                name='user_pref_country_idx',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.preferred_country:
            self.preferred_country = self.preferred_country.upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.user} preferences'

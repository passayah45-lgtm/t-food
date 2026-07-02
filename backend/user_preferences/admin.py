from django.contrib import admin

from .models import UserPreference


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'language', 'theme', 'accent_color', 'preferred_country',
        'preferred_currency', 'currency_display', 'preference_version',
        'updated_at',
    )
    list_filter = (
        'language', 'theme', 'accent_color', 'currency_display',
        'large_text', 'high_contrast', 'reduced_motion',
    )
    search_fields = ('user__username', 'user__email', 'preferred_country')
    autocomplete_fields = ('user', 'preferred_market', 'preferred_currency')
    readonly_fields = ('preference_version', 'created_at', 'updated_at')

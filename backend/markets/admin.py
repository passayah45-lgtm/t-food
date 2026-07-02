from django.contrib import admin

from .models import CommerceArea, CommerceCity, Currency, Market


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'symbol',
        'minor_unit',
        'is_active',
        'updated_at',
    )
    list_filter = ('is_active', 'minor_unit')
    search_fields = ('code', 'numeric_code', 'name')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('code',)


@admin.register(Market)
class MarketAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'slug',
        'country_code',
        'default_currency',
        'timezone',
        'phone_country_code',
        'is_active',
    )
    list_filter = ('is_active', 'country_code', 'default_currency')
    search_fields = ('name', 'slug', 'country_code')
    readonly_fields = ('created_at', 'updated_at')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('name',)


@admin.register(CommerceCity)
class CommerceCityAdmin(admin.ModelAdmin):
    list_display = ('name', 'market', 'is_active', 'updated_at')
    list_filter = ('is_active', 'market')
    search_fields = ('name', 'slug', 'market__name', 'market__country_code')
    readonly_fields = ('created_at', 'updated_at')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('market__name', 'name')


@admin.register(CommerceArea)
class CommerceAreaAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'market', 'service_radius_km', 'is_active', 'updated_at')
    list_filter = ('is_active', 'market', 'city')
    search_fields = ('name', 'slug', 'city__name', 'market__name', 'market__country_code')
    readonly_fields = ('created_at', 'updated_at')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('city__name', 'name')

from django.contrib import admin

from .models import RecommendationEvent, SearchEvent, VisualSearchEvent


@admin.register(SearchEvent)
class SearchEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'query', 'category', 'result_count', 'created_at')
    list_filter = ('created_at', 'market')
    search_fields = ('query', 'category', 'user__username')
    readonly_fields = ('created_at',)


@admin.register(RecommendationEvent)
class RecommendationEventAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'user', 'surface', 'object_type', 'object_id', 'action',
        'score', 'created_at',
    )
    list_filter = ('action', 'surface', 'object_type', 'created_at')
    search_fields = ('surface', 'object_type', 'object_id', 'user__username')
    readonly_fields = ('created_at',)


@admin.register(VisualSearchEvent)
class VisualSearchEventAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'user', 'provider_code', 'normalized_query', 'confidence',
        'market', 'country_code', 'category', 'result_count',
        'matched_item_count', 'matched_merchant_count', 'created_at',
    )
    list_filter = ('provider_code', 'market', 'country_code', 'category', 'created_at')
    search_fields = ('normalized_query', 'provider_code', 'user__username')
    readonly_fields = ('created_at',)

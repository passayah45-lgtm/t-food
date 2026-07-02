from django.contrib import admin

from .models import (
    OperationsAccessAudit,
    OperationsStaffAreaAccess,
    OperationsStaffCityAccess,
    OperationsStaffMarketAccess,
    OperationsStaffProfile,
)


class OperationsStaffMarketAccessInline(admin.TabularInline):
    model = OperationsStaffMarketAccess
    extra = 0
    autocomplete_fields = ('market', 'created_by')


class OperationsStaffCityAccessInline(admin.TabularInline):
    model = OperationsStaffCityAccess
    extra = 0
    autocomplete_fields = ('city', 'created_by')


class OperationsStaffAreaAccessInline(admin.TabularInline):
    model = OperationsStaffAreaAccess
    extra = 0
    autocomplete_fields = ('area', 'created_by')


@admin.register(OperationsStaffProfile)
class OperationsStaffProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'status', 'created_at', 'updated_at')
    list_filter = ('role', 'status')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    autocomplete_fields = ('user', 'created_by', 'updated_by')
    inlines = (
        OperationsStaffMarketAccessInline,
        OperationsStaffCityAccessInline,
        OperationsStaffAreaAccessInline,
    )


@admin.register(OperationsStaffMarketAccess)
class OperationsStaffMarketAccessAdmin(admin.ModelAdmin):
    list_display = ('profile', 'market', 'created_by', 'created_at')
    list_filter = ('market',)
    search_fields = ('profile__user__username', 'market__name', 'market__country_code')
    autocomplete_fields = ('profile', 'market', 'created_by')


@admin.register(OperationsStaffCityAccess)
class OperationsStaffCityAccessAdmin(admin.ModelAdmin):
    list_display = ('profile', 'city', 'created_by', 'created_at')
    list_filter = ('city__market',)
    search_fields = ('profile__user__username', 'city__name', 'city__market__name')
    autocomplete_fields = ('profile', 'city', 'created_by')


@admin.register(OperationsStaffAreaAccess)
class OperationsStaffAreaAccessAdmin(admin.ModelAdmin):
    list_display = ('profile', 'area', 'created_by', 'created_at')
    list_filter = ('area__market', 'area__city')
    search_fields = ('profile__user__username', 'area__name', 'area__city__name')
    autocomplete_fields = ('profile', 'area', 'created_by')


@admin.register(OperationsAccessAudit)
class OperationsAccessAuditAdmin(admin.ModelAdmin):
    list_display = ('action', 'actor', 'target_type', 'target_id', 'scope_type', 'scope_id', 'created_at')
    list_filter = ('action', 'scope_type')
    search_fields = ('actor__username', 'action', 'target_type', 'target_id', 'scope_type', 'scope_id')
    readonly_fields = ('created_at',)
    autocomplete_fields = ('actor',)


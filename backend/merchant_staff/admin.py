from django.contrib import admin

from .models import (
    MerchantStaffBranchAccess,
    MerchantStaffInvite,
    MerchantStaffMember,
)


class MerchantStaffBranchAccessInline(admin.TabularInline):
    model = MerchantStaffBranchAccess
    extra = 0
    autocomplete_fields = ('branch', 'created_by')


@admin.register(MerchantStaffMember)
class MerchantStaffMemberAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'merchant', 'role', 'membership_status',
        'verification_status', 'is_company_wide', 'created_at',
    )
    list_filter = (
        'role', 'membership_status', 'verification_status',
        'is_company_wide', 'created_at',
    )
    search_fields = (
        'user__username', 'user__email', 'user__first_name',
        'user__last_name', 'merchant__business_name',
    )
    autocomplete_fields = (
        'merchant', 'user', 'verification_reviewed_by',
        'created_by', 'updated_by',
    )
    readonly_fields = ('created_at', 'updated_at')
    inlines = (MerchantStaffBranchAccessInline,)


@admin.register(MerchantStaffBranchAccess)
class MerchantStaffBranchAccessAdmin(admin.ModelAdmin):
    list_display = ('staff_member', 'branch', 'created_by', 'created_at')
    list_filter = ('created_at',)
    search_fields = (
        'staff_member__user__username',
        'staff_member__merchant__business_name',
        'branch__rest_name',
        'branch__branch_name',
    )
    autocomplete_fields = ('staff_member', 'branch', 'created_by')
    readonly_fields = ('created_at',)


@admin.register(MerchantStaffInvite)
class MerchantStaffInviteAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'email', 'merchant', 'role', 'status',
        'is_company_wide', 'expires_at', 'created_at',
    )
    list_filter = ('role', 'status', 'is_company_wide', 'expires_at')
    search_fields = (
        'name', 'email', 'phone', 'merchant__business_name',
        'invite_token',
    )
    autocomplete_fields = ('merchant', 'invited_by', 'linked_staff_member')
    filter_horizontal = ('branches',)
    readonly_fields = ('invite_token', 'created_at', 'updated_at')

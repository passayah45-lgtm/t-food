from django.contrib import admin

from .models import VerificationDocument, VerificationDocumentRequirement


@admin.register(VerificationDocument)
class VerificationDocumentAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'subject_type', 'document_type', 'status',
        'reviewed_by', 'reviewed_at', 'created_at',
    )
    list_filter = ('subject_type', 'document_type', 'status')
    search_fields = ('user__username', 'notes', 'rejection_reason')
    readonly_fields = ('created_at', 'updated_at', 'reviewed_at')


@admin.register(VerificationDocumentRequirement)
class VerificationDocumentRequirementAdmin(admin.ModelAdmin):
    list_display = (
        'market', 'subject_type', 'document_type', 'display_name',
        'is_required', 'is_active', 'updated_at',
    )
    list_filter = ('market', 'subject_type', 'document_type', 'is_required', 'is_active')
    search_fields = ('display_name', 'market__name', 'market__slug')
    readonly_fields = ('created_at', 'updated_at')

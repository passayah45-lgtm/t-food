from django.urls import path

from .verification_views import (
    MerchantDocumentListCreateView,
    OwnedDocumentDeleteView,
    PartnerDocumentListCreateView,
    StaffDocumentListCreateView,
    VerificationDocumentDownloadView,
)


urlpatterns = [
    path(
        'documents/<int:document_id>/download/',
        VerificationDocumentDownloadView.as_view(),
        name='api_verification_document_download',
    ),
    path(
        'merchant/documents/',
        MerchantDocumentListCreateView.as_view(),
        name='api_merchant_verification_documents',
    ),
    path(
        'merchant/documents/<int:pk>/',
        OwnedDocumentDeleteView.as_view(),
        {'subject_type': 'MERCHANT'},
        name='api_merchant_verification_document_delete',
    ),
    path(
        'partner/documents/',
        PartnerDocumentListCreateView.as_view(),
        name='api_partner_verification_documents',
    ),
    path(
        'partner/documents/<int:pk>/',
        OwnedDocumentDeleteView.as_view(),
        {'subject_type': 'PARTNER'},
        name='api_partner_verification_document_delete',
    ),
    path(
        'staff/documents/',
        StaffDocumentListCreateView.as_view(),
        name='api_staff_verification_documents',
    ),
    path(
        'staff/documents/<int:pk>/',
        OwnedDocumentDeleteView.as_view(),
        {'subject_type': 'MERCHANT_STAFF'},
        name='api_staff_verification_document_delete',
    ),
]

import os

from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from delivery.models import DeliveryPartner
from fooddelivery.media_storage import (
    file_response,
    open_private_file,
    private_file_exists,
    private_storage,
)
from fooddelivery.upload_validation import prepare_private_document_upload
from merchant_staff.models import MerchantStaffMember
from restaurants.models import MerchantProfile
from notifications.events import notify_verification_event
from operations_access.permissions import (
    MANAGE_VERIFICATIONS,
    VIEW_VERIFICATIONS,
    get_operations_actor,
    require_operations_permission,
)
from api.operations_views import (
    scoped_merchant_queryset,
    scoped_partner_queryset,
    scoped_staff_queryset,
)
from verifications.constants import (
    MERCHANT_DOCUMENT_VALUES,
    PARTNER_DOCUMENT_VALUES,
    STATUS_APPROVED,
    STATUS_REJECTED,
    SUBJECT_MERCHANT,
    SUBJECT_MERCHANT_STAFF,
    SUBJECT_PARTNER,
    VERIFICATION_REJECTED,
)
from verifications.models import VerificationDocument
from verifications.services import (
    approve_staff_member,
    mark_merchant_submitted,
    mark_partner_submitted,
    mark_staff_submitted,
    merchant_document_summary,
    partner_document_summary,
    reject_staff_member,
    review_document,
    staff_allowed_document_types,
    staff_document_summary,
    staff_missing_requirements,
)


def document_list_payload(response_data, summary):
    if isinstance(response_data, dict) and 'results' in response_data:
        payload = dict(response_data)
        payload['summary'] = summary
        return payload
    return {
        'summary': summary,
        'results': response_data,
    }


class VerificationDocumentSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True, required=False)
    file_url = serializers.SerializerMethodField()
    filename = serializers.SerializerMethodField()
    size_bytes = serializers.SerializerMethodField()
    reviewed_by_username = serializers.CharField(
        source='reviewed_by.username', read_only=True
    )

    class Meta:
        model = VerificationDocument
        fields = (
            'id', 'subject_type', 'document_type', 'file', 'file_url',
            'filename', 'size_bytes', 'status', 'notes', 'rejection_reason',
            'reviewed_by', 'reviewed_by_username', 'reviewed_at',
            'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'subject_type', 'file_url', 'status', 'rejection_reason',
            'reviewed_by', 'reviewed_by_username', 'reviewed_at',
            'created_at', 'updated_at',
        )

    def get_file_url(self, obj):
        request = self.context.get('request')
        if not obj.file:
            return None
        path = f'/api/v1/verifications/documents/{obj.id}/download/'
        return request.build_absolute_uri(path) if request else path

    def get_filename(self, obj):
        return os.path.basename(obj.file.name) if obj.file else ''

    def get_size_bytes(self, obj):
        if not obj.file or not private_file_exists(obj.file.name):
            return None
        return private_storage().size(obj.file.name)


class DocumentUploadSerializer(VerificationDocumentSerializer):
    file = serializers.FileField(write_only=True, required=True)

    class Meta(VerificationDocumentSerializer.Meta):
        fields = (
            'id', 'subject_type', 'document_type', 'file', 'file_url',
            'filename', 'size_bytes', 'status', 'notes', 'rejection_reason',
            'reviewed_by', 'reviewed_by_username', 'reviewed_at',
            'created_at', 'updated_at',
        )
        read_only_fields = VerificationDocumentSerializer.Meta.read_only_fields

    def validate_document_type(self, value):
        allowed = self.context['allowed_document_types']
        if value not in allowed:
            raise serializers.ValidationError(
                'Choose a valid document type for this account.'
            )
        return value

    def validate_file(self, value):
        try:
            return prepare_private_document_upload(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)


def user_can_access_document(user, document):
    if not user or not user.is_authenticated:
        return False
    if document.user_id == user.id:
        return True
    actor = get_operations_actor(user)
    if not actor.permissions:
        return False
    require_operations_permission(actor, VIEW_VERIFICATIONS)
    if document.subject_type == SUBJECT_MERCHANT:
        profile = getattr(document.user, 'merchant_profile', None)
        return bool(profile and scoped_merchant_queryset(
            MerchantProfile.objects.filter(id=profile.id),
            actor,
        ).exists())
    if document.subject_type == SUBJECT_PARTNER:
        partner = getattr(document.user, 'delivery_partner', None)
        return bool(partner and scoped_partner_queryset(
            DeliveryPartner.objects.filter(id=partner.id),
            actor,
        ).exists())
    if document.subject_type == SUBJECT_MERCHANT_STAFF:
        staff_member = get_current_staff_member(document.user)
        return bool(staff_member and scoped_staff_queryset(
            MerchantStaffMember.objects.filter(id=staff_member.id),
            actor,
        ).exists())
    return False


class VerificationDocumentDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, document_id):
        document = get_object_or_404(VerificationDocument, id=document_id)
        if not user_can_access_document(request.user, document):
            raise PermissionDenied('You do not have access to this document.')
        if not document.file or not private_file_exists(document.file.name):
            return Response(
                {'detail': 'Document file not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return file_response(
            open_private_file(document.file.name, 'rb'),
            filename=os.path.basename(document.file.name),
        )

    def validate_document_type(self, value):
        allowed = self.context['allowed_document_types']
        if value not in allowed:
            raise serializers.ValidationError(
                'Choose a valid document type for this account.'
            )
        return value


class MerchantDocumentListCreateView(generics.ListCreateAPIView):
    serializer_class = DocumentUploadSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_profile(self):
        if not hasattr(self.request.user, 'merchant_profile'):
            raise PermissionDenied('Merchant access required.')
        return self.request.user.merchant_profile

    def get_queryset(self):
        self.get_profile()
        return VerificationDocument.objects.filter(
            user=self.request.user,
            subject_type=SUBJECT_MERCHANT,
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['allowed_document_types'] = MERCHANT_DOCUMENT_VALUES
        return context

    def perform_create(self, serializer):
        profile = self.get_profile()
        serializer.save(user=self.request.user, subject_type=SUBJECT_MERCHANT)
        mark_merchant_submitted(profile)

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response.data = document_list_payload(
            response.data,
            merchant_document_summary(request.user),
        )
        return response


class PartnerDocumentListCreateView(generics.ListCreateAPIView):
    serializer_class = DocumentUploadSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_partner(self):
        if not hasattr(self.request.user, 'delivery_partner'):
            raise PermissionDenied('Delivery partner access required.')
        return self.request.user.delivery_partner

    def get_queryset(self):
        self.get_partner()
        return VerificationDocument.objects.filter(
            user=self.request.user,
            subject_type=SUBJECT_PARTNER,
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['allowed_document_types'] = PARTNER_DOCUMENT_VALUES
        return context

    def perform_create(self, serializer):
        partner = self.get_partner()
        serializer.save(user=self.request.user, subject_type=SUBJECT_PARTNER)
        mark_partner_submitted(partner)

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response.data = document_list_payload(
            response.data,
            partner_document_summary(request.user),
        )
        return response


def get_current_staff_member(user):
    return (
        MerchantStaffMember.objects
        .select_related('merchant', 'merchant__market', 'user')
        .filter(user=user)
        .exclude(membership_status=MerchantStaffMember.STATUS_REMOVED)
        .order_by('id')
        .first()
    )


class StaffDocumentListCreateView(generics.ListCreateAPIView):
    serializer_class = DocumentUploadSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_staff_member(self):
        staff_member = get_current_staff_member(self.request.user)
        if not staff_member:
            raise PermissionDenied('Merchant staff access required.')
        return staff_member

    def get_queryset(self):
        self.get_staff_member()
        return VerificationDocument.objects.filter(
            user=self.request.user,
            subject_type=SUBJECT_MERCHANT_STAFF,
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['allowed_document_types'] = staff_allowed_document_types(
            self.get_staff_member()
        )
        return context

    def perform_create(self, serializer):
        staff_member = self.get_staff_member()
        serializer.save(
            user=self.request.user,
            subject_type=SUBJECT_MERCHANT_STAFF,
        )
        mark_staff_submitted(staff_member)

    def list(self, request, *args, **kwargs):
        staff_member = self.get_staff_member()
        response = super().list(request, *args, **kwargs)
        response.data = document_list_payload(
            response.data,
            staff_document_summary(staff_member),
        )
        return response


class OwnedDocumentDeleteView(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        subject_type = self.kwargs['subject_type']
        return VerificationDocument.objects.filter(
            user=self.request.user,
            subject_type=subject_type,
        )

    def destroy(self, request, *args, **kwargs):
        document = self.get_object()
        if document.status == STATUS_APPROVED:
            return Response(
                {'detail': 'Approved documents cannot be deleted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)


class OperationsMerchantDocumentListView(generics.ListAPIView):
    serializer_class = VerificationDocumentSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        actor = get_operations_actor(self.request.user)
        require_operations_permission(actor, VIEW_VERIFICATIONS)
        merchant = get_object_or_404(
            scoped_merchant_queryset(MerchantProfile.objects.all(), actor),
            id=self.kwargs['merchant_id'],
        )
        return VerificationDocument.objects.filter(
            user=merchant.user,
            subject_type=SUBJECT_MERCHANT,
        )

    def list(self, request, *args, **kwargs):
        actor = get_operations_actor(request.user)
        merchant = get_object_or_404(
            scoped_merchant_queryset(MerchantProfile.objects.all(), actor),
            id=self.kwargs['merchant_id'],
        )
        response = super().list(request, *args, **kwargs)
        response.data = document_list_payload(
            response.data,
            merchant_document_summary(merchant.user),
        )
        return response


class OperationsPartnerDocumentListView(generics.ListAPIView):
    serializer_class = VerificationDocumentSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        actor = get_operations_actor(self.request.user)
        require_operations_permission(actor, VIEW_VERIFICATIONS)
        partner = get_object_or_404(
            scoped_partner_queryset(DeliveryPartner.objects.all(), actor),
            id=self.kwargs['partner_id'],
        )
        return VerificationDocument.objects.filter(
            user=partner.user,
            subject_type=SUBJECT_PARTNER,
        )

    def list(self, request, *args, **kwargs):
        actor = get_operations_actor(request.user)
        partner = get_object_or_404(
            scoped_partner_queryset(DeliveryPartner.objects.all(), actor),
            id=self.kwargs['partner_id'],
        )
        response = super().list(request, *args, **kwargs)
        response.data = document_list_payload(
            response.data,
            partner_document_summary(partner.user),
        )
        return response


class OperationsStaffDocumentListView(generics.ListAPIView):
    serializer_class = VerificationDocumentSerializer
    permission_classes = [IsAdminUser]

    def get_staff_member(self):
        actor = get_operations_actor(self.request.user)
        require_operations_permission(actor, VIEW_VERIFICATIONS)
        return get_object_or_404(
            scoped_staff_queryset(
                MerchantStaffMember.objects.select_related('user', 'merchant'),
                actor,
            ),
            id=self.kwargs['staff_id'],
        )

    def get_queryset(self):
        staff_member = self.get_staff_member()
        return VerificationDocument.objects.filter(
            user=staff_member.user,
            subject_type=SUBJECT_MERCHANT_STAFF,
        )

    def list(self, request, *args, **kwargs):
        staff_member = self.get_staff_member()
        response = super().list(request, *args, **kwargs)
        response.data = document_list_payload(
            response.data,
            staff_document_summary(staff_member),
        )
        return response


class OperationsStaffStatusView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, staff_id):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, MANAGE_VERIFICATIONS)
        action = request.data.get('action')
        if action == 'MORE_INFO_REQUIRED':
            action = 'REQUEST_MORE_INFO'
        if action not in {'APPROVE', 'REJECT', 'SUSPEND', 'REQUEST_MORE_INFO'}:
            return Response(
                {'action': ['Choose APPROVE, REJECT, SUSPEND, or REQUEST_MORE_INFO.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        staff_member = (
            scoped_staff_queryset(MerchantStaffMember.objects.all(), actor)
            .select_related('user', 'merchant')
            .filter(id=staff_id)
            .first()
        )
        if not staff_member:
            return Response(
                {'detail': 'Merchant staff member not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        reason = request.data.get('rejection_reason', '').strip()
        if action in {'REJECT', 'SUSPEND', 'REQUEST_MORE_INFO'} and not reason:
            return Response(
                {'rejection_reason': ['Explain the verification decision.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if action == 'APPROVE':
            missing = staff_missing_requirements(staff_member)
            if missing:
                return Response(
                    {'documents': missing},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            approve_staff_member(staff_member, request.user)
        elif action == 'SUSPEND':
            reject_staff_member(staff_member, request.user, reason)
            staff_member.refresh_from_db()
            staff_member.verification_status = staff_member.VERIFICATION_SUSPENDED
            staff_member.save(update_fields=('verification_status', 'updated_at'))
        elif action == 'REQUEST_MORE_INFO':
            staff_member.verification_status = (
                staff_member.VERIFICATION_MORE_INFO_REQUIRED
            )
            staff_member.verification_rejection_reason = reason
            staff_member.verification_reviewed_at = timezone.now()
            staff_member.verification_reviewed_by = request.user
            if staff_member.membership_status == staff_member.STATUS_ACTIVE:
                staff_member.membership_status = staff_member.STATUS_INACTIVE
            staff_member.save(update_fields=(
                'membership_status',
                'verification_status',
                'verification_rejection_reason',
                'verification_reviewed_at',
                'verification_reviewed_by',
                'updated_at',
            ))
            notify_verification_event(
                staff_member,
                'staff_more_info_requested',
                actor=request.user,
            )
        else:
            reject_staff_member(staff_member, request.user, reason)

        staff_member.refresh_from_db()
        return Response({
            'id': staff_member.id,
            'merchant': staff_member.merchant_id,
            'user': staff_member.user_id,
            'role': staff_member.role,
            'membership_status': staff_member.membership_status,
            'verification_status': staff_member.verification_status,
            'verification_rejection_reason': (
                staff_member.verification_rejection_reason
            ),
            'verification_reviewed_by': (
                staff_member.verification_reviewed_by_id
            ),
            'verification_reviewed_at': staff_member.verification_reviewed_at,
        })


class OperationsDocumentReviewView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, document_id):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, MANAGE_VERIFICATIONS)
        document = get_object_or_404(VerificationDocument, id=document_id)
        if document.subject_type == SUBJECT_MERCHANT:
            profile = getattr(document.user, 'merchant_profile', None)
            if not profile or not scoped_merchant_queryset(
                MerchantProfile.objects.filter(id=profile.id),
                actor,
            ).exists():
                raise PermissionDenied('You do not have access to this verification document.')
        elif document.subject_type == SUBJECT_PARTNER:
            partner = getattr(document.user, 'delivery_partner', None)
            if not partner or not scoped_partner_queryset(
                DeliveryPartner.objects.filter(id=partner.id),
                actor,
            ).exists():
                raise PermissionDenied('You do not have access to this verification document.')
        elif document.subject_type == SUBJECT_MERCHANT_STAFF:
            staff_member = get_current_staff_member(document.user)
            if not staff_member or not scoped_staff_queryset(
                MerchantStaffMember.objects.filter(id=staff_member.id),
                actor,
            ).exists():
                raise PermissionDenied('You do not have access to this verification document.')
        next_status = request.data.get('status')
        action = request.data.get('action')
        if action == 'APPROVE_DOCUMENT':
            next_status = STATUS_APPROVED
        elif action == 'REJECT_DOCUMENT':
            next_status = STATUS_REJECTED
        if next_status not in {STATUS_APPROVED, STATUS_REJECTED}:
            return Response(
                {'status': ['Choose APPROVED or REJECTED.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        reason = request.data.get('rejection_reason', '').strip()
        if next_status == STATUS_REJECTED and not reason:
            return Response(
                {'rejection_reason': ['Explain why this document was rejected.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        document = review_document(document, request.user, next_status, reason)

        if next_status == STATUS_REJECTED:
            if document.subject_type == SUBJECT_MERCHANT:
                profile = getattr(document.user, 'merchant_profile', None)
                if profile:
                    profile.is_verified = False
                    profile.verification_status = VERIFICATION_REJECTED
                    profile.verification_rejection_reason = reason
                    profile.verification_reviewed_at = timezone.now()
                    profile.verification_reviewed_by = request.user
                    profile.save(update_fields=(
                        'is_verified',
                        'verification_status',
                        'verification_rejection_reason',
                        'verification_reviewed_at',
                        'verification_reviewed_by',
                    ))
            elif document.subject_type == SUBJECT_PARTNER:
                partner = getattr(document.user, 'delivery_partner', None)
                if partner:
                    partner.is_verified = False
                    partner.is_available = False
                    partner.verification_status = VERIFICATION_REJECTED
                    partner.verification_rejection_reason = reason
                    partner.verification_reviewed_at = timezone.now()
                    partner.verification_reviewed_by = request.user
                    partner.save(update_fields=(
                        'is_verified',
                        'is_available',
                        'verification_status',
                        'verification_rejection_reason',
                        'verification_reviewed_at',
                        'verification_reviewed_by',
                    ))
            elif document.subject_type == SUBJECT_MERCHANT_STAFF:
                staff_member = get_current_staff_member(document.user)
                if staff_member:
                    reject_staff_member(staff_member, request.user, reason)

        return Response(VerificationDocumentSerializer(
            document,
            context={'request': request},
        ).data)

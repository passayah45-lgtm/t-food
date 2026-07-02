from django.utils import timezone

from notifications.events import notify_verification_event

from .constants import (
    MERCHANT_IDENTITY_DOCUMENTS,
    PARTNER_IDENTITY_DOCUMENTS,
    STAFF_DOCUMENT_VALUES,
    STAFF_IDENTITY_DOCUMENTS,
    STATUS_APPROVED,
    STATUS_PENDING,
    STATUS_REJECTED,
    SUBJECT_MERCHANT,
    SUBJECT_MERCHANT_STAFF,
    SUBJECT_PARTNER,
    VERIFICATION_APPROVED,
    VERIFICATION_REJECTED,
    VERIFICATION_SUBMITTED,
    VERIFICATION_SUSPENDED,
)
from .models import VerificationDocument, VerificationDocumentRequirement


def merchant_document_summary(user):
    documents = VerificationDocument.objects.filter(
        user=user,
        subject_type=SUBJECT_MERCHANT,
    )
    types = set(documents.values_list('document_type', flat=True))
    return {
        'has_owner_profile_photo': 'OWNER_PROFILE_PHOTO' in types,
        'has_identity_document': bool(types & MERCHANT_IDENTITY_DOCUMENTS),
        'has_restaurant_photo': 'RESTAURANT_PHOTO' in types,
        'document_count': documents.count(),
    }


def partner_document_summary(user):
    documents = VerificationDocument.objects.filter(
        user=user,
        subject_type=SUBJECT_PARTNER,
    )
    types = set(documents.values_list('document_type', flat=True))
    return {
        'has_partner_profile_photo': 'PARTNER_PROFILE_PHOTO' in types,
        'has_identity_document': bool(types & PARTNER_IDENTITY_DOCUMENTS),
        'document_count': documents.count(),
    }


def staff_document_summary(staff_member):
    documents = VerificationDocument.objects.filter(
        user=staff_member.user,
        subject_type=SUBJECT_MERCHANT_STAFF,
    )
    types = set(documents.values_list('document_type', flat=True))
    return {
        'has_identity_document': bool(types & STAFF_IDENTITY_DOCUMENTS),
        'document_count': documents.count(),
    }


def merchant_missing_requirements(user):
    summary = merchant_document_summary(user)
    missing = []
    if not summary['has_owner_profile_photo']:
        missing.append('Owner profile photo is required.')
    if not summary['has_identity_document']:
        missing.append('At least one identity document is required.')
    if not summary['has_restaurant_photo']:
        missing.append('At least one restaurant photo is required.')
    return missing


def get_staff_market(staff_member):
    if staff_member.merchant.market_id:
        return staff_member.merchant.market
    return (
        staff_member.merchant.user.owned_restaurants
        .filter(market__isnull=False)
        .select_related('market')
        .order_by('id')
        .first()
        .market
        if staff_member.merchant.user.owned_restaurants.filter(
            market__isnull=False
        ).exists()
        else None
    )


def staff_allowed_document_types(staff_member):
    market = get_staff_market(staff_member)
    requirements = VerificationDocumentRequirement.objects.filter(
        subject_type=SUBJECT_MERCHANT_STAFF,
        is_active=True,
    )
    if market:
        market_requirements = requirements.filter(market=market)
        if market_requirements.exists():
            return set(market_requirements.values_list('document_type', flat=True))
    global_requirements = requirements.filter(market__isnull=True)
    if global_requirements.exists():
        return set(global_requirements.values_list('document_type', flat=True))
    return STAFF_DOCUMENT_VALUES


def staff_required_document_types(staff_member):
    market = get_staff_market(staff_member)
    requirements = VerificationDocumentRequirement.objects.filter(
        subject_type=SUBJECT_MERCHANT_STAFF,
        is_active=True,
        is_required=True,
    )
    if market:
        market_requirements = requirements.filter(market=market)
        if market_requirements.exists():
            return set(market_requirements.values_list('document_type', flat=True))
    global_requirements = requirements.filter(market__isnull=True)
    if global_requirements.exists():
        return set(global_requirements.values_list('document_type', flat=True))
    return STAFF_IDENTITY_DOCUMENTS


def partner_missing_requirements(user):
    summary = partner_document_summary(user)
    missing = []
    if not summary['has_partner_profile_photo']:
        missing.append('Partner profile photo is required.')
    if not summary['has_identity_document']:
        missing.append('At least one identity or driving license document is required.')
    return missing


def staff_missing_requirements(staff_member):
    uploaded = set(VerificationDocument.objects.filter(
        user=staff_member.user,
        subject_type=SUBJECT_MERCHANT_STAFF,
    ).values_list('document_type', flat=True))
    required = staff_required_document_types(staff_member)
    if required == STAFF_IDENTITY_DOCUMENTS:
        if uploaded & STAFF_IDENTITY_DOCUMENTS:
            return []
        return ['At least one staff identity document is required.']
    missing_types = sorted(required - uploaded)
    if not missing_types:
        return []
    return [
        f'{document_type.replace("_", " ").title()} is required.'
        for document_type in missing_types
    ]


def mark_merchant_submitted(profile):
    if profile.is_verified:
        return
    profile.verification_status = VERIFICATION_SUBMITTED
    profile.verification_rejection_reason = ''
    profile.verification_submitted_at = timezone.now()
    profile.save(update_fields=(
        'verification_status',
        'verification_rejection_reason',
        'verification_submitted_at',
    ))
    notify_verification_event(profile, 'merchant_pending')


def mark_partner_submitted(partner):
    if partner.is_verified:
        return
    partner.verification_status = VERIFICATION_SUBMITTED
    partner.verification_rejection_reason = ''
    partner.verification_submitted_at = timezone.now()
    partner.save(update_fields=(
        'verification_status',
        'verification_rejection_reason',
        'verification_submitted_at',
    ))
    notify_verification_event(partner, 'partner_pending')


def mark_staff_submitted(staff_member):
    if staff_member.verification_status == staff_member.VERIFICATION_VERIFIED:
        return
    staff_member.verification_status = staff_member.VERIFICATION_SUBMITTED
    staff_member.verification_rejection_reason = ''
    staff_member.verification_submitted_at = timezone.now()
    staff_member.save(update_fields=(
        'verification_status',
        'verification_rejection_reason',
        'verification_submitted_at',
        'updated_at',
    ))
    notify_verification_event(staff_member, 'staff_pending')


def approve_merchant(profile, reviewer):
    now = timezone.now()
    profile.is_verified = True
    profile.verification_status = VERIFICATION_APPROVED
    profile.verification_rejection_reason = ''
    profile.verification_reviewed_at = now
    profile.verification_reviewed_by = reviewer
    profile.save(update_fields=(
        'is_verified',
        'verification_status',
        'verification_rejection_reason',
        'verification_reviewed_at',
        'verification_reviewed_by',
    ))
    VerificationDocument.objects.filter(
        user=profile.user,
        subject_type=SUBJECT_MERCHANT,
        status=STATUS_PENDING,
    ).update(status=STATUS_APPROVED, reviewed_by=reviewer, reviewed_at=now)
    notify_verification_event(profile, 'merchant_approved', actor=reviewer)


def approve_staff_member(staff_member, reviewer):
    now = timezone.now()
    staff_member.verification_status = staff_member.VERIFICATION_VERIFIED
    staff_member.verification_rejection_reason = ''
    staff_member.verification_reviewed_at = now
    staff_member.verification_reviewed_by = reviewer
    staff_member.save(update_fields=(
        'verification_status',
        'verification_rejection_reason',
        'verification_reviewed_at',
        'verification_reviewed_by',
        'updated_at',
    ))
    VerificationDocument.objects.filter(
        user=staff_member.user,
        subject_type=SUBJECT_MERCHANT_STAFF,
        status=STATUS_PENDING,
    ).update(status=STATUS_APPROVED, reviewed_by=reviewer, reviewed_at=now)
    notify_verification_event(staff_member, 'staff_approved', actor=reviewer)


def reject_merchant(profile, reviewer, reason):
    now = timezone.now()
    profile.is_verified = False
    profile.verification_status = VERIFICATION_REJECTED if reason else VERIFICATION_SUSPENDED
    profile.verification_rejection_reason = reason
    profile.verification_reviewed_at = now
    profile.verification_reviewed_by = reviewer
    profile.save(update_fields=(
        'is_verified',
        'verification_status',
        'verification_rejection_reason',
        'verification_reviewed_at',
        'verification_reviewed_by',
    ))
    notify_verification_event(profile, 'merchant_rejected', actor=reviewer)


def reject_staff_member(staff_member, reviewer, reason):
    now = timezone.now()
    staff_member.verification_status = (
        staff_member.VERIFICATION_REJECTED if reason
        else staff_member.VERIFICATION_SUSPENDED
    )
    staff_member.verification_rejection_reason = reason
    staff_member.verification_reviewed_at = now
    staff_member.verification_reviewed_by = reviewer
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
        'staff_rejected' if reason else 'staff_suspended',
        actor=reviewer,
    )


def approve_partner(partner, reviewer):
    now = timezone.now()
    partner.is_verified = True
    partner.is_available = not partner.deliveries.exclude(status='DELIVERED').exists()
    partner.verification_status = VERIFICATION_APPROVED
    partner.verification_rejection_reason = ''
    partner.verification_reviewed_at = now
    partner.verification_reviewed_by = reviewer
    partner.save(update_fields=(
        'is_verified',
        'is_available',
        'verification_status',
        'verification_rejection_reason',
        'verification_reviewed_at',
        'verification_reviewed_by',
    ))
    VerificationDocument.objects.filter(
        user=partner.user,
        subject_type=SUBJECT_PARTNER,
        status=STATUS_PENDING,
    ).update(status=STATUS_APPROVED, reviewed_by=reviewer, reviewed_at=now)
    notify_verification_event(partner, 'partner_approved', actor=reviewer)


def reject_partner(partner, reviewer, reason):
    now = timezone.now()
    partner.is_verified = False
    partner.is_available = False
    partner.verification_status = VERIFICATION_REJECTED if reason else VERIFICATION_SUSPENDED
    partner.verification_rejection_reason = reason
    partner.verification_reviewed_at = now
    partner.verification_reviewed_by = reviewer
    partner.save(update_fields=(
        'is_verified',
        'is_available',
        'verification_status',
        'verification_rejection_reason',
        'verification_reviewed_at',
        'verification_reviewed_by',
    ))
    notify_verification_event(partner, 'partner_rejected', actor=reviewer)


def review_document(document, reviewer, status, reason=''):
    document.status = status
    document.reviewed_by = reviewer
    document.reviewed_at = timezone.now()
    if status == STATUS_REJECTED:
        document.rejection_reason = reason
    elif status == STATUS_APPROVED:
        document.rejection_reason = ''
    document.save(update_fields=(
        'status',
        'reviewed_by',
        'reviewed_at',
        'rejection_reason',
        'updated_at',
    ))
    return document

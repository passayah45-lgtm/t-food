from secrets import token_urlsafe
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


def merchant_staff_invite_token():
    return token_urlsafe(32)


def merchant_staff_invite_expiry():
    return timezone.now() + timedelta(days=7)


class MerchantStaffMember(models.Model):
    ROLE_OWNER = 'OWNER'
    ROLE_ADMIN = 'ADMIN'
    ROLE_BRANCH_MANAGER = 'BRANCH_MANAGER'
    ROLE_KITCHEN_STAFF = 'KITCHEN_STAFF'
    ROLE_CASHIER = 'CASHIER'
    ROLE_DISPATCHER = 'DISPATCHER'
    ROLE_CUSTOMER_SUPPORT = 'CUSTOMER_SUPPORT'
    ROLE_FINANCE_STAFF = 'FINANCE_STAFF'
    ROLE_VIEWER = 'VIEWER'
    ROLE_CHOICES = [
        (ROLE_OWNER, 'Owner'),
        (ROLE_ADMIN, 'Admin'),
        (ROLE_BRANCH_MANAGER, 'Branch manager'),
        (ROLE_KITCHEN_STAFF, 'Kitchen staff'),
        (ROLE_CASHIER, 'Cashier'),
        (ROLE_DISPATCHER, 'Dispatcher'),
        (ROLE_CUSTOMER_SUPPORT, 'Customer support'),
        (ROLE_FINANCE_STAFF, 'Finance staff'),
        (ROLE_VIEWER, 'Viewer'),
    ]

    STATUS_INVITED = 'INVITED'
    STATUS_PENDING_VERIFICATION = 'PENDING_VERIFICATION'
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_INACTIVE = 'INACTIVE'
    STATUS_REMOVED = 'REMOVED'
    MEMBERSHIP_STATUS_CHOICES = [
        (STATUS_INVITED, 'Invited'),
        (STATUS_PENDING_VERIFICATION, 'Pending verification'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INACTIVE, 'Inactive'),
        (STATUS_REMOVED, 'Removed'),
    ]

    VERIFICATION_PENDING = 'PENDING'
    VERIFICATION_SUBMITTED = 'SUBMITTED'
    VERIFICATION_VERIFIED = 'VERIFIED'
    VERIFICATION_REJECTED = 'REJECTED'
    VERIFICATION_SUSPENDED = 'SUSPENDED'
    VERIFICATION_MORE_INFO_REQUIRED = 'MORE_INFO_REQUIRED'
    VERIFICATION_STATUS_CHOICES = [
        (VERIFICATION_PENDING, 'Pending'),
        (VERIFICATION_SUBMITTED, 'Submitted'),
        (VERIFICATION_VERIFIED, 'Verified'),
        (VERIFICATION_REJECTED, 'Rejected'),
        (VERIFICATION_SUSPENDED, 'Suspended'),
        (VERIFICATION_MORE_INFO_REQUIRED, 'More information required'),
    ]

    merchant = models.ForeignKey(
        'restaurants.MerchantProfile',
        on_delete=models.CASCADE,
        related_name='staff_members',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='merchant_staff_memberships',
    )
    role = models.CharField(
        max_length=32,
        choices=ROLE_CHOICES,
        default=ROLE_VIEWER,
    )
    membership_status = models.CharField(
        max_length=32,
        choices=MEMBERSHIP_STATUS_CHOICES,
        default=STATUS_INVITED,
    )
    verification_status = models.CharField(
        max_length=32,
        choices=VERIFICATION_STATUS_CHOICES,
        default=VERIFICATION_PENDING,
    )
    verification_rejection_reason = models.TextField(blank=True)
    verification_submitted_at = models.DateTimeField(null=True, blank=True)
    verification_reviewed_at = models.DateTimeField(null=True, blank=True)
    verification_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_merchant_staff_members',
    )
    is_company_wide = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_merchant_staff_members',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_merchant_staff_members',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('merchant__business_name', 'user__username', 'id')
        constraints = [
            models.UniqueConstraint(
                fields=('merchant', 'user'),
                condition=~Q(membership_status='REMOVED'),
                name='unique_current_staff_member_per_merchant_user',
            ),
            models.CheckConstraint(
                check=(
                    ~Q(membership_status='ACTIVE')
                    | Q(verification_status='VERIFIED')
                ),
                name='active_staff_requires_verified_identity',
            ),
        ]
        indexes = [
            models.Index(fields=('merchant', 'role', 'membership_status')),
            models.Index(fields=('merchant', 'verification_status')),
            models.Index(fields=('user', 'membership_status')),
        ]

    def __str__(self):
        return f'{self.user} - {self.merchant} ({self.role})'

    def clean(self):
        super().clean()
        if (
            self.membership_status == self.STATUS_ACTIVE
            and self.verification_status != self.VERIFICATION_VERIFIED
        ):
            raise ValidationError({
                'membership_status': (
                    'Staff cannot become active until T-Food Operations '
                    'verifies their identity.'
                ),
            })


class MerchantStaffBranchAccess(models.Model):
    staff_member = models.ForeignKey(
        MerchantStaffMember,
        on_delete=models.CASCADE,
        related_name='branch_access',
    )
    branch = models.ForeignKey(
        'restaurants.Restaurant',
        on_delete=models.CASCADE,
        related_name='staff_access',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_merchant_staff_branch_access',
    )

    class Meta:
        ordering = ('staff_member', 'branch__branch_name', 'id')
        constraints = [
            models.UniqueConstraint(
                fields=('staff_member', 'branch'),
                name='unique_staff_branch_access',
            ),
        ]
        indexes = [
            models.Index(fields=('branch', 'created_at')),
        ]

    def __str__(self):
        return f'{self.staff_member} -> {self.branch}'

    def clean(self):
        super().clean()
        if not self.staff_member_id or not self.branch_id:
            return
        staff = self.staff_member
        branch = self.branch
        if staff.membership_status == MerchantStaffMember.STATUS_REMOVED:
            raise ValidationError({
                'staff_member': 'Removed staff cannot be assigned to branches.',
            })
        if branch.owner_id != staff.merchant.user_id:
            raise ValidationError({
                'branch': 'Branch must belong to the same merchant company.',
            })


class MerchantStaffInvite(models.Model):
    STATUS_PENDING = 'PENDING'
    STATUS_ACCEPTED = 'ACCEPTED'
    STATUS_EXPIRED = 'EXPIRED'
    STATUS_CANCELLED = 'CANCELLED'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_EXPIRED, 'Expired'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    merchant = models.ForeignKey(
        'restaurants.MerchantProfile',
        on_delete=models.CASCADE,
        related_name='staff_invites',
    )
    name = models.CharField(max_length=120)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(
        max_length=32,
        choices=MerchantStaffMember.ROLE_CHOICES,
        default=MerchantStaffMember.ROLE_VIEWER,
    )
    is_company_wide = models.BooleanField(default=False)
    branches = models.ManyToManyField(
        'restaurants.Restaurant',
        blank=True,
        related_name='staff_invites',
    )
    invite_token = models.CharField(
        max_length=96,
        unique=True,
        default=merchant_staff_invite_token,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    expires_at = models.DateTimeField(default=merchant_staff_invite_expiry)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='merchant_staff_invites_sent',
    )
    linked_staff_member = models.ForeignKey(
        MerchantStaffMember,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='accepted_invites',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at', 'id')
        indexes = [
            models.Index(fields=('merchant', 'status')),
            models.Index(fields=('invite_token',)),
            models.Index(fields=('expires_at',)),
        ]

    def __str__(self):
        return f'{self.name} invited to {self.merchant}'

    def is_expired(self, now=None):
        return (
            self.status == self.STATUS_PENDING
            and self.expires_at <= (now or timezone.now())
        )

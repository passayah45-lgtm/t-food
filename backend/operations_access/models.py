from django.conf import settings
from django.db import models


class OperationsStaffProfile(models.Model):
    ROLE_GLOBAL_ADMIN = 'GLOBAL_ADMIN'
    ROLE_COUNTRY_ADMIN = 'COUNTRY_ADMIN'
    ROLE_CITY_ADMIN = 'CITY_ADMIN'
    ROLE_AREA_ADMIN = 'AREA_ADMIN'
    ROLE_OPERATIONS_STAFF = 'OPERATIONS_STAFF'
    ROLE_SUPPORT_STAFF = 'SUPPORT_STAFF'
    ROLE_FINANCE_STAFF = 'FINANCE_STAFF'
    ROLE_VERIFICATION_REVIEWER = 'VERIFICATION_REVIEWER'
    ROLE_DISPATCH_OPERATOR = 'DISPATCH_OPERATOR'
    ROLE_VIEWER = 'VIEWER'
    ROLE_CHOICES = [
        (ROLE_GLOBAL_ADMIN, 'Global admin'),
        (ROLE_COUNTRY_ADMIN, 'Country admin'),
        (ROLE_CITY_ADMIN, 'City admin'),
        (ROLE_AREA_ADMIN, 'Area admin'),
        (ROLE_OPERATIONS_STAFF, 'Operations staff'),
        (ROLE_SUPPORT_STAFF, 'Support staff'),
        (ROLE_FINANCE_STAFF, 'Finance staff'),
        (ROLE_VERIFICATION_REVIEWER, 'Verification reviewer'),
        (ROLE_DISPATCH_OPERATOR, 'Dispatch operator'),
        (ROLE_VIEWER, 'Viewer'),
    ]

    STATUS_ACTIVE = 'ACTIVE'
    STATUS_INACTIVE = 'INACTIVE'
    STATUS_SUSPENDED = 'SUSPENDED'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INACTIVE, 'Inactive'),
        (STATUS_SUSPENDED, 'Suspended'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='operations_staff_profile',
    )
    role = models.CharField(
        max_length=32,
        choices=ROLE_CHOICES,
        default=ROLE_OPERATIONS_STAFF,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )
    permissions = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_operations_staff_profiles',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_operations_staff_profiles',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('user__username', 'id')
        indexes = [
            models.Index(fields=('role', 'status')),
            models.Index(fields=('status', 'created_at')),
        ]

    def __str__(self):
        return f'{self.user} - {self.role}'


class OperationsStaffMarketAccess(models.Model):
    profile = models.ForeignKey(
        OperationsStaffProfile,
        on_delete=models.CASCADE,
        related_name='market_access',
    )
    market = models.ForeignKey(
        'markets.Market',
        on_delete=models.CASCADE,
        related_name='operations_staff_access',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_operations_market_access',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('profile', 'market__name', 'id')
        constraints = [
            models.UniqueConstraint(
                fields=('profile', 'market'),
                name='unique_operations_profile_market_access',
            ),
        ]
        indexes = [
            models.Index(fields=('market', 'created_at')),
        ]

    def __str__(self):
        return f'{self.profile} -> {self.market}'


class OperationsStaffCityAccess(models.Model):
    profile = models.ForeignKey(
        OperationsStaffProfile,
        on_delete=models.CASCADE,
        related_name='city_access',
    )
    city = models.ForeignKey(
        'markets.CommerceCity',
        on_delete=models.CASCADE,
        related_name='operations_staff_access',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_operations_city_access',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('profile', 'city__name', 'id')
        constraints = [
            models.UniqueConstraint(
                fields=('profile', 'city'),
                name='unique_operations_profile_city_access',
            ),
        ]
        indexes = [
            models.Index(fields=('city', 'created_at')),
        ]

    def __str__(self):
        return f'{self.profile} -> {self.city}'


class OperationsStaffAreaAccess(models.Model):
    profile = models.ForeignKey(
        OperationsStaffProfile,
        on_delete=models.CASCADE,
        related_name='area_access',
    )
    area = models.ForeignKey(
        'markets.CommerceArea',
        on_delete=models.CASCADE,
        related_name='operations_staff_access',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_operations_area_access',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('profile', 'area__name', 'id')
        constraints = [
            models.UniqueConstraint(
                fields=('profile', 'area'),
                name='unique_operations_profile_area_access',
            ),
        ]
        indexes = [
            models.Index(fields=('area', 'created_at')),
        ]

    def __str__(self):
        return f'{self.profile} -> {self.area}'


class OperationsAccessAudit(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='operations_access_audit_events',
    )
    action = models.CharField(max_length=80)
    target_type = models.CharField(max_length=80, blank=True)
    target_id = models.CharField(max_length=80, blank=True)
    scope_type = models.CharField(max_length=40, blank=True)
    scope_id = models.CharField(max_length=80, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-id')
        indexes = [
            models.Index(fields=('actor', 'created_at')),
            models.Index(fields=('action', 'created_at')),
            models.Index(fields=('scope_type', 'scope_id')),
        ]

    def __str__(self):
        return f'{self.action} by {self.actor or "system"}'


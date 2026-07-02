from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from markets.models import CommerceArea, CommerceCity, Market

from .config import legacy_global_operations_access_enabled
from .models import (
    OperationsAccessAudit,
    OperationsStaffAreaAccess,
    OperationsStaffCityAccess,
    OperationsStaffMarketAccess,
    OperationsStaffProfile,
)
from .permissions import (
    MANAGE_OPERATIONS_USERS,
    can_access_area,
    can_access_city,
    can_access_market,
    get_operations_actor,
    require_operations_permission,
)


User = get_user_model()


def _user_payload(user):
    full_name = user.get_full_name().strip()
    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'name': full_name or user.username,
        'is_active': user.is_active,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
    }


def _market_payload(access):
    market = access.market
    return {
        'id': market.id,
        'name': market.name,
        'slug': market.slug,
        'country_code': market.country_code,
        'currency': getattr(market.default_currency, 'code', ''),
    }


def _city_payload(access):
    city = access.city
    return {
        'id': city.id,
        'name': city.name,
        'slug': city.slug,
        'market_id': city.market_id,
        'market_name': city.market.name if city.market_id else '',
        'country_code': city.market.country_code if city.market_id else '',
    }


def _area_payload(access):
    area = access.area
    return {
        'id': area.id,
        'name': area.name,
        'slug': area.slug,
        'city_id': area.city_id,
        'city_name': area.city.name if area.city_id else '',
        'market_id': area.market_id,
        'market_name': area.market.name if area.market_id else '',
        'country_code': area.market.country_code if area.market_id else '',
    }


def serialize_operations_profile(profile):
    actor = get_operations_actor(profile.user)
    return {
        'id': profile.id,
        'user': _user_payload(profile.user),
        'role': profile.role,
        'status': profile.status,
        'permissions': sorted(profile.permissions or []),
        'effective_permissions': sorted(actor.permissions),
        'is_global_scope': bool(actor.is_global_scope),
        'assigned_markets': [
            _market_payload(access)
            for access in profile.market_access.select_related('market', 'market__default_currency').all()
        ],
        'assigned_cities': [
            _city_payload(access)
            for access in profile.city_access.select_related('city', 'city__market').all()
        ],
        'assigned_areas': [
            _area_payload(access)
            for access in profile.area_access.select_related('area', 'area__city', 'area__market').all()
        ],
        'created_at': profile.created_at,
        'updated_at': profile.updated_at,
        'created_by': _user_payload(profile.created_by) if profile.created_by_id else None,
        'updated_by': _user_payload(profile.updated_by) if profile.updated_by_id else None,
    }


def serialize_operations_actor(actor):
    return {
        'is_operations_user': bool(actor.permissions),
        'is_authenticated': bool(actor.is_authenticated),
        'is_superuser': bool(actor.is_superuser),
        'is_legacy_staff': bool(actor.is_legacy_staff),
        'has_profile': bool(actor.has_profile),
        'role': actor.role,
        'status': actor.status,
        'permissions': sorted(actor.permissions),
        'is_global_scope': bool(actor.is_global_scope),
        'assigned_market_ids': list(actor.assigned_market_ids),
        'assigned_country_codes': list(actor.assigned_country_codes),
        'assigned_city_ids': list(actor.assigned_city_ids),
        'assigned_area_ids': list(actor.assigned_area_ids),
        'legacy_compatibility_enabled': legacy_global_operations_access_enabled(),
    }


def audit_access_change(actor, action, profile, *, scope_type='', scope_id='', metadata=None):
    OperationsAccessAudit.objects.create(
        actor=actor.user if actor else None,
        action=action,
        target_type='OperationsStaffProfile',
        target_id=str(profile.id),
        scope_type=scope_type,
        scope_id=str(scope_id) if scope_id else '',
        metadata=metadata or {},
    )


def _managed_profiles_for_actor(actor):
    queryset = OperationsStaffProfile.objects.select_related(
        'user',
        'created_by',
        'updated_by',
    ).prefetch_related(
        'market_access__market__default_currency',
        'city_access__city__market',
        'area_access__area__city',
        'area_access__area__market',
    )
    if actor.is_global_scope:
        return queryset

    filters = {}
    if actor.assigned_area_ids:
        filters['area_access__area_id__in'] = actor.assigned_area_ids
    elif actor.assigned_city_ids:
        filters['city_access__city_id__in'] = actor.assigned_city_ids
    elif actor.assigned_market_ids:
        filters['market_access__market_id__in'] = actor.assigned_market_ids
    else:
        return queryset.none()
    return queryset.filter(**filters).distinct()


def _get_profile_for_actor(actor, profile_id):
    try:
        return _managed_profiles_for_actor(actor).get(id=profile_id)
    except OperationsStaffProfile.DoesNotExist as exc:
        raise NotFound('Operations user profile not found in your scope.') from exc


def _validate_can_manage_actor(actor):
    require_operations_permission(actor, MANAGE_OPERATIONS_USERS)
    if not actor.permissions:
        raise PermissionDenied('Inactive operations users cannot manage operations access.')


def _can_manage_global_admin(actor):
    return actor.is_superuser or (
        actor.has_profile
        and actor.is_global_scope
        and actor.role == OperationsStaffProfile.ROLE_GLOBAL_ADMIN
    )


class OperationsProfileWriteSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=False)
    username = serializers.CharField(max_length=150, required=False, allow_blank=False)
    email = serializers.EmailField(required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=OperationsStaffProfile.ROLE_CHOICES)
    status = serializers.ChoiceField(
        choices=OperationsStaffProfile.STATUS_CHOICES,
        default=OperationsStaffProfile.STATUS_ACTIVE,
    )
    permissions = serializers.ListField(
        child=serializers.CharField(max_length=80),
        required=False,
        allow_empty=True,
    )

    def validate(self, attrs):
        if not attrs.get('user_id') and not attrs.get('username'):
            raise serializers.ValidationError('Provide user_id or username.')
        return attrs


class OperationsProfilePatchSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=OperationsStaffProfile.ROLE_CHOICES, required=False)
    status = serializers.ChoiceField(choices=OperationsStaffProfile.STATUS_CHOICES, required=False)
    permissions = serializers.ListField(
        child=serializers.CharField(max_length=80),
        required=False,
        allow_empty=True,
    )


class ScopeAssignmentSerializer(serializers.Serializer):
    market_id = serializers.IntegerField(required=False)
    city_id = serializers.IntegerField(required=False)
    area_id = serializers.IntegerField(required=False)


class OperationsAccessMeView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        actor = get_operations_actor(request.user)
        return Response(serialize_operations_actor(actor))


class OperationsAccessStaffListCreateView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        actor = get_operations_actor(request.user)
        _validate_can_manage_actor(actor)
        profiles = _managed_profiles_for_actor(actor)
        return Response([serialize_operations_profile(profile) for profile in profiles])

    @transaction.atomic
    def post(self, request):
        actor = get_operations_actor(request.user)
        _validate_can_manage_actor(actor)
        serializer = OperationsProfileWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data['role'] == OperationsStaffProfile.ROLE_GLOBAL_ADMIN and not _can_manage_global_admin(actor):
            raise PermissionDenied('Only a superuser or Global Admin can create Global Admin profiles.')

        if data.get('user_id'):
            try:
                user = User.objects.get(id=data['user_id'])
            except User.DoesNotExist as exc:
                raise NotFound('User not found.') from exc
        else:
            user, created = User.objects.get_or_create(username=data['username'])
            if created:
                user.set_unusable_password()

        if hasattr(user, 'operations_staff_profile'):
            raise serializers.ValidationError({'user_id': ['This user already has an operations profile.']})

        user.email = data.get('email', user.email)
        user.first_name = data.get('first_name', user.first_name)
        user.last_name = data.get('last_name', user.last_name)
        user.is_staff = True
        user.save()

        profile = OperationsStaffProfile.objects.create(
            user=user,
            role=data['role'],
            status=data['status'],
            permissions=data.get('permissions', []),
            created_by=request.user,
            updated_by=request.user,
        )
        audit_access_change(actor, 'CREATE_OPERATIONS_PROFILE', profile, metadata={'role': profile.role})
        return Response(serialize_operations_profile(profile), status=status.HTTP_201_CREATED)


class OperationsAccessStaffDetailView(APIView):
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def patch(self, request, profile_id):
        actor = get_operations_actor(request.user)
        _validate_can_manage_actor(actor)
        profile = _get_profile_for_actor(actor, profile_id)
        serializer = OperationsProfilePatchSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if (
            data.get('role') == OperationsStaffProfile.ROLE_GLOBAL_ADMIN
            and profile.role != OperationsStaffProfile.ROLE_GLOBAL_ADMIN
            and not _can_manage_global_admin(actor)
        ):
            raise PermissionDenied('Only a superuser or Global Admin can promote Global Admin profiles.')

        user_updates = []
        for field in ('email', 'first_name', 'last_name'):
            if field in data:
                setattr(profile.user, field, data[field])
                user_updates.append(field)
        if user_updates:
            profile.user.save(update_fields=user_updates)

        profile_updates = ['updated_by']
        for field in ('role', 'status', 'permissions'):
            if field in data:
                setattr(profile, field, data[field])
                profile_updates.append(field)
        profile.updated_by = request.user
        profile.save(update_fields=profile_updates + ['updated_at'])
        audit_access_change(actor, 'UPDATE_OPERATIONS_PROFILE', profile, metadata=data)
        return Response(serialize_operations_profile(profile))


class OperationsAccessScopeView(APIView):
    permission_classes = [IsAdminUser]
    scope_type = ''

    def _get_object(self, request):
        serializer = ScopeAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if self.scope_type == 'market':
            object_id = data.get('market_id')
            model = Market
        elif self.scope_type == 'city':
            object_id = data.get('city_id')
            model = CommerceCity
        else:
            object_id = data.get('area_id')
            model = CommerceArea
        if not object_id:
            raise serializers.ValidationError({f'{self.scope_type}_id': ['This field is required.']})
        try:
            return model.objects.get(id=object_id)
        except model.DoesNotExist as exc:
            raise NotFound(f'{self.scope_type.title()} not found.') from exc

    def _validate_scope_access(self, actor, obj):
        if self.scope_type == 'market' and not can_access_market(actor, obj):
            raise PermissionDenied('You cannot assign markets outside your scope.')
        if self.scope_type == 'city' and not can_access_city(actor, obj):
            raise PermissionDenied('You cannot assign cities outside your scope.')
        if self.scope_type == 'area' and not can_access_area(actor, obj):
            raise PermissionDenied('You cannot assign areas outside your scope.')

    @transaction.atomic
    def post(self, request, profile_id):
        actor = get_operations_actor(request.user)
        _validate_can_manage_actor(actor)
        profile = _get_profile_for_actor(actor, profile_id)
        obj = self._get_object(request)
        self._validate_scope_access(actor, obj)

        if self.scope_type == 'market':
            OperationsStaffMarketAccess.objects.get_or_create(
                profile=profile,
                market=obj,
                defaults={'created_by': request.user},
            )
        elif self.scope_type == 'city':
            OperationsStaffCityAccess.objects.get_or_create(
                profile=profile,
                city=obj,
                defaults={'created_by': request.user},
            )
        else:
            OperationsStaffAreaAccess.objects.get_or_create(
                profile=profile,
                area=obj,
                defaults={'created_by': request.user},
            )
        audit_access_change(
            actor,
            f'ASSIGN_{self.scope_type.upper()}_ACCESS',
            profile,
            scope_type=self.scope_type.upper(),
            scope_id=obj.id,
        )
        return Response(serialize_operations_profile(profile))

    @transaction.atomic
    def delete(self, request, profile_id, object_id):
        actor = get_operations_actor(request.user)
        _validate_can_manage_actor(actor)
        profile = _get_profile_for_actor(actor, profile_id)

        if self.scope_type == 'market':
            try:
                obj = Market.objects.get(id=object_id)
            except Market.DoesNotExist as exc:
                raise NotFound('Market not found.') from exc
            self._validate_scope_access(actor, obj)
            OperationsStaffMarketAccess.objects.filter(profile=profile, market=obj).delete()
        elif self.scope_type == 'city':
            try:
                obj = CommerceCity.objects.get(id=object_id)
            except CommerceCity.DoesNotExist as exc:
                raise NotFound('City not found.') from exc
            self._validate_scope_access(actor, obj)
            OperationsStaffCityAccess.objects.filter(profile=profile, city=obj).delete()
        else:
            try:
                obj = CommerceArea.objects.get(id=object_id)
            except CommerceArea.DoesNotExist as exc:
                raise NotFound('Area not found.') from exc
            self._validate_scope_access(actor, obj)
            OperationsStaffAreaAccess.objects.filter(profile=profile, area=obj).delete()

        audit_access_change(
            actor,
            f'REMOVE_{self.scope_type.upper()}_ACCESS',
            profile,
            scope_type=self.scope_type.upper(),
            scope_id=obj.id,
        )
        return Response(serialize_operations_profile(profile))


class OperationsAccessMarketScopeView(OperationsAccessScopeView):
    scope_type = 'market'


class OperationsAccessCityScopeView(OperationsAccessScopeView):
    scope_type = 'city'


class OperationsAccessAreaScopeView(OperationsAccessScopeView):
    scope_type = 'area'

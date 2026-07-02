from django.contrib.auth.models import User
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from merchant_staff.permissions import get_merchant_actor
from operations_access.config import legacy_global_operations_access_enabled
from operations_access.permissions import get_operations_actor
from user_preferences.serializers import UserPreferenceSerializer
from user_preferences.services import ensure_user_preference
from .serializers import RegisterSerializer, UserSerializer


def get_user_role(user):
    if user.is_staff:
        return 'admin'
    if hasattr(user, 'merchant_profile'):
        return 'merchant'
    if hasattr(user, 'delivery_partner'):
        return 'partner'
    return 'customer'


def merchant_auth_context(user):
    actor = get_merchant_actor(user)
    is_owner = bool(actor.is_owner)
    is_eligible_staff = bool(actor.is_staff and actor.permissions)
    return {
        'is_merchant_owner': is_owner,
        'is_merchant_staff': is_eligible_staff,
        'merchant_id': actor.merchant_id if (is_owner or is_eligible_staff) else None,
        'staff_member_id': (
            actor.staff_member.id
            if is_eligible_staff and actor.staff_member else None
        ),
        'staff_role': actor.role if is_eligible_staff else '',
        'membership_status': actor.membership_status,
        'verification_status': actor.verification_status,
        'is_company_wide': bool(
            actor.is_company_wide if (is_owner or is_eligible_staff) else False
        ),
        'branch_ids': list(actor.branch_ids) if (is_owner or is_eligible_staff) else [],
        'permissions': sorted(actor.permissions) if (is_owner or is_eligible_staff) else [],
    }


def operations_auth_context(user):
    actor = get_operations_actor(user)
    is_operations_user = bool(actor.permissions)
    return {
        'is_operations_user': is_operations_user,
        'operations_role': actor.role,
        'operations_status': actor.status,
        'operations_permissions': sorted(actor.permissions),
        'operations_is_global_scope': bool(actor.is_global_scope),
        'operations_market_ids': list(actor.assigned_market_ids),
        'operations_country_codes': list(actor.assigned_country_codes),
        'operations_city_ids': list(actor.assigned_city_ids),
        'operations_area_ids': list(actor.assigned_area_ids),
        'operations_is_legacy_staff': bool(actor.is_legacy_staff),
        'operations_legacy_compatibility_enabled': legacy_global_operations_access_enabled(),
    }


def preference_auth_context(user):
    preference = ensure_user_preference(user)
    data = UserPreferenceSerializer(preference).data if preference else None
    return {
        'preferences': data,
        'preference_version': (
            preference.preference_version if preference else None
        ),
    }


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adds user info to the login response alongside the tokens."""
    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = UserSerializer(self.user).data
        # Include role
        data['role'] = get_user_role(self.user)
        data.update(merchant_auth_context(self.user))
        data.update(operations_auth_context(self.user))
        data.update(preference_auth_context(self.user))
        return data


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth_register'

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Return tokens immediately after registration
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'role': get_user_role(user),
            **merchant_auth_context(user),
            **operations_auth_context(user),
            **preference_auth_context(user),
            'access':  str(refresh.access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth_login'


class RefreshView(TokenRefreshView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth_refresh'


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({'detail': 'Logged out successfully.'}, status=status.HTTP_200_OK)
        except Exception:
            return Response({'detail': 'Invalid token.'}, status=status.HTTP_400_BAD_REQUEST)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            'user': UserSerializer(user).data,
            'role': get_user_role(user),
            **merchant_auth_context(user),
            **operations_auth_context(user),
            **preference_auth_context(user),
        })


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'

    def post(self, request):
        email = request.data.get('email', '').strip()
        user = User.objects.filter(
            email__iexact=email,
            is_active=True,
        ).first()
        if user and user.has_usable_password():
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = f'{settings.PUBLIC_APP_URL}/reset-password/{uid}/{token}'
            send_mail(
                subject='Reset your T-Food password',
                message=(
                    f'Hello {user.get_full_name() or user.username},\n\n'
                    f'Use this link to reset your T-Food password:\n{reset_url}\n\n'
                    'If you did not request this, you can ignore this email.'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
            )
        return Response({
            'detail': 'If that email is registered, a reset link has been sent.'
        })


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset_confirm'

    def post(self, request):
        uid = request.data.get('uid', '')
        token = request.data.get('token', '')
        password = request.data.get('password', '')
        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(id=user_id, is_active=True)
        except (ValueError, TypeError, OverflowError, User.DoesNotExist):
            user = None

        if not user or not default_token_generator.check_token(user, token):
            return Response(
                {'detail': 'This reset link is invalid or expired.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            validate_password(password, user)
        except ValidationError as error:
            return Response(
                {'password': list(error.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(password)
        user.save(update_fields=['password'])
        return Response({'detail': 'Password reset successfully.'})

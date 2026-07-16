import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import redirect
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.text import slugify
from customers.models import Customer
from delivery.models import DeliveryPartner
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
from restaurants.models import MerchantProfile
from user_preferences.serializers import UserPreferenceSerializer
from user_preferences.services import ensure_user_preference
from .serializers import RegisterSerializer, UserSerializer

GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://openidconnect.googleapis.com/v1/userinfo'
GOOGLE_OAUTH_STATE_SALT = 't-food.google-oauth-state'
GOOGLE_ROLES = {'customer', 'partner', 'merchant'}


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


def google_oauth_configured():
    return bool(
        settings.GOOGLE_OAUTH_ENABLED
        and settings.GOOGLE_OAUTH_CLIENT_ID
        and settings.GOOGLE_OAUTH_CLIENT_SECRET
    )


def google_redirect_uri():
    return settings.GOOGLE_OAUTH_REDIRECT_URI or (
        f'{settings.PUBLIC_APP_URL}/api/v1/auth/google/callback/'
    )


def safe_next_path(value):
    if not value or not value.startswith('/') or value.startswith('//'):
        return '/'
    return value[:300]


def make_unique_username(email, name=''):
    base = slugify((email.split('@')[0] if email else '') or name or 'tfood-user')
    base = re.sub(r'[^a-zA-Z0-9_.@+-]', '', base.replace('-', '.')) or 'tfood.user'
    candidate = base[:140]
    suffix = 2
    while User.objects.filter(username__iexact=candidate).exists():
        tail = str(suffix)
        candidate = f'{base[:140 - len(tail)]}{tail}'
        suffix += 1
    return candidate


def ensure_role_profile(user, role):
    if role == 'partner':
        DeliveryPartner.objects.get_or_create(
            user=user,
            defaults={
                'partner_name': user.get_full_name() or user.username,
                'partner_phone': '',
                'transport_details': '',
            },
        )
    elif role == 'merchant':
        MerchantProfile.objects.get_or_create(
            user=user,
            defaults={'business_name': user.get_full_name() or user.username},
        )
    else:
        Customer.objects.get_or_create(user=user)


def auth_payload_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'user': UserSerializer(user).data,
        'role': get_user_role(user),
        **merchant_auth_context(user),
        **operations_auth_context(user),
        **preference_auth_context(user),
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }


def _post_json(url, payload, timeout=None):
    data = urlencode(payload).encode('utf-8')
    request = Request(
        url,
        data=data,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST',
    )
    with urlopen(request, timeout=timeout or settings.GOOGLE_OAUTH_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode('utf-8'))


def _get_json(url, headers=None, timeout=None):
    request = Request(url, headers=headers or {}, method='GET')
    with urlopen(request, timeout=timeout or settings.GOOGLE_OAUTH_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode('utf-8'))


def _exchange_google_code(code):
    return _post_json(GOOGLE_TOKEN_URL, {
        'code': code,
        'client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
        'client_secret': settings.GOOGLE_OAUTH_CLIENT_SECRET,
        'redirect_uri': google_redirect_uri(),
        'grant_type': 'authorization_code',
    })


def _fetch_google_userinfo(access_token):
    return _get_json(
        GOOGLE_USERINFO_URL,
        headers={'Authorization': f'Bearer {access_token}'},
    )


class GoogleOAuthConfigView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({
            'enabled': google_oauth_configured(),
            'start_url': '/api/v1/auth/google/start/',
        })


class GoogleOAuthStartView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth_google_start'

    def get(self, request):
        if not google_oauth_configured():
            return Response(
                {'detail': 'Google sign-in is not enabled.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        role = request.query_params.get('role', 'customer')
        if role not in GOOGLE_ROLES:
            role = 'customer'
        state = signing.dumps(
            {
                'role': role,
                'next': safe_next_path(request.query_params.get('next', '/')),
            },
            salt=GOOGLE_OAUTH_STATE_SALT,
        )
        params = {
            'client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
            'redirect_uri': google_redirect_uri(),
            'response_type': 'code',
            'scope': 'openid email profile',
            'state': state,
            'prompt': 'select_account',
            'access_type': 'online',
        }
        return redirect(f'{GOOGLE_AUTH_URL}?{urlencode(params)}')


class GoogleOAuthCallbackView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth_google_callback'

    def get(self, request):
        if not google_oauth_configured():
            return Response(
                {'detail': 'Google sign-in is not enabled.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        code = request.query_params.get('code')
        state = request.query_params.get('state')
        if not code or not state:
            return Response(
                {'detail': 'Google sign-in response is incomplete.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            state_data = signing.loads(
                state,
                salt=GOOGLE_OAUTH_STATE_SALT,
                max_age=600,
            )
            token_data = _exchange_google_code(code)
            userinfo = _fetch_google_userinfo(token_data.get('access_token', ''))
        except signing.BadSignature:
            return Response(
                {'detail': 'Google sign-in state is invalid or expired.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except (HTTPError, URLError, TimeoutError, ValueError, KeyError):
            return Response(
                {'detail': 'Google sign-in could not be completed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = (userinfo.get('email') or '').strip().lower()
        if not email or not userinfo.get('email_verified'):
            return Response(
                {'detail': 'Google account email must be verified.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        role = state_data.get('role') if state_data.get('role') in GOOGLE_ROLES else 'customer'
        with transaction.atomic():
            user = User.objects.filter(email__iexact=email).first()
            if not user:
                user = User(
                    username=make_unique_username(email, userinfo.get('name', '')),
                    email=email,
                    first_name=(userinfo.get('given_name') or '')[:150],
                    last_name=(userinfo.get('family_name') or '')[:150],
                    is_active=True,
                )
                user.set_unusable_password()
                user.save()
                ensure_role_profile(user, role)
            elif not user.is_active:
                return Response(
                    {'detail': 'This account is inactive.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        payload = auth_payload_for_user(user)
        next_path = safe_next_path(state_data.get('next', '/'))
        fragment = urlencode({
            'access': payload['access'],
            'refresh': payload['refresh'],
            'next': next_path,
        })
        return redirect(f'{settings.PUBLIC_APP_URL}/auth/google/callback#{fragment}')


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
        if user:
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

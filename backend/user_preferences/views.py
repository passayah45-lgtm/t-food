from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    AccountAvatarSerializer,
    PreferenceOptionsSerializer,
    UserPreferenceSerializer,
)
from .services import ensure_user_preference


class UserPreferenceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        preference = ensure_user_preference(request.user)
        return Response(UserPreferenceSerializer(preference).data)

    def patch(self, request):
        preference = ensure_user_preference(request.user)
        serializer = UserPreferenceSerializer(
            preference,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class UserPreferenceOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(PreferenceOptionsSerializer({}).data)


class AccountAvatarView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        preference = ensure_user_preference(request.user)
        return Response(AccountAvatarSerializer(preference).data)

    def patch(self, request):
        preference = ensure_user_preference(request.user)
        serializer = AccountAvatarSerializer(
            preference,
            data=request.data,
            partial=True,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

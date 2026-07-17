from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db import transaction
from customers.models import Customer, DeliveryAddress
from delivery.models import DeliveryPartner
from .serializers import (
    CustomerProfileSerializer,
    DeliveryAddressSerializer,
    DeliveryPartnerProfileSerializer,
)


class CustomerProfileView(generics.RetrieveUpdateAPIView):
    """GET or PATCH the logged-in customer's profile. Supports avatar upload."""
    serializer_class = CustomerProfileSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_object(self):
        profile, _ = Customer.objects.get_or_create(user=self.request.user)
        return profile


class DeliveryPartnerProfileView(generics.RetrieveUpdateAPIView):
    """GET or PATCH the logged-in delivery partner's profile."""
    serializer_class = DeliveryPartnerProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        try:
            return self.request.user.delivery_partner
        except DeliveryPartner.DoesNotExist:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('You are not a delivery partner.')


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')

        if user.has_usable_password() and not user.check_password(old_password):
            return Response({'old_password': 'Incorrect password.'}, status=status.HTTP_400_BAD_REQUEST)

        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        try:
            validate_password(new_password, user)
        except ValidationError as e:
            return Response({'new_password': list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        return Response({'detail': 'Password updated successfully.', 'has_usable_password': True})


class DeliveryAddressListCreateView(generics.ListCreateAPIView):
    serializer_class = DeliveryAddressSerializer

    def get_queryset(self):
        return DeliveryAddress.objects.filter(user=self.request.user)

    @transaction.atomic
    def perform_create(self, serializer):
        addresses = DeliveryAddress.objects.select_for_update().filter(
            user=self.request.user
        )
        if addresses.count() >= 10:
            from rest_framework.exceptions import ValidationError
            raise ValidationError('You can save up to 10 delivery addresses.')
        make_default = serializer.validated_data.get('is_default') or not addresses.exists()
        if make_default:
            addresses.update(is_default=False)
        serializer.save(user=self.request.user, is_default=make_default)


class DeliveryAddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = DeliveryAddressSerializer

    def get_queryset(self):
        return DeliveryAddress.objects.filter(user=self.request.user)

    @transaction.atomic
    def perform_update(self, serializer):
        was_default = serializer.instance.is_default
        if serializer.validated_data.get('is_default'):
            DeliveryAddress.objects.select_for_update().filter(
                user=self.request.user
            ).exclude(id=serializer.instance.id).update(is_default=False)
        address = serializer.save()
        if was_default and not address.is_default:
            replacement = DeliveryAddress.objects.filter(
                user=self.request.user
            ).exclude(id=address.id).order_by('-updated_at').first()
            if replacement:
                replacement.is_default = True
                replacement.save(update_fields=['is_default', 'updated_at'])
            else:
                address.is_default = True
                address.save(update_fields=['is_default', 'updated_at'])

    @transaction.atomic
    def perform_destroy(self, instance):
        was_default = instance.is_default
        instance.delete()
        if was_default:
            replacement = DeliveryAddress.objects.filter(
                user=self.request.user
            ).order_by('-updated_at').first()
            if replacement:
                replacement.is_default = True
                replacement.save(update_fields=['is_default', 'updated_at'])

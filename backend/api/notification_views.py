from datetime import datetime, time

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_time
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import generics, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.models import (
    Notification,
    NotificationDevice,
    NotificationPreference,
)
from notifications.preferences import ensure_default_preferences


SENSITIVE_METADATA_FRAGMENTS = (
    'password',
    'secret',
    'credential',
    'token',
    'api_key',
    'private_key',
)


def _metadata_is_sensitive(key):
    normalized = str(key).lower()
    return any(fragment in normalized for fragment in SENSITIVE_METADATA_FRAGMENTS)


def sanitize_metadata(value):
    if isinstance(value, dict):
        return {
            key: sanitize_metadata(item)
            for key, item in value.items()
            if not _metadata_is_sensitive(key)
        }
    if isinstance(value, list):
        return [sanitize_metadata(item) for item in value]
    return value


def truthy(value):
    return str(value).lower() in {'1', 'true', 'yes', 'y', 'on'}


def parse_bound(value, *, end=False):
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        parsed_date = parse_date(value)
        if not parsed_date:
            return None
        if end:
            parsed = datetime.combine(parsed_date, time.max)
        else:
            parsed = datetime.combine(parsed_date, time.min)
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


class NotificationSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(read_only=True, allow_null=True)
    market = serializers.IntegerField(source='market_id', read_only=True, allow_null=True)
    market_name = serializers.CharField(source='market.name', read_only=True, allow_null=True)
    city = serializers.IntegerField(source='city_id', read_only=True, allow_null=True)
    area = serializers.IntegerField(source='area_id', read_only=True, allow_null=True)
    branch = serializers.IntegerField(source='branch_id', read_only=True, allow_null=True)
    branch_name = serializers.SerializerMethodField()
    metadata = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = (
            'id', 'kind', 'title', 'message', 'order_id',
            'is_read', 'created_at',
            'recipient_type', 'category', 'event_type', 'priority', 'status',
            'action_url', 'metadata', 'expires_at', 'auto_archive_after',
            'country_code', 'city', 'area', 'branch', 'branch_name',
            'market', 'market_name',
        )

    def get_branch_name(self, obj):
        if not obj.branch:
            return ''
        return obj.branch.branch_name or obj.branch.rest_name

    def get_metadata(self, obj):
        return sanitize_metadata(obj.metadata or {})


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    is_active_channel = serializers.BooleanField(read_only=True)
    effective_enabled = serializers.BooleanField(read_only=True)

    class Meta:
        model = NotificationPreference
        fields = (
            'id', 'category', 'channel', 'enabled',
            'quiet_hours_enabled', 'quiet_hours_start', 'quiet_hours_end',
            'language', 'is_active_channel', 'effective_enabled',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')


class NotificationPreferencePatchSerializer(serializers.Serializer):
    preferences = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
    )

    def validate_preferences(self, preferences):
        categories = {choice[0] for choice in Notification.CATEGORY_CHOICES}
        channels = {choice[0] for choice in NotificationPreference.CHANNEL_CHOICES}
        cleaned = []
        for preference in preferences:
            category = str(preference.get('category', '')).upper()
            channel = str(preference.get('channel', '')).upper()
            if category not in categories:
                raise serializers.ValidationError(
                    f'Unsupported notification category: {category}.'
                )
            if channel not in channels:
                raise serializers.ValidationError(
                    f'Unsupported notification channel: {channel}.'
                )
            item = {'category': category, 'channel': channel}
            if 'enabled' in preference:
                item['enabled'] = self.parse_bool(preference['enabled'], 'enabled')
            if 'quiet_hours_enabled' in preference:
                item['quiet_hours_enabled'] = self.parse_bool(
                    preference['quiet_hours_enabled'],
                    'quiet_hours_enabled',
                )
            if 'quiet_hours_start' in preference:
                item['quiet_hours_start'] = self.parse_optional_time(
                    preference.get('quiet_hours_start'),
                    'quiet_hours_start',
                )
            if 'quiet_hours_end' in preference:
                item['quiet_hours_end'] = self.parse_optional_time(
                    preference.get('quiet_hours_end'),
                    'quiet_hours_end',
                )
            if 'language' in preference:
                language = str(preference.get('language') or 'en').strip()[:12]
                item['language'] = language or 'en'
            cleaned.append(item)
        return cleaned

    def parse_bool(self, value, field):
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized in {'1', 'true', 'yes', 'y', 'on'}:
            return True
        if normalized in {'0', 'false', 'no', 'n', 'off'}:
            return False
        raise serializers.ValidationError(f'{field} must be a boolean.')

    def parse_optional_time(self, value, field):
        if value in (None, ''):
            return None
        parsed = parse_time(str(value))
        if parsed is None:
            raise serializers.ValidationError(f'{field} must be HH:MM[:ss].')
        return parsed


class NotificationDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationDevice
        fields = (
            'id', 'device_type', 'device_identifier', 'push_token',
            'is_active', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'is_active', 'created_at', 'updated_at')
        extra_kwargs = {
            'push_token': {'required': False, 'allow_blank': True, 'allow_null': True},
        }

    def validate_device_type(self, value):
        return str(value).upper()

    def validate_device_identifier(self, value):
        value = str(value or '').strip()
        if not value:
            raise serializers.ValidationError('Device identifier is required.')
        return value


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        queryset = (
            Notification.objects
            .filter(user=self.request.user)
            .select_related('order', 'market', 'city', 'area', 'branch')
        )
        params = self.request.query_params
        status_filter = params.get('status')
        if status_filter:
            statuses = [
                value.strip().upper()
                for value in status_filter.split(',')
                if value.strip()
            ]
            queryset = queryset.filter(status__in=statuses)
        else:
            queryset = queryset.exclude(status__in=[
                Notification.STATUS_ARCHIVED,
                Notification.STATUS_DISMISSED,
            ])

        if not truthy(params.get('include_expired')):
            now = timezone.now()
            queryset = queryset.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))

        if params.get('category'):
            queryset = queryset.filter(category=params['category'].upper())
        if params.get('priority'):
            queryset = queryset.filter(priority=params['priority'].upper())
        if params.get('event_type'):
            queryset = queryset.filter(event_type=params['event_type'])
        if params.get('unread') is not None:
            if truthy(params.get('unread')):
                queryset = queryset.filter(
                    Q(status=Notification.STATUS_UNREAD) | Q(is_read=False)
                )
            else:
                queryset = queryset.exclude(
                    Q(status=Notification.STATUS_UNREAD) | Q(is_read=False)
                )

        date_from = parse_bound(params.get('date_from'))
        date_to = parse_bound(params.get('date_to'), end=True)
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        return queryset


class NotificationPreferenceView(APIView):
    def get(self, request):
        ensure_default_preferences(request.user)
        preferences = NotificationPreference.objects.filter(
            user=request.user,
        ).order_by('category', 'channel')
        return Response({
            'active_channels': sorted(NotificationPreference.ACTIVE_CHANNELS),
            'future_channels_inactive': [
                channel
                for channel, _label in NotificationPreference.CHANNEL_CHOICES
                if channel not in NotificationPreference.ACTIVE_CHANNELS
            ],
            'results': NotificationPreferenceSerializer(
                preferences,
                many=True,
            ).data,
        })

    def patch(self, request):
        ensure_default_preferences(request.user)
        serializer = NotificationPreferencePatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = []
        for item in serializer.validated_data.get('preferences', []):
            preference, _ = NotificationPreference.objects.get_or_create(
                user=request.user,
                category=item['category'],
                channel=item['channel'],
            )
            update_fields = []
            for field in (
                'enabled', 'quiet_hours_enabled', 'quiet_hours_start',
                'quiet_hours_end', 'language',
            ):
                if field in item:
                    setattr(preference, field, item[field])
                    update_fields.append(field)
            if update_fields:
                preference.save(update_fields=update_fields + ['updated_at'])
            updated.append(preference)
        preferences = NotificationPreference.objects.filter(
            user=request.user,
        ).order_by('category', 'channel')
        return Response({
            'updated': len(updated),
            'results': NotificationPreferenceSerializer(
                preferences,
                many=True,
            ).data,
        })


class NotificationDeviceListCreateView(APIView):
    def get(self, request):
        devices = NotificationDevice.objects.filter(
            user=request.user,
        ).order_by('-updated_at', '-created_at')
        return Response({
            'results': NotificationDeviceSerializer(devices, many=True).data,
            'push_active': False,
            'message': 'Push devices are registered for future use. Push delivery is not active yet.',
        })

    def post(self, request):
        serializer = NotificationDeviceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        device, created = NotificationDevice.objects.get_or_create(
            user=request.user,
            device_identifier=data['device_identifier'],
            defaults={
                'device_type': data['device_type'],
                'push_token': data.get('push_token') or '',
                'is_active': True,
            },
        )
        if not created:
            device.device_type = data['device_type']
            device.push_token = data.get('push_token') or ''
            device.is_active = True
            device.save(update_fields=(
                'device_type', 'push_token', 'is_active', 'updated_at',
            ))
        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(
            NotificationDeviceSerializer(device).data,
            status=response_status,
        )


class NotificationDeviceDeleteView(APIView):
    def delete(self, request, device_id):
        updated = NotificationDevice.objects.filter(
            id=device_id,
            user=request.user,
        ).update(is_active=False)
        if not updated:
            return Response(
                {'detail': 'Device not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationUnreadView(APIView):
    def get(self, request):
        now = timezone.now()
        return Response({
            'unread_count': Notification.objects.filter(
                user=request.user,
            ).filter(
                Q(status=Notification.STATUS_UNREAD) | Q(is_read=False),
            ).exclude(
                status__in=[
                    Notification.STATUS_ARCHIVED,
                    Notification.STATUS_DISMISSED,
                ],
            ).filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=now),
            ).count()
        })


class NotificationReadView(APIView):
    def patch(self, request, notification_id):
        updated = Notification.objects.filter(
            id=notification_id,
            user=request.user,
        ).update(is_read=True, status=Notification.STATUS_READ)
        if not updated:
            return Response(
                {'detail': 'Notification not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({'detail': 'Notification marked as read.'})

    def post(self, request, notification_id):
        return self.patch(request, notification_id)


class NotificationReadAllView(APIView):
    def post(self, request):
        updated = Notification.objects.filter(
            user=request.user,
        ).filter(
            Q(status=Notification.STATUS_UNREAD) | Q(is_read=False),
        ).update(is_read=True, status=Notification.STATUS_READ)
        return Response({'updated': updated})


class NotificationArchiveView(APIView):
    def patch(self, request, notification_id):
        updated = Notification.objects.filter(
            id=notification_id,
            user=request.user,
        ).update(is_read=True, status=Notification.STATUS_ARCHIVED)
        if not updated:
            return Response(
                {'detail': 'Notification not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({'detail': 'Notification archived.'})


class NotificationDismissView(APIView):
    def patch(self, request, notification_id):
        updated = Notification.objects.filter(
            id=notification_id,
            user=request.user,
        ).update(is_read=True, status=Notification.STATUS_DISMISSED)
        if not updated:
            return Response(
                {'detail': 'Notification not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({'detail': 'Notification dismissed.'})


class NotificationArchiveReadView(APIView):
    def post(self, request):
        updated = Notification.objects.filter(
            user=request.user,
            is_read=True,
            status=Notification.STATUS_READ,
        ).update(status=Notification.STATUS_ARCHIVED)
        return Response({'updated': updated})


class NotificationMarkByFilterView(APIView):
    allowed_actions = {
        'read': (True, Notification.STATUS_READ),
        'archive': (True, Notification.STATUS_ARCHIVED),
        'dismiss': (True, Notification.STATUS_DISMISSED),
    }

    def post(self, request):
        action = str(request.data.get('action', '')).lower()
        if action not in self.allowed_actions:
            return Response(
                {'detail': 'Unsupported action.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        view = NotificationListView()
        view.request = request
        queryset = view.get_queryset()
        is_read, new_status = self.allowed_actions[action]
        updated = queryset.update(is_read=is_read, status=new_status)
        return Response({'updated': updated})

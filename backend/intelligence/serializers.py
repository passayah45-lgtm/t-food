from rest_framework import serializers

from .models import RecommendationEvent, SearchEvent


class SearchEventSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = SearchEvent
        fields = (
            'id', 'user', 'query', 'category', 'latitude', 'longitude',
            'market', 'result_count', 'created_at',
        )
        read_only_fields = ('id', 'user', 'created_at')

    def validate(self, attrs):
        attrs['query'] = attrs.get('query', '').strip()[:200]
        attrs['category'] = attrs.get('category', '').strip()[:80]
        return attrs


class RecommendationEventSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = RecommendationEvent
        fields = (
            'id', 'user', 'surface', 'object_type', 'object_id', 'action',
            'score', 'reason_codes', 'created_at',
        )
        read_only_fields = ('id', 'user', 'created_at')

    def validate_surface(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Surface is required.')
        return value[:80]

    def validate_object_type(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Object type is required.')
        return value[:40]

    def validate_object_id(self, value):
        value = str(value).strip()
        if not value:
            raise serializers.ValidationError('Object id is required.')
        return value[:80]

    def validate_reason_codes(self, value):
        if value in (None, ''):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError('Reason codes must be a list.')
        safe_codes = []
        for item in value[:20]:
            if not isinstance(item, str):
                raise serializers.ValidationError('Reason codes must be strings.')
            code = item.strip()
            if code:
                safe_codes.append(code[:80])
        return safe_codes


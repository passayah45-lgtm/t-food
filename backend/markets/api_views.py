from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from fooddelivery.dashboard_cache import (
    get_cached_response_data,
    set_cached_response_data,
)
from operations_access.permissions import (
    get_operations_actor,
    require_operations_permission,
    MANAGE_AREAS,
    MANAGE_CITIES,
    MANAGE_MARKETS,
)

from .models import CommerceArea, CommerceCity, Market


class MarketSerializer(serializers.ModelSerializer):
    currency = serializers.CharField(source='default_currency.code', read_only=True)

    class Meta:
        model = Market
        fields = (
            'id', 'slug', 'name', 'country_code', 'currency', 'timezone',
            'phone_country_code', 'is_active',
        )


class CommerceCitySerializer(serializers.ModelSerializer):
    market_slug = serializers.CharField(source='market.slug', read_only=True)
    market_name = serializers.CharField(source='market.name', read_only=True)
    country_code = serializers.CharField(source='market.country_code', read_only=True)

    class Meta:
        model = CommerceCity
        fields = (
            'id', 'name', 'slug', 'market', 'market_slug', 'market_name',
            'country_code', 'is_active',
        )


class CommerceAreaSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source='city.name', read_only=True)
    city_slug = serializers.CharField(source='city.slug', read_only=True)
    market_slug = serializers.CharField(source='market.slug', read_only=True)
    market_name = serializers.CharField(source='market.name', read_only=True)
    country_code = serializers.CharField(source='market.country_code', read_only=True)

    class Meta:
        model = CommerceArea
        fields = (
            'id', 'name', 'slug', 'city', 'city_name', 'city_slug',
            'market', 'market_slug', 'market_name', 'country_code',
            'service_radius_km', 'is_active',
        )


def apply_market_filter(queryset, value):
    if not value:
        return queryset
    if str(value).isdigit():
        return queryset.filter(market_id=value)
    return queryset.filter(market__slug__iexact=value)


def request_has_operations_identity(request, actor):
    user = request.user
    return bool(
        getattr(user, 'is_authenticated', False)
        and (
            getattr(user, 'is_superuser', False)
            or getattr(user, 'is_staff', False)
            or actor.has_profile
        )
    )


def require_operations_read_scope(actor, permission):
    if actor.can(permission):
        return
    if actor.permissions and (
        actor.is_global_scope
        or actor.assigned_market_ids
        or actor.assigned_country_codes
        or actor.assigned_city_ids
        or actor.assigned_area_ids
    ):
        return
    require_operations_permission(actor, permission)


def apply_operations_market_scope(queryset, actor):
    if actor.is_global_scope:
        return queryset
    if actor.assigned_market_ids:
        return queryset.filter(id__in=actor.assigned_market_ids)
    if actor.assigned_country_codes:
        return queryset.filter(country_code__in=actor.assigned_country_codes)
    return queryset.none()


def apply_operations_city_scope(queryset, actor):
    if actor.is_global_scope:
        return queryset
    if actor.assigned_city_ids:
        return queryset.filter(id__in=actor.assigned_city_ids)
    if actor.assigned_market_ids:
        return queryset.filter(market_id__in=actor.assigned_market_ids)
    if actor.assigned_country_codes:
        return queryset.filter(market__country_code__in=actor.assigned_country_codes)
    return queryset.none()


def apply_operations_area_scope(queryset, actor):
    if actor.is_global_scope:
        return queryset
    if actor.assigned_area_ids:
        return queryset.filter(id__in=actor.assigned_area_ids)
    if actor.assigned_city_ids:
        return queryset.filter(city_id__in=actor.assigned_city_ids)
    if actor.assigned_market_ids:
        return queryset.filter(market_id__in=actor.assigned_market_ids)
    if actor.assigned_country_codes:
        return queryset.filter(market__country_code__in=actor.assigned_country_codes)
    return queryset.none()


class MarketListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        actor = get_operations_actor(request.user)
        cached = get_cached_response_data(
            'markets:list',
            actor if request_has_operations_identity(request, actor) else request.user,
            request.query_params,
        )
        if cached is not None:
            return Response(cached)
        markets = Market.objects.select_related('default_currency').filter(
            is_active=True,
        ).order_by('name')
        if request_has_operations_identity(request, actor):
            require_operations_read_scope(actor, MANAGE_MARKETS)
            markets = apply_operations_market_scope(markets, actor)
        data = MarketSerializer(markets, many=True).data
        set_cached_response_data(
            'markets:list',
            data,
            timeout=60 * 20,
            actor_or_user=actor if request_has_operations_identity(request, actor) else request.user,
            params=request.query_params,
        )
        return Response(data)


class CommerceCityListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        actor = get_operations_actor(request.user)
        cached = get_cached_response_data(
            'markets:cities',
            actor if request_has_operations_identity(request, actor) else request.user,
            request.query_params,
        )
        if cached is not None:
            return Response(cached)
        cities = CommerceCity.objects.select_related('market').filter(
            is_active=True,
            market__is_active=True,
        ).order_by('market__name', 'name')
        cities = apply_market_filter(cities, request.query_params.get('market'))
        country_code = request.query_params.get('country_code')
        if country_code:
            cities = cities.filter(market__country_code__iexact=country_code)
        if request_has_operations_identity(request, actor):
            require_operations_read_scope(actor, MANAGE_CITIES)
            cities = apply_operations_city_scope(cities, actor)
        data = CommerceCitySerializer(cities, many=True).data
        set_cached_response_data(
            'markets:cities',
            data,
            timeout=60 * 20,
            actor_or_user=actor if request_has_operations_identity(request, actor) else request.user,
            params=request.query_params,
        )
        return Response(data)


class CommerceAreaListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        actor = get_operations_actor(request.user)
        cached = get_cached_response_data(
            'markets:areas',
            actor if request_has_operations_identity(request, actor) else request.user,
            request.query_params,
        )
        if cached is not None:
            return Response(cached)
        areas = CommerceArea.objects.select_related('market', 'city').filter(
            is_active=True,
            market__is_active=True,
            city__is_active=True,
        ).order_by('market__name', 'city__name', 'name')
        areas = apply_market_filter(areas, request.query_params.get('market'))
        country_code = request.query_params.get('country_code')
        city = request.query_params.get('city')
        if country_code:
            areas = areas.filter(market__country_code__iexact=country_code)
        if city:
            areas = (
                areas.filter(city_id=city)
                if str(city).isdigit()
                else areas.filter(city__slug__iexact=city)
            )
        if request_has_operations_identity(request, actor):
            require_operations_read_scope(actor, MANAGE_AREAS)
            areas = apply_operations_area_scope(areas, actor)
        data = CommerceAreaSerializer(areas, many=True).data
        set_cached_response_data(
            'markets:areas',
            data,
            timeout=60 * 20,
            actor_or_user=actor if request_has_operations_identity(request, actor) else request.user,
            params=request.query_params,
        )
        return Response(data)

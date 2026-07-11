from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from django.core.exceptions import ValidationError as DjangoValidationError

from api.restaurant_views import request_location
from fooddelivery.dashboard_cache import (
    get_cached_response_data,
    set_cached_response_data,
)
from markets.models import Market
from operations_access.permissions import (
    VIEW_INTELLIGENCE,
    get_operations_actor,
    require_operations_permission,
)

from merchant_staff.models import MerchantStaffMember

from .assistant_service import (
    AssistantProviderError,
    SUPPORTED_ASSISTANT_SURFACES,
    ask_tfood_assistant,
)
from .models import VisualSearchEvent
from .merchant_insights import merchant_insights_for
from .operations_insights import operations_insights
from .serializers import RecommendationEventSerializer, SearchEventSerializer
from .services import get_customer_recommendations
from .visual_search.catalog import (
    parse_visual_search_location,
    resolve_market,
    search_visual_catalog,
)
from .visual_search.services import extract_visual_product_labels


class EventTrackingMixin:
    permission_classes = [AllowAny]

    def event_user(self, request):
        return request.user if request.user.is_authenticated else None


class RecommendationEventCreateView(EventTrackingMixin, APIView):
    def post(self, request):
        serializer = RecommendationEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = serializer.save(user=self.event_user(request))
        return Response(
            RecommendationEventSerializer(event).data,
            status=status.HTTP_201_CREATED,
        )


class SearchEventCreateView(EventTrackingMixin, APIView):
    def post(self, request):
        serializer = SearchEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = serializer.save(user=self.event_user(request))
        return Response(
            SearchEventSerializer(event).data,
            status=status.HTTP_201_CREATED,
        )


class CustomerRecommendationsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(
            get_customer_recommendations(
                request,
                location=request_location(request),
            )
        )


class MerchantInsightsView(APIView):
    def get(self, request):
        if not hasattr(request.user, 'merchant_profile'):
            raise PermissionDenied('Merchant access required.')
        cached = get_cached_response_data(
            'intelligence:merchant-insights',
            request.user,
            request.query_params,
        )
        if cached is not None:
            return Response(cached)
        data = merchant_insights_for(request.user)
        set_cached_response_data(
            'intelligence:merchant-insights',
            data,
            timeout=60,
            actor_or_user=request.user,
            params=request.query_params,
        )
        return Response(data)


class OperationsInsightsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        actor = get_operations_actor(request.user)
        require_operations_permission(actor, VIEW_INTELLIGENCE)
        cached = get_cached_response_data(
            'intelligence:operations-insights',
            actor,
            request.query_params,
        )
        if cached is not None:
            return Response(cached)
        data = operations_insights(actor=actor, request=request)
        set_cached_response_data(
            'intelligence:operations-insights',
            data,
            timeout=60,
            actor_or_user=actor,
            params=request.query_params,
        )
        return Response(data)


class AssistantChatView(APIView):
    permission_classes = [IsAuthenticated]

    def _require_surface_access(self, request, surface):
        user = request.user
        if surface in {'support', 'customer'}:
            return
        if surface == 'merchant':
            if hasattr(user, 'merchant_profile'):
                return
            has_staff_access = user.merchant_staff_memberships.filter(
                membership_status=MerchantStaffMember.STATUS_ACTIVE,
                verification_status=MerchantStaffMember.VERIFICATION_VERIFIED,
            ).exists()
            if has_staff_access:
                return
            raise PermissionDenied('Merchant assistant access required.')
        if surface == 'operations':
            actor = get_operations_actor(user)
            require_operations_permission(actor, VIEW_INTELLIGENCE)

    def post(self, request):
        surface = (request.data.get('surface') or '').strip().lower()
        message = (request.data.get('message') or '').strip()
        language = (request.data.get('language') or 'en').strip().lower()[:10]
        if surface not in SUPPORTED_ASSISTANT_SURFACES:
            raise DRFValidationError({'surface': 'Unsupported assistant surface.'})
        if not message:
            raise DRFValidationError({'message': 'Message is required.'})
        if len(message) > 2000:
            raise DRFValidationError({'message': 'Message is too long.'})

        self._require_surface_access(request, surface)
        try:
            data = ask_tfood_assistant(surface, message, language)
        except AssistantProviderError:
            return Response(
                {'detail': 'Assistant could not answer right now. Please try again later.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({'surface': surface, **data})


class VisualProductSearchView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        image = request.FILES.get('image') or request.FILES.get('file')
        provider_code = request.data.get('provider_code') or 'local_mock'
        category = (request.data.get('category') or '').strip()[:80]
        market = resolve_market(request.data.get('market'))
        location = parse_visual_search_location(
            request.data.get('latitude'),
            request.data.get('longitude'),
        )

        try:
            extraction = extract_visual_product_labels(
                image,
                provider_code=provider_code,
                context={
                    'market': market.slug if isinstance(market, Market) else '',
                    'category': category,
                },
            )
        except DjangoValidationError as exc:
            raise DRFValidationError({'image': exc.messages})

        catalog_result = search_visual_catalog(
            extraction['labels'],
            normalized_query=extraction['normalized_query'],
            market=market,
            category=category,
            location=location,
        )
        self._log_visual_search_event(
            request,
            extraction,
            market,
            category,
            catalog_result,
            location,
        )

        return Response({
            'predicted_labels': extraction['labels'],
            'confidence': extraction['confidence'],
            'normalized_query': extraction['normalized_query'],
            'fallback_query': extraction['fallback_query'],
            'matched_items': catalog_result['matched_items'],
            'matched_merchants': catalog_result['matched_merchants'],
            'similar_categories': catalog_result['similar_categories'],
            'provider_code': extraction['provider_code'],
            'image_metadata': extraction['metadata'].get('image', {}),
        })

    def _log_visual_search_event(self, request, extraction, market, category,
                                 catalog_result, location):
        country_code = ''
        if market:
            country_code = market.country_code
        matched_item_count = len(catalog_result['matched_items'])
        matched_merchant_count = len(catalog_result['matched_merchants'])
        VisualSearchEvent.objects.create(
            user=request.user if request.user.is_authenticated else None,
            provider_code=extraction['provider_code'],
            labels=extraction['labels'],
            normalized_query=extraction['normalized_query'],
            fallback_query=extraction['fallback_query'],
            confidence=extraction['confidence'],
            market=market,
            country_code=country_code,
            category=category,
            result_count=matched_item_count + matched_merchant_count,
            matched_item_count=matched_item_count,
            matched_merchant_count=matched_merchant_count,
            latitude=location['latitude'] if location else None,
            longitude=location['longitude'] if location else None,
        )

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Avg, Count, Prefetch, Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from customers.models import FavoriteRestaurant
from fooddelivery.media_storage import (
    file_response,
    open_private_file,
    open_public_file,
    private_file_exists,
    public_file_exists,
)
from operations_access.permissions import (
    VIEW_SUPPORT,
    can_access_area,
    can_access_city,
    can_access_country,
    can_access_market,
    get_operations_actor,
)
from fooddelivery.dashboard_cache import (
    get_cached_response_data,
    set_cached_response_data,
)
from restaurants.notification_events import schedule_review_photo_pending_notification
from restaurants.models import FoodItem, Restaurant, RestaurantReview, ReviewPhoto
from restaurants.services import restaurants_sorted_for_location
from .serializers import (
    RestaurantDetailSerializer,
    ReviewPhotoSerializer,
    RestaurantReviewSerializer,
    RestaurantSerializer,
)


def request_location(request):
    latitude = request.query_params.get('latitude')
    longitude = request.query_params.get('longitude')
    if not latitude or not longitude:
        return None
    try:
        latitude = Decimal(latitude)
        longitude = Decimal(longitude)
    except (InvalidOperation, TypeError):
        return None
    if not Decimal('-90') <= latitude <= Decimal('90'):
        return None
    if not Decimal('-180') <= longitude <= Decimal('180'):
        return None
    return {'latitude': latitude, 'longitude': longitude}


def restaurant_catalog_queryset():
    return Restaurant.objects.filter(is_active=True).select_related(
            'owner',
            'owner__merchant_profile',
            'market__default_currency',
            'city_ref',
            'area_ref',
            'branch_manager',
        ).prefetch_related(
            'operating_hours',
            Prefetch(
                'food_items',
                queryset=FoodItem.objects.filter(is_available=True).prefetch_related(
                    'option_groups__options'
                ),
            )
        ).annotate(
            item_count=Count(
                'food_items',
                filter=Q(food_items__is_available=True),
                distinct=True,
            ),
            review_count=Count('reviews', distinct=True),
            average_rating=Avg('reviews__rating'),
        ).order_by('rest_name')


class RestaurantListView(generics.ListAPIView):
    serializer_class = RestaurantSerializer
    permission_classes = [AllowAny]

    def list(self, request, *args, **kwargs):
        cached = get_cached_response_data(
            'restaurants:public-list',
            request.user,
            request.query_params,
        )
        if cached is not None:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        set_cached_response_data(
            'restaurants:public-list',
            response.data,
            timeout=45,
            actor_or_user=request.user,
            params=request.query_params,
        )
        return response

    def get_queryset(self):
        queryset = restaurant_catalog_queryset()
        search = self.request.query_params.get('search', '').strip()
        city = self.request.query_params.get('city', '').strip()
        area = self.request.query_params.get('area', '').strip()
        market = self.request.query_params.get('market', '').strip()
        country_code = self.request.query_params.get('country_code', '').strip()
        branch_type = self.request.query_params.get('branch_type', '').strip()
        category = self.request.query_params.get('category', '').strip()

        if search:
            queryset = queryset.filter(
                Q(rest_name__icontains=search) |
                Q(branch_name__icontains=search) |
                Q(rest_city__icontains=search) |
                Q(city_ref__name__icontains=search) |
                Q(area_ref__name__icontains=search) |
                Q(food_items__food_name__icontains=search) |
                Q(food_items__food_categ__icontains=search)
            ).distinct()
        if city:
            queryset = queryset.filter(
                Q(rest_city__icontains=city) |
                Q(city_ref__name__icontains=city) |
                Q(city_ref__slug__iexact=city)
            )
        if area:
            queryset = queryset.filter(
                Q(area_ref__name__icontains=area) |
                Q(area_ref__slug__iexact=area)
            )
        if market:
            if market.isdigit():
                queryset = queryset.filter(market_id=market)
            else:
                queryset = queryset.filter(market__slug__iexact=market)
        if country_code:
            queryset = queryset.filter(country_code__iexact=country_code)
        if branch_type:
            queryset = queryset.filter(branch_type__iexact=branch_type)
        if category:
            queryset = queryset.filter(food_items__food_categ__iexact=category).distinct()
        location = request_location(self.request)
        if location:
            return restaurants_sorted_for_location(
                queryset,
                location['latitude'],
                location['longitude'],
            )
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['location'] = request_location(self.request)
        return context


class RestaurantDetailView(generics.RetrieveAPIView):
    serializer_class = RestaurantDetailSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return restaurant_catalog_queryset()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['location'] = request_location(self.request)
        return context


class FavoriteRestaurantListView(generics.ListAPIView):
    serializer_class = RestaurantSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return restaurant_catalog_queryset().filter(
            customer_favorites__user=self.request.user
        )


class FavoriteRestaurantToggleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, restaurant_id):
        restaurant = get_object_or_404(
            Restaurant,
            id=restaurant_id,
            is_active=True,
        )
        favorite, created = FavoriteRestaurant.objects.get_or_create(
            user=request.user,
            restaurant=restaurant,
        )
        if not created:
            favorite.delete()
        return Response(
            {'restaurant_id': restaurant.id, 'is_favorite': created},
            status=status.HTTP_200_OK,
        )


class RestaurantReviewListCreateView(generics.ListCreateAPIView):
    serializer_class = RestaurantReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_restaurant(self):
        if not hasattr(self, '_restaurant'):
            self._restaurant = get_object_or_404(
                Restaurant,
                id=self.kwargs['restaurant_id'],
            )
        return self._restaurant

    def get_queryset(self):
        return RestaurantReview.objects.filter(
            restaurant=self.get_restaurant()
        ).select_related('customer')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['restaurant'] = self.get_restaurant()
        return context


class RestaurantReviewPhotoListCreateView(APIView):
    permission_classes = [AllowAny]

    def get_restaurant(self):
        if not hasattr(self, '_restaurant'):
            self._restaurant = get_object_or_404(
                Restaurant,
                id=self.kwargs['restaurant_id'],
            )
        return self._restaurant

    def get_review(self):
        if not hasattr(self, '_review'):
            self._review = get_object_or_404(
                RestaurantReview.objects.select_related('customer', 'order'),
                id=self.kwargs['review_id'],
                restaurant=self.get_restaurant(),
            )
        return self._review

    def get(self, request, restaurant_id, review_id):
        review = self.get_review()
        photos = review.photos.all()
        if not (request.user.is_authenticated and request.user == review.customer):
            photos = photos.filter(status=ReviewPhoto.STATUS_APPROVED)
        serializer = ReviewPhotoSerializer(
            photos,
            many=True,
            context={'request': request},
        )
        return Response(serializer.data)

    def post(self, request, restaurant_id, review_id):
        if not request.user.is_authenticated:
            raise PermissionDenied('Authentication required.')
        review = self.get_review()
        if review.customer_id != request.user.id:
            raise PermissionDenied('You can upload photos only for your own review.')
        if review.order.status != 'DELIVERED':
            raise ValidationError({
                'review': 'Review photos require a delivered order.'
            })
        image = request.FILES.get('image')
        if not image:
            raise ValidationError({'image': 'Image is required.'})
        try:
            photo = ReviewPhoto.objects.create(
                review=review,
                uploaded_by=request.user,
                image=image,
                caption=(request.data.get('caption') or '').strip()[:240],
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict if hasattr(exc, 'message_dict') else exc.messages)
        schedule_review_photo_pending_notification(photo, actor=request.user)
        serializer = ReviewPhotoSerializer(
            photo,
            context={'request': request},
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class RestaurantReviewPhotoDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, restaurant_id, review_id, photo_id):
        review = get_object_or_404(
            RestaurantReview.objects.select_related('customer'),
            id=review_id,
            restaurant_id=restaurant_id,
        )
        photo = get_object_or_404(
            ReviewPhoto,
            id=photo_id,
            review=review,
        )
        if review.customer_id != request.user.id or photo.uploaded_by_id != request.user.id:
            raise PermissionDenied('You can delete only your own pending review photos.')
        if photo.status != ReviewPhoto.STATUS_PENDING:
            raise ValidationError({
                'status': 'Only pending review photos can be deleted by the customer.'
            })
        photo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def operations_actor_can_access_photo(actor, photo):
    if not actor or not actor.permissions or not actor.can(VIEW_SUPPORT):
        return False
    if actor.is_global_scope:
        return True
    branch = photo.review.restaurant
    if not branch:
        return False
    if branch.area_ref_id and can_access_area(actor, branch.area_ref):
        return True
    if branch.city_ref_id and can_access_city(actor, branch.city_ref):
        return True
    if branch.market_id and can_access_market(actor, branch.market):
        return True
    if branch.country_code and can_access_country(actor, branch.country_code):
        return True
    return False


class ReviewPhotoPreviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, photo_id):
        photo = get_object_or_404(
            ReviewPhoto.objects.select_related(
                'review__customer',
                'review__restaurant',
                'review__restaurant__market',
                'review__restaurant__city_ref',
                'review__restaurant__area_ref',
            ),
            id=photo_id,
        )
        actor = get_operations_actor(request.user)
        can_preview = (
            photo.uploaded_by_id == request.user.id
            or operations_actor_can_access_photo(actor, photo)
        )
        if not can_preview:
            raise PermissionDenied('You do not have access to this review photo.')
        if not photo.image:
            return Response({'detail': 'Review photo not found.'}, status=404)
        if private_file_exists(photo.image.name):
            return file_response(
                open_private_file(photo.image.name, 'rb'),
                filename=photo.image.name.rsplit('/', 1)[-1],
            )
        if photo.status == ReviewPhoto.STATUS_APPROVED and public_file_exists(photo.image.name):
            return file_response(
                open_public_file(photo.image.name, 'rb'),
                filename=photo.image.name.rsplit('/', 1)[-1],
            )
        return Response({'detail': 'Review photo not found.'}, status=404)

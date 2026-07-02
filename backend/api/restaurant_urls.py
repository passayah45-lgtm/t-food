from django.urls import path

from .restaurant_views import (
    RestaurantDetailView,
    FavoriteRestaurantListView,
    FavoriteRestaurantToggleView,
    RestaurantListView,
    RestaurantReviewListCreateView,
    RestaurantReviewPhotoDetailView,
    RestaurantReviewPhotoListCreateView,
    ReviewPhotoPreviewView,
)


urlpatterns = [
    path('', RestaurantListView.as_view(), name='api_restaurant_list'),
    path('favorites/', FavoriteRestaurantListView.as_view(), name='api_restaurant_favorites'),
    path('<int:restaurant_id>/favorite/', FavoriteRestaurantToggleView.as_view(), name='api_restaurant_favorite_toggle'),
    path('<int:pk>/', RestaurantDetailView.as_view(), name='api_restaurant_detail'),
    path(
        '<int:restaurant_id>/reviews/',
        RestaurantReviewListCreateView.as_view(),
        name='api_restaurant_reviews',
    ),
    path(
        '<int:restaurant_id>/reviews/<int:review_id>/photos/',
        RestaurantReviewPhotoListCreateView.as_view(),
        name='api_restaurant_review_photos',
    ),
    path(
        '<int:restaurant_id>/reviews/<int:review_id>/photos/<int:photo_id>/',
        RestaurantReviewPhotoDetailView.as_view(),
        name='api_restaurant_review_photo_detail',
    ),
    path(
        'review-photos/<int:photo_id>/preview/',
        ReviewPhotoPreviewView.as_view(),
        name='api_review_photo_preview',
    ),
]

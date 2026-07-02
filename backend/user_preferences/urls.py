from django.urls import path

from .views import UserPreferenceOptionsView, UserPreferenceView


urlpatterns = [
    path('', UserPreferenceView.as_view(), name='user_preferences'),
    path('options/', UserPreferenceOptionsView.as_view(), name='user_preference_options'),
]

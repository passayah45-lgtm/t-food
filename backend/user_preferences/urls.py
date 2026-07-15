from django.urls import path

from .views import AccountAvatarView, UserPreferenceOptionsView, UserPreferenceView


urlpatterns = [
    path('', UserPreferenceView.as_view(), name='user_preferences'),
    path('account-avatar/', AccountAvatarView.as_view(), name='account_avatar'),
    path('options/', UserPreferenceOptionsView.as_view(), name='user_preference_options'),
]

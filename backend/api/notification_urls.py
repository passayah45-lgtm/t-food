from django.urls import path

from .notification_views import (
    NotificationArchiveReadView,
    NotificationArchiveView,
    NotificationDismissView,
    NotificationDeviceDeleteView,
    NotificationDeviceListCreateView,
    NotificationListView,
    NotificationMarkByFilterView,
    NotificationPreferenceView,
    NotificationReadAllView,
    NotificationReadView,
    NotificationUnreadView,
)


urlpatterns = [
    path('', NotificationListView.as_view()),
    path('preferences/', NotificationPreferenceView.as_view()),
    path('devices/', NotificationDeviceListCreateView.as_view()),
    path('devices/<int:device_id>/', NotificationDeviceDeleteView.as_view()),
    path('unread/', NotificationUnreadView.as_view()),
    path('read-all/', NotificationReadAllView.as_view()),
    path('archive-read/', NotificationArchiveReadView.as_view()),
    path('mark-by-filter/', NotificationMarkByFilterView.as_view()),
    path('<int:notification_id>/read/', NotificationReadView.as_view()),
    path('<int:notification_id>/archive/', NotificationArchiveView.as_view()),
    path('<int:notification_id>/dismiss/', NotificationDismissView.as_view()),
]

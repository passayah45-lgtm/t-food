from django.urls import path

from .support_views import SupportTicketListCreateView


urlpatterns = [
    path('tickets/', SupportTicketListCreateView.as_view()),
]

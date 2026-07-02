from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from fooddelivery.views import home
from restaurants.views import restaurant_menu

admin.site.site_header = 'T-Food operations'
admin.site.site_title = 'T-Food admin'
admin.site.index_title = 'Operations dashboard'

urlpatterns = [
    # Legacy template views (kept until React frontend is fully live)
    path('', home, name='home'),
    path('restaurant/<int:restaurant_id>/', restaurant_menu, name='restaurant_menu'),
    path('', include('restaurants.urls')),
    path('orders/', include('orders.urls')),
    path('payment/', include('payments.urls')),
    path('delivery/', include('delivery.urls')),
    path('accounts/', include('django.contrib.auth.urls')),

    # REST API  (all React frontend calls go here)
    path('api/v1/', include('api.urls')),

    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

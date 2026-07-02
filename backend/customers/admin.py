from django.contrib import admin
from .models import Customer, DeliveryAddress

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'address', 'loyalty_points')
    search_fields = ('user__username', 'user__email', 'phone')


@admin.register(DeliveryAddress)
class DeliveryAddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'label', 'recipient_name', 'phone', 'is_default', 'updated_at')
    list_filter = ('label', 'is_default')
    search_fields = ('user__username', 'recipient_name', 'phone', 'address')

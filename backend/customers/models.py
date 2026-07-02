from django.db import models
from django.contrib.auth.models import User
from fooddelivery.gis_fields import PointField
from fooddelivery.gis_utils import sync_point_from_lat_lng


class Customer(models.Model):
    market = models.ForeignKey(
        'markets.Market',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='customers',
    )
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='customer_profile'
    )
    phone   = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    avatar  = models.ImageField(upload_to='avatars/', null=True, blank=True)
    loyalty_points = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class FavoriteRestaurant(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='favorite_restaurants',
    )
    restaurant = models.ForeignKey(
        'restaurants.Restaurant',
        on_delete=models.CASCADE,
        related_name='customer_favorites',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'restaurant'),
                name='unique_user_favorite_restaurant',
            ),
        ]
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.user} - {self.restaurant}'


class DeliveryAddress(models.Model):
    LABEL_CHOICES = [
        ('HOME', 'Home'),
        ('WORK', 'Work'),
        ('OTHER', 'Other'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='delivery_addresses',
    )
    market = models.ForeignKey(
        'markets.Market',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='delivery_addresses',
    )
    label = models.CharField(max_length=10, choices=LABEL_CHOICES, default='HOME')
    recipient_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    address = models.TextField(max_length=500)
    instructions = models.CharField(max_length=300, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_point = PointField(srid=4326, null=True, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-is_default', '-updated_at')
        constraints = [
            models.UniqueConstraint(
                fields=('user',),
                condition=models.Q(is_default=True),
                name='one_default_delivery_address_per_user',
            ),
        ]

    def __str__(self):
        return f'{self.user} - {self.get_label_display()}'

    def save(self, *args, **kwargs):
        kwargs['update_fields'] = sync_point_from_lat_lng(
            self,
            point_field='location_point',
            latitude_field='latitude',
            longitude_field='longitude',
            update_fields=kwargs.get('update_fields'),
        )
        super().save(*args, **kwargs)

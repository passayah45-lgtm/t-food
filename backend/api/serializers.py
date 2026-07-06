from django.contrib.auth.models import User
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from customers.models import Customer, DeliveryAddress
from delivery.models import DeliveryPartner
from fooddelivery.upload_validation import prepare_public_image_upload
from orders.models import Offer, Order, OrderItem, OrderStatusEvent
from restaurants.models import (
    FoodOption,
    FoodOptionGroup,
    FoodItem,
    MerchantProfile,
    Restaurant,
    RestaurantOperatingHour,
    RestaurantReview,
    ReviewPhoto,
)
from restaurants.services import (
    restaurant_accepting_orders,
    restaurant_delivery_distance,
)

def restaurant_currency_code(restaurant):
    country_currency = {
        'GN': 'GNF',
        'IN': 'INR',
        'US': 'USD',
        'SA': 'SAR',
    }.get(str(getattr(restaurant, 'country_code', '') or '').upper())
    if country_currency:
        return country_currency
    market_currency = getattr(getattr(restaurant, 'market', None), 'default_currency', None)
    if market_currency and getattr(market_currency, 'code', None):
        return market_currency.code
    return 'GNF'


# ──────────────────────────────────────────────
# AUTH SERIALIZERS
# ──────────────────────────────────────────────

class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        required=True,
        validators=[UniqueValidator(queryset=User.objects.all())]
    )
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True, label='Confirm password')
    role = serializers.ChoiceField(
        choices=['customer', 'partner', 'merchant'],
        default='customer',
        write_only=True
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password', 'password2', 'role')
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name':  {'required': True},
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({'password': 'Passwords do not match.'})
        return attrs

    def create(self, validated_data):
        role = validated_data.pop('role', 'customer')
        validated_data.pop('password2')

        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
        )

        # Auto-create profile based on role
        if role == 'customer':
            Customer.objects.get_or_create(user=user)
        elif role == 'partner':
            DeliveryPartner.objects.get_or_create(
                user=user,
                defaults={
                    'partner_name': user.get_full_name() or user.username,
                    'partner_phone': '',
                    'transport_details': '',
                }
            )
        elif role == 'merchant':
            MerchantProfile.objects.get_or_create(
                user=user,
                defaults={'business_name': user.get_full_name()},
            )
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name')
        read_only_fields = ('id', 'username', 'email')


# ──────────────────────────────────────────────
# CUSTOMER PROFILE SERIALIZER
# ──────────────────────────────────────────────

class CustomerProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    avatar = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Customer
        fields = ('id', 'user', 'phone', 'address', 'avatar', 'loyalty_points')
        read_only_fields = ('loyalty_points',)

    def validate_avatar(self, value):
        if not value:
            return value
        try:
            return prepare_public_image_upload(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class DeliveryAddressSerializer(serializers.ModelSerializer):
    label_display = serializers.CharField(source='get_label_display', read_only=True)

    class Meta:
        model = DeliveryAddress
        fields = (
            'id', 'label', 'label_display', 'recipient_name', 'phone',
            'address', 'instructions', 'latitude', 'longitude',
            'is_default', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'label_display', 'created_at', 'updated_at')

    def validate(self, attrs):
        latitude = attrs.get('latitude', getattr(self.instance, 'latitude', None))
        longitude = attrs.get('longitude', getattr(self.instance, 'longitude', None))
        if (latitude is None) != (longitude is None):
            raise serializers.ValidationError(
                'Latitude and longitude must be provided together.'
            )
        return attrs


# ──────────────────────────────────────────────
# DELIVERY PARTNER PROFILE SERIALIZER
# ──────────────────────────────────────────────

class DeliveryPartnerProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = DeliveryPartner
        fields = (
            'id', 'user', 'partner_name', 'partner_phone',
            'transport_details', 'is_available', 'is_verified',
            'verification_status', 'verification_rejection_reason',
            'verification_submitted_at', 'verification_reviewed_at',
            'current_latitude', 'current_longitude', 'location_updated_at',
        )
        read_only_fields = (
            'id', 'user', 'is_verified', 'verification_status',
            'verification_rejection_reason', 'verification_submitted_at',
            'verification_reviewed_at', 'current_latitude', 'current_longitude',
            'location_updated_at',
        )


class FoodOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FoodOption
        fields = ('id', 'name', 'price_delta', 'is_available', 'ordering')


class FoodOptionGroupSerializer(serializers.ModelSerializer):
    options = FoodOptionSerializer(many=True, read_only=True)

    class Meta:
        model = FoodOptionGroup
        fields = ('id', 'name', 'min_select', 'max_select', 'ordering', 'options')


class FoodItemSerializer(serializers.ModelSerializer):
    option_groups = FoodOptionGroupSerializer(many=True, read_only=True)

    class Meta:
        model = FoodItem
        fields = (
            'id', 'restaurant_id', 'food_name', 'food_desc',
            'food_price', 'food_categ', 'is_available',
            'image',
            'option_groups',
        )


class RestaurantOperatingHourSerializer(serializers.ModelSerializer):
    day_display = serializers.CharField(
        source='get_day_of_week_display', read_only=True
    )

    class Meta:
        model = RestaurantOperatingHour
        fields = (
            'day_of_week', 'day_display', 'is_closed',
            'opens_at', 'closes_at',
        )


class RestaurantSerializer(serializers.ModelSerializer):
    is_open = serializers.SerializerMethodField()
    currency_code = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    area = serializers.SerializerMethodField()
    branch_manager_name = serializers.SerializerMethodField()
    item_count = serializers.IntegerField(read_only=True)
    review_count = serializers.IntegerField(read_only=True)
    average_rating = serializers.DecimalField(
        max_digits=3,
        decimal_places=2,
        read_only=True,
        allow_null=True,
    )
    categories = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()
    distance_km = serializers.SerializerMethodField()
    is_serviceable = serializers.SerializerMethodField()
    merchant_verified = serializers.SerializerMethodField()
    operating_hours = RestaurantOperatingHourSerializer(many=True, read_only=True)

    class Meta:
        model = Restaurant
        fields = (
            'id',
            'rest_name',
            'rest_email',
            'rest_contact',
            'rest_address',
            'rest_city',
            'branch_name',
            'branch_code',
            'branch_type',
            'country_code',
            'currency_code',
            'city',
            'area',
            'city_ref',
            'area_ref',
            'branch_manager_name',
            'delivery_fee',
            'delivery_radius_km',
            'estimated_prep_minutes',
            'min_order_amount',
            'is_open',
            'cover_image',
            'item_count',
            'review_count',
            'average_rating',
            'categories',
            'is_favorite',
            'distance_km',
            'is_serviceable',
            'merchant_verified',
            'operating_hours',
        )

    def get_categories(self, obj):
        return sorted({item.food_categ for item in obj.food_items.all()})

    def get_currency_code(self, obj):
        country_currency = {
            'GN': 'GNF',
            'IN': 'INR',
            'US': 'USD',
            'SA': 'SAR',
        }.get((obj.country_code or '').upper())
        if country_currency:
            return country_currency
        if obj.market_id and obj.market.default_currency_id:
            return obj.market.default_currency.code
        return 'GNF'

    def get_city(self, obj):
        return obj.city_ref.name if obj.city_ref_id else obj.rest_city

    def get_area(self, obj):
        return obj.area_ref.name if obj.area_ref_id else ''

    def get_branch_manager_name(self, obj):
        manager = obj.branch_manager
        if not manager:
            return ''
        return manager.get_full_name() or manager.username

    def get_is_favorite(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.customer_favorites.filter(user=request.user).exists()

    def get_is_open(self, obj):
        return restaurant_accepting_orders(obj)

    def get_distance_km(self, obj):
        if hasattr(obj, 'distance_km'):
            return obj.distance_km
        location = self.context.get('location')
        if not location:
            return None
        distance = restaurant_delivery_distance(
            obj, location['latitude'], location['longitude']
        )
        return distance

    def get_is_serviceable(self, obj):
        if hasattr(obj, 'is_serviceable'):
            return obj.is_serviceable
        distance = self.get_distance_km(obj)
        if distance is None:
            return None
        return distance <= obj.delivery_radius_km

    def get_merchant_verified(self, obj):
        profile = getattr(obj.owner, 'merchant_profile', None)
        return bool(profile and profile.is_verified)


class RestaurantDetailSerializer(RestaurantSerializer):
    food_items = FoodItemSerializer(many=True, read_only=True)

    class Meta(RestaurantSerializer.Meta):
        fields = RestaurantSerializer.Meta.fields + ('food_items',)


class OrderItemReadSerializer(serializers.ModelSerializer):
    food = FoodItemSerializer(read_only=True)
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = (
            'id', 'food', 'quantity', 'base_price', 'price',
            'selected_options', 'subtotal',
        )

    def get_subtotal(self, obj):
        return obj.get_subtotal()


class OrderItemInputSerializer(serializers.Serializer):
    food_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, max_value=99)
    option_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )


class OrderStatusEventSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    source_display = serializers.CharField(source='get_source_display', read_only=True)

    class Meta:
        model = OrderStatusEvent
        fields = (
            'id', 'status', 'status_display', 'source', 'source_display',
            'description', 'created_at',
        )


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemReadSerializer(many=True, read_only=True)
    payment = serializers.SerializerMethodField()
    delivery = serializers.SerializerMethodField()
    offer_code = serializers.CharField(source='offer.code', read_only=True)
    review = serializers.SerializerMethodField()
    timeline = OrderStatusEventSerializer(source='status_events', many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            'id', 'client_order_id', 'status', 'delivery_address',
            'delivery_instructions', 'contact_phone',
            'latitude', 'longitude', 'subtotal_amount', 'discount_amount',
            'delivery_fee', 'total_amount', 'offer_code',
            'items', 'payment', 'delivery', 'review', 'timeline',
            'payment_expires_at', 'delivery_distance_km',
            'estimated_delivery_at',
            'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'client_order_id', 'status', 'subtotal_amount', 'discount_amount',
            'delivery_fee', 'total_amount', 'offer_code', 'items',
            'review', 'timeline', 'payment_expires_at',
            'delivery_distance_km', 'estimated_delivery_at',
            'created_at', 'updated_at',
        )

    def get_payment(self, obj):
        if not hasattr(obj, 'payment'):
            return None
        return {
            'method': obj.payment.method,
            'status': obj.payment.status,
            'transaction_id': obj.payment.transaction_id,
        }

    def get_delivery(self, obj):
        if not hasattr(obj, 'delivery'):
            return None
        delivery = obj.delivery
        request = self.context.get('request')
        show_confirmation_code = (
            request
            and request.user == obj.customer
            and delivery.status != 'DELIVERED'
        )
        return {
            'id': delivery.id,
            'status': delivery.status,
            'partner_name': (
                delivery.delivery_partner.partner_name
                if delivery.delivery_partner else None
            ),
            'current_latitude': delivery.current_latitude,
            'current_longitude': delivery.current_longitude,
            'confirmation_code': (
                delivery.confirmation_code if show_confirmation_code else None
            ),
            'confirmation_verified_at': delivery.confirmation_verified_at,
        }

    def get_review(self, obj):
        if not hasattr(obj, 'review'):
            return None
        return {
            'id': obj.review.id,
            'restaurant_id': obj.review.restaurant_id,
            'rating': obj.review.rating,
        }


class OrderCreateSerializer(serializers.Serializer):
    enforce_serviceability = True
    client_order_id = serializers.UUIDField(required=False, allow_null=True)
    items = OrderItemInputSerializer(many=True)
    delivery_address = serializers.CharField(max_length=500)
    delivery_instructions = serializers.CharField(
        max_length=300, required=False, allow_blank=True
    )
    contact_phone = serializers.CharField(max_length=15)
    offer_code = serializers.CharField(
        max_length=30,
        required=False,
        allow_blank=True,
    )
    latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )

    def validate_delivery_address(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Enter a delivery address.')
        return value

    def validate_contact_phone(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Enter a contact phone number.')
        return value

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError(
                'Add at least one item before placing an order.'
            )

        food_ids = [item['food_id'] for item in items]
        foods = FoodItem.objects.select_related('restaurant__market__default_currency').prefetch_related(
            'option_groups__options'
        ).filter(id__in=food_ids)
        food_by_id = {food.id: food for food in foods}
        missing_ids = sorted(set(food_ids) - set(food_by_id))
        if missing_ids:
            raise serializers.ValidationError(
                f'Food item not found: {missing_ids[0]}'
            )

        restaurant_ids = {
            food_by_id[food_id].restaurant_id for food_id in food_ids
        }
        if len(restaurant_ids) > 1:
            raise serializers.ValidationError(
                'Order items must come from one restaurant.'
            )

        restaurant = next(iter(food_by_id.values())).restaurant
        if not restaurant_accepting_orders(restaurant):
            raise serializers.ValidationError(
                'This restaurant is not accepting orders right now.'
            )
        unavailable = [
            food.food_name for food in food_by_id.values() if not food.is_available
        ]
        if unavailable:
            raise serializers.ValidationError(
                f'{unavailable[0]} is currently unavailable.'
            )

        for item in items:
            food = food_by_id[item['food_id']]
            option_ids = item.get('option_ids', [])
            if len(option_ids) != len(set(option_ids)):
                raise serializers.ValidationError(
                    f'Duplicate options selected for {food.food_name}.'
                )
            selected = []
            selected_ids = set(option_ids)
            valid_ids = set()
            for group in food.option_groups.all():
                available = [option for option in group.options.all() if option.is_available]
                valid_ids.update(option.id for option in available)
                group_selected = [option for option in available if option.id in selected_ids]
                if len(group_selected) < group.min_select:
                    raise serializers.ValidationError(
                        f'Select at least {group.min_select} option(s) for {group.name}.'
                    )
                if len(group_selected) > group.max_select:
                    raise serializers.ValidationError(
                        f'Select no more than {group.max_select} option(s) for {group.name}.'
                    )
                selected.extend((group, option) for option in group_selected)
            invalid_ids = selected_ids - valid_ids
            if invalid_ids:
                raise serializers.ValidationError(
                    f'An option selected for {food.food_name} is unavailable or invalid.'
                )
            item['food'] = food
            item['selected_option_objects'] = selected
            item['unit_price'] = food.food_price + sum(
                (option.price_delta for _, option in selected), Decimal('0.00')
            )
        return items

    def validate_offer_eligibility(self, offer):
        if not offer.is_active or (
            offer.valid_until and offer.valid_until < timezone.now()
        ):
            raise serializers.ValidationError(
                {'offer_code': 'This offer is invalid or expired.'}
            )
        customer = self.context['request'].user
        active_redemptions = Order.objects.filter(offer=offer).exclude(
            status__in=('CANCELLED', 'EXPIRED')
        )
        if (
            offer.max_uses_total is not None
            and active_redemptions.count() >= offer.max_uses_total
        ):
            raise serializers.ValidationError(
                {'offer_code': 'This offer has reached its usage limit.'}
            )
        if (
            offer.max_uses_per_customer is not None
            and active_redemptions.filter(customer=customer).count()
            >= offer.max_uses_per_customer
        ):
            raise serializers.ValidationError(
                {'offer_code': 'You have already used this offer.'}
            )
        if offer.first_order_only and Order.objects.filter(
            customer=customer
        ).exclude(status__in=('CANCELLED', 'EXPIRED')).exists():
            raise serializers.ValidationError(
                {'offer_code': 'This offer is available only on your first order.'}
            )

    def validate(self, attrs):
        items = attrs['items']
        subtotal = sum(
            item['unit_price'] * item['quantity'] for item in items
        )
        code = attrs.get('offer_code', '').strip().upper()
        delivery_fee = items[0]['food'].restaurant.delivery_fee
        restaurant = items[0]['food'].restaurant
        latitude = attrs.get('latitude')
        longitude = attrs.get('longitude')
        delivery_distance = None
        if (
            restaurant.pickup_latitude is not None
            and restaurant.pickup_longitude is not None
        ):
            if self.enforce_serviceability and (
                latitude is None or longitude is None
            ):
                raise serializers.ValidationError({
                    'latitude': (
                        'Add a precise delivery location to confirm that this '
                        'restaurant serves your address.'
                    )
                })
            if latitude is not None and longitude is not None:
                delivery_distance = restaurant_delivery_distance(
                    restaurant, latitude, longitude
                )
                if delivery_distance > restaurant.delivery_radius_km:
                    raise serializers.ValidationError({
                        'delivery_address': (
                            f'This address is {delivery_distance} km away and '
                            f'outside the restaurant delivery radius of '
                            f'{restaurant.delivery_radius_km} km.'
                        )
                    })
        if subtotal < restaurant.min_order_amount:
            raise serializers.ValidationError({
                'items': (
                    f'Minimum order is {restaurant_currency_code(restaurant)} {restaurant.min_order_amount}.'
                )
            })
        offer = None
        discount = 0

        if code:
            offer = Offer.objects.filter(code__iexact=code, is_active=True).first()
            if not offer:
                raise serializers.ValidationError(
                    {'offer_code': 'This offer is invalid or expired.'}
                )
            self.validate_offer_eligibility(offer)
            if offer.market_id and restaurant.market_id != offer.market_id:
                raise serializers.ValidationError(
                    {'offer_code': 'This offer is not available for this market.'}
                )
            if subtotal < offer.min_order_amount:
                raise serializers.ValidationError({
                    'offer_code': (
                        f'Minimum order is {restaurant_currency_code(restaurant)} {offer.min_order_amount}.'
                    )
                })
            discount = min(
                subtotal,
                subtotal * offer.discount_percent / 100,
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        net_food = subtotal - discount
        platform_fee = (
            net_food * restaurant.commission_percent / 100
        ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        attrs['_pricing'] = {
            'subtotal': subtotal,
            'discount': discount,
            'delivery_fee': delivery_fee,
            'platform_fee': platform_fee,
            'merchant_payout': net_food - platform_fee,
            'total': net_food + delivery_fee,
            'offer': offer,
            'delivery_distance': delivery_distance,
            'estimated_delivery_at': (
                timezone.now() + timedelta(
                    minutes=(
                        restaurant.estimated_prep_minutes
                        + max(15, int(float(delivery_distance or 0) * 4))
                    )
                )
            ),
        }
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        items = validated_data.pop('items')
        validated_data.pop('offer_code', None)
        pricing = validated_data.pop('_pricing')
        if pricing['offer']:
            User.objects.select_for_update().get(
                id=self.context['request'].user.id
            )
            pricing['offer'] = Offer.objects.select_for_update().get(
                id=pricing['offer'].id
            )
            self.validate_offer_eligibility(pricing['offer'])
        order = Order.objects.create(
            customer=self.context['request'].user,
            pickup_branch=items[0]['food'].restaurant,
            payment_expires_at=(
                timezone.now() + timedelta(
                    minutes=settings.PAYMENT_TIMEOUT_MINUTES
                )
            ),
            subtotal_amount=pricing['subtotal'],
            discount_amount=pricing['discount'],
            delivery_fee=pricing['delivery_fee'],
            platform_fee=pricing['platform_fee'],
            merchant_payout=pricing['merchant_payout'],
            delivery_distance_km=pricing['delivery_distance'],
            estimated_delivery_at=pricing['estimated_delivery_at'],
            total_amount=pricing['total'],
            offer=pricing['offer'],
            **validated_data,
        )

        order_items = []
        for item in items:
            food = item['food']
            quantity = item['quantity']
            order_items.append(OrderItem(
                order=order,
                food=food,
                quantity=quantity,
                base_price=food.food_price,
                price=item['unit_price'],
                selected_options=[
                    {
                        'option_id': option.id,
                        'group': group.name,
                        'name': option.name,
                        'price_delta': str(option.price_delta),
                    }
                    for group, option in item['selected_option_objects']
                ],
            ))

        OrderItem.objects.bulk_create(order_items)
        return order


class OfferValidationSerializer(OrderCreateSerializer):
    enforce_serviceability = False
    delivery_address = serializers.CharField(required=False, default='preview')
    contact_phone = serializers.CharField(required=False, default='preview')
    latitude = serializers.HiddenField(default=None)
    longitude = serializers.HiddenField(default=None)

    def create(self, validated_data):
        raise NotImplementedError


class RestaurantReviewSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()
    order_id = serializers.IntegerField(write_only=True)
    photos = serializers.SerializerMethodField()

    class Meta:
        model = RestaurantReview
        fields = (
            'id', 'customer_name', 'order_id', 'rating', 'comment', 'created_at',
            'photos',
        )
        read_only_fields = ('id', 'customer_name', 'created_at', 'photos')

    def get_customer_name(self, obj):
        return obj.customer.get_full_name() or obj.customer.username

    def get_photos(self, obj):
        approved = obj.photos.filter(status=ReviewPhoto.STATUS_APPROVED)
        return ReviewPhotoSerializer(
            approved,
            many=True,
            context={**self.context, 'public': True},
        ).data

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError('Rating must be between 1 and 5.')
        return value

    def validate(self, attrs):
        request = self.context['request']
        restaurant = self.context['restaurant']
        order = Order.objects.filter(
            id=attrs['order_id'],
            customer=request.user,
            status='DELIVERED',
            items__food__restaurant=restaurant,
        ).distinct().first()
        if not order:
            raise serializers.ValidationError({
                'order_id': 'A delivered order from this restaurant is required.'
            })
        if hasattr(order, 'review'):
            raise serializers.ValidationError({
                'order_id': 'This order has already been reviewed.'
            })
        attrs['order'] = order
        return attrs

    def create(self, validated_data):
        validated_data.pop('order_id')
        return RestaurantReview.objects.create(
            restaurant=self.context['restaurant'],
            customer=self.context['request'].user,
            **validated_data,
        )


class ReviewPhotoSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    preview_url = serializers.SerializerMethodField()
    moderation_reason = serializers.SerializerMethodField()

    class Meta:
        model = ReviewPhoto
        fields = (
            'id', 'review', 'caption', 'status', 'moderation_reason',
            'image_url', 'preview_url', 'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'review', 'status', 'moderation_reason',
            'image_url', 'created_at', 'updated_at',
        )

    def get_image_url(self, obj):
        if obj.status != ReviewPhoto.STATUS_APPROVED:
            return None
        if not obj.image:
            return None
        request = self.context.get('request')
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url

    def get_preview_url(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        if request.user != obj.uploaded_by:
            return None
        path = f'/api/v1/restaurants/review-photos/{obj.id}/preview/'
        return request.build_absolute_uri(path)

    def get_moderation_reason(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated and request.user == obj.uploaded_by:
            return obj.moderation_reason
        return ''

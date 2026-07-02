from django.db.models.signals import pre_save
from django.dispatch import receiver

from customers.models import Customer, DeliveryAddress
from delivery.models import Delivery, DeliveryPartner
from notifications.models import Notification
from orders.models import Offer, Order
from payments.models import Payment, PaymentWebhookEvent
from restaurants.models import MerchantProfile, Restaurant

from .models import Market


MARKET_SCOPED_MODELS = (
    Customer,
    DeliveryAddress,
    Delivery,
    DeliveryPartner,
    Notification,
    Offer,
    Order,
    Payment,
    PaymentWebhookEvent,
    MerchantProfile,
    Restaurant,
)


def default_market_id():
    return Market.objects.filter(slug='india', is_active=True).values_list(
        'id', flat=True
    ).first()


@receiver(pre_save)
def assign_default_market(sender, instance, **kwargs):
    if sender not in MARKET_SCOPED_MODELS:
        return
    if getattr(instance, 'market_id', None):
        return
    market_id = default_market_id()
    if market_id:
        instance.market_id = market_id


from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from delivery.models import Delivery, DeliveryPartner
from delivery.tasks import notify_pending_delivery_candidates_task
from notifications.models import Notification
from orders.models import Order, OrderItem
from payments.models import Payment
from restaurants.models import FoodItem, Restaurant


class NotifyPendingDeliveryCandidatesTaskTests(TestCase):
    def test_task_does_not_duplicate_pickup_notifications(self):
        customer = User.objects.create_user(username='dispatch-task-customer')
        driver_user = User.objects.create_user(username='dispatch-task-driver')
        DeliveryPartner.objects.create(
            user=driver_user,
            partner_name='Dispatch Task Driver',
            partner_phone='9000000020',
            transport_details='Bike',
            is_verified=True,
            is_available=True,
        )
        restaurant = Restaurant.objects.create(
            rest_name='Dispatch Task Kitchen',
            rest_email='dispatch-task@example.com',
            rest_contact='1234567890',
            rest_address='Kitchen Road',
            rest_city='Test City',
            is_active=True,
        )
        food = FoodItem.objects.create(
            restaurant=restaurant,
            food_name='Task Delivery Meal',
            food_price=Decimal('200.00'),
            food_categ='Vegetarian',
        )
        order = Order.objects.create(
            customer=customer,
            status='READY_FOR_PICKUP',
            delivery_address='Customer Street',
            delivery_fee=Decimal('40.00'),
            total_amount=Decimal('220.00'),
        )
        OrderItem.objects.create(
            order=order,
            food=food,
            quantity=1,
            price=Decimal('200.00'),
        )
        Payment.objects.create(order=order, method='CARD', status='SUCCESS')
        Delivery.objects.create(order=order)

        first_result = notify_pending_delivery_candidates_task.apply().get()
        second_result = notify_pending_delivery_candidates_task.apply().get()

        self.assertEqual(first_result, 1)
        self.assertEqual(second_result, 0)
        self.assertEqual(
            Notification.objects.filter(
                user=driver_user,
                order=order,
                kind='DELIVERY',
                title=f'Pickup available for order #{order.id}',
            ).count(),
            1,
        )


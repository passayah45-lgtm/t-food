from django.core.management.base import BaseCommand

from restaurants.models import FoodItem, Restaurant


CATALOG = [
    {
        'restaurant': {
            'rest_name': 'Tasty Bites',
            'rest_email': 'tasty@food.com',
            'rest_contact': '9876543210',
            'rest_address': 'Main Street',
            'rest_city': 'Delhi',
        },
        'items': [
            ('Chicken Biryani', 'Spicy rice with chicken', '250.00', 'Non-Vegetarian'),
            ('Paneer Butter Masala', 'Creamy paneer curry', '220.00', 'Vegetarian'),
            ('Cold Coffee', 'Chilled coffee', '120.00', 'Beverages'),
        ],
    },
    {
        'restaurant': {
            'rest_name': 'Food Corner',
            'rest_email': 'foodcorner@food.com',
            'rest_contact': '9123456780',
            'rest_address': 'Park Road',
            'rest_city': 'Mumbai',
        },
        'items': [
            ('Veg Burger', 'Fresh veg burger with crispy patty and sauce', '100.00', 'Vegetarian'),
            ('French Fries', 'Crispy golden fries served hot', '150.00', 'Vegetarian'),
            ('Soft Drink', 'Chilled refreshing soft drink', '80.00', 'Beverages'),
        ],
    },
    {
        'restaurant': {
            'rest_name': 'Spice Hub',
            'rest_email': 'spicehub@food.com',
            'rest_contact': '9988776655',
            'rest_address': 'Market Area',
            'rest_city': 'Bangalore',
        },
        'items': [
            ('Mutton Curry', '', '300.00', 'Non-Vegetarian'),
            ('Veg Pulao', '', '180.00', 'Vegetarian'),
            ('Gulab Jamun', '', '90.00', 'Desserts'),
        ],
    },
]


class Command(BaseCommand):
    help = 'Create or update the non-sensitive demo restaurant catalog.'

    def handle(self, *args, **options):
        item_count = 0
        for entry in CATALOG:
            restaurant_data = entry['restaurant']
            restaurant, _ = Restaurant.objects.update_or_create(
                rest_email=restaurant_data['rest_email'],
                defaults=restaurant_data,
            )
            for name, description, price, category in entry['items']:
                FoodItem.objects.update_or_create(
                    restaurant=restaurant,
                    food_name=name,
                    defaults={
                        'food_desc': description,
                        'food_price': price,
                        'food_categ': category,
                    },
                )
                item_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Demo catalog ready: {len(CATALOG)} restaurants, {item_count} items.'
        ))

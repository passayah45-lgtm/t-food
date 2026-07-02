
# Create your views here.
from django.shortcuts import render, get_object_or_404
from .models import Restaurant, FoodItem

def restaurant_list(request):
    restaurants = Restaurant.objects.all()
    return render(request, 'restaurants/list.html', {
        'restaurants': restaurants
    })


def restaurant_menu(request, restaurant_id):
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    food_items = FoodItem.objects.filter(restaurant=restaurant)

    return render(
        request,
        'restaurants/menu.html',
        {
            'restaurant': restaurant,
            'food_items': food_items
        }
    )

from django.shortcuts import redirect, get_object_or_404, render
from django.contrib.auth.decorators import login_required

from restaurants.models import FoodItem
from .models import Order, OrderItem
from .services import assign_merchant_order_code


# =========================
# CART OPERATIONS
# =========================

def add_to_cart(request, food_id):
    cart = request.session.get('cart', {})
    food_id = str(food_id)
    cart[food_id] = cart.get(food_id, 0) + 1
    request.session['cart'] = cart
    return redirect('view_cart')


def view_cart(request):
    cart = request.session.get('cart', {})
    items = []
    total = 0

    for food_id, quantity in cart.items():
        food = get_object_or_404(FoodItem, id=food_id)
        subtotal = food.food_price * quantity
        total += subtotal
        items.append({'food': food, 'quantity': quantity, 'subtotal': subtotal})

    return render(request, 'orders/cart.html', {'items': items, 'total': total})


def remove_from_cart(request, food_id):
    cart = request.session.get('cart', {})
    cart.pop(str(food_id), None)
    request.session['cart'] = cart
    return redirect('view_cart')


def clear_cart(request):
    request.session['cart'] = {}
    return redirect('view_cart')


def increase_quantity(request, food_id):
    cart = request.session.get('cart', {})
    food_id = str(food_id)
    if food_id in cart:
        cart[food_id] += 1
    request.session['cart'] = cart
    return redirect('view_cart')


def decrease_quantity(request, food_id):
    cart = request.session.get('cart', {})
    food_id = str(food_id)
    if food_id in cart:
        if cart[food_id] > 1:
            cart[food_id] -= 1
        else:
            del cart[food_id]
    request.session['cart'] = cart
    return redirect('view_cart')


# =========================
# ORDER PLACEMENT
# =========================

@login_required
def place_order(request):
    """
    1. Create order (status=PLACED)
    2. Redirect to payment page
    Delivery assignment happens AFTER payment succeeds.
    """
    if request.method != 'POST':
        return redirect('view_cart')

    cart = request.session.get('cart', {})
    if not cart:
        return redirect('view_cart')

    latitude = request.POST.get('latitude')
    longitude = request.POST.get('longitude')

    if not latitude or not longitude:
        return redirect('view_cart')

    # FIX: removed created_at=timezone.now() — field uses auto_now_add=True
    order = Order.objects.create(
        customer=request.user,
        status='PLACED',
        latitude=latitude,
        longitude=longitude,
    )

    total_amount = 0
    pickup_branch = None
    for food_id, quantity in cart.items():
        food = get_object_or_404(FoodItem, id=food_id)
        if pickup_branch is None:
            pickup_branch = food.restaurant
        OrderItem.objects.create(
            order=order,
            food=food,
            quantity=quantity,
            price=food.food_price,
        )
        total_amount += food.food_price * quantity

    order.total_amount = total_amount
    order.pickup_branch = pickup_branch
    order.save()
    assign_merchant_order_code(order)

    request.session['cart'] = {}
    return redirect('payment_page', order_id=order.id)


# =========================
# ORDER SUCCESS & LIST
# =========================

@login_required
def order_success(request):
    return render(request, 'orders/order_success.html')


@login_required
def order_list(request):
    orders = Order.objects.filter(customer=request.user).order_by('-id')
    return render(request, 'orders/order_list.html', {'orders': orders})

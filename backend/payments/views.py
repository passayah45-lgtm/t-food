from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required

from orders.models import Order
from .models import Payment
from delivery.models import Delivery
from delivery.services import auto_assign_delivery


@login_required
def payment_page(request, order_id):
    order = get_object_or_404(Order, id=order_id, customer=request.user)

    # Prevent duplicate payment
    if hasattr(order, 'payment'):
        return redirect('payment_success', order_id=order.id)

    if request.method == 'POST':
        method = request.POST.get('method')

        if not method:
            return render(request, 'payments/payment.html', {
                'order': order,
                'error': 'Please select a payment method',
            })

        # Record payment (simulated — always SUCCESS in dev)
        Payment.objects.create(
            order=order,
            method=method,
            status='SUCCESS',
        )

        # FIX: use the unified status constant 'CONFIRMED' (not the string 'Confirmed')
        order.status = 'CONFIRMED'
        order.save()

        # FIX: delegate to the shared service so notifications fire correctly
        auto_assign_delivery(order)

        return redirect('payment_success', order_id=order.id)

    return render(request, 'payments/payment.html', {'order': order})


@login_required
def payment_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, customer=request.user)

    # Ensure a delivery record exists (handles edge cases where partner unavailable)
    Delivery.objects.get_or_create(
        order=order,
        defaults={
            'current_latitude': 20.2961,
            'current_longitude': 85.8245,
        }
    )

    return render(request, 'payments/payment_success.html', {'order': order})

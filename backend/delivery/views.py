# ==========================================================
# Imports
# ==========================================================
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from .decorators import delivery_partner_required
from .models import Delivery
from .notifications import (
    notify_partner_assigned,
    notify_customer_status,
    notify_admin_delivered
)


# ==========================================================
# DELIVERY PARTNER DASHBOARD (UNCHANGED)
# ==========================================================
@login_required
@delivery_partner_required
def partner_dashboard(request):
    # Get logged-in delivery partner
    partner = request.user.delivery_partner

    # Fetch all deliveries assigned to this partner
    deliveries = Delivery.objects.filter(
        delivery_partner=partner
    ).order_by('-assigned_at')

    return render(
        request,
        'delivery/partner_dashboard.html',
        {'deliveries': deliveries}
    )


# ==========================================================
# UPDATE DELIVERY STATUS (UPDATED – TRACKING HOOK ADDED)
# ==========================================================
@login_required
@delivery_partner_required
def update_delivery_status(request, delivery_id):
    """
    Updates delivery status.
    Tracking ready (location updates happen separately).
    """

    # Ensure delivery belongs to logged-in partner
    delivery = get_object_or_404(
        Delivery,
        id=delivery_id,
        delivery_partner=request.user.delivery_partner
    )

    if request.method == 'POST':
        new_status = request.POST.get('status')

        # Validate status
        if new_status in dict(Delivery.DELIVERY_STATUS_CHOICES):
            delivery.status = new_status

            partner = delivery.delivery_partner

            # Partner unavailable while delivering
            if new_status in ['ASSIGNED', 'PICKED_UP', 'ON_THE_WAY']:
                partner.is_available = False

            # Partner available after delivery
            if new_status == 'DELIVERED':
                partner.is_available = True

                # Notify admin when delivered
                notify_admin_delivered(delivery)

            # Notify customer about status change
            notify_customer_status(delivery)

            # Save changes
            partner.save()
            delivery.save()

        # Redirect back to partner dashboard
        return redirect('partner_dashboard')

    # Render update status page (GET request)
    return render(
        request,
        'delivery/update_status.html',
        {'delivery': delivery}
    )


# ==========================================================
# UPDATE DELIVERY LOCATION ( TRACKING)
# ==========================================================
@login_required
@delivery_partner_required
def update_location(request, delivery_id):
    """
    Receives live GPS updates from delivery partner
    Used for Google Maps live tracking
    """

    delivery = get_object_or_404(
        Delivery,
        id=delivery_id,
        delivery_partner=request.user.delivery_partner
    )

    if request.method == 'POST':
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')

        if latitude and longitude:
            delivery.current_latitude = latitude
            delivery.current_longitude = longitude
            delivery.save()

            return JsonResponse({'status': 'success'})

    return JsonResponse({'status': 'failed'}, status=400)


@login_required
def track_order(request, order_id):
    delivery = get_object_or_404(
        Delivery,
        order_id=order_id,
        order__customer=request.user
    )

    return render(
        request,
        'delivery/track_order.html',
        {'delivery': delivery}
    )
@login_required
def get_delivery_location(request, order_id):
    """
    Returns current delivery location for tracking
    """
    delivery = get_object_or_404(
        Delivery,
        order_id=order_id,
        order__customer=request.user
    )

    return JsonResponse({
        'latitude': delivery.current_latitude,
        'longitude': delivery.current_longitude,
        'status': delivery.status
    })

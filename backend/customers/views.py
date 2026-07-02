from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Customer


@login_required
def profile(request):
    """View / update the logged-in customer's profile."""
    profile, _ = Customer.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        profile.phone = request.POST.get('phone', '').strip()
        profile.address = request.POST.get('address', '').strip()
        profile.save()
        return redirect('profile')

    return render(request, 'customers/profile.html', {'profile': profile})

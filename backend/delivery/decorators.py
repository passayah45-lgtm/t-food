from functools import wraps
from django.shortcuts import redirect
 


def delivery_partner_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Admin should never be blocked
        #if request.user.is_staff or request.user.is_superuser:
           # return view_func(request, *args, **kwargs)

        # Must be logged in
        if not request.user.is_authenticated:
            return redirect('login')

        # Must be a delivery partner
        if not hasattr(request.user, 'delivery_partner'):
            return redirect('login')

        return view_func(request, *args, **kwargs)

    return wrapper

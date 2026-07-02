from django.shortcuts import render
from restaurants.models import Restaurant
from django.db.models import Q

def home(request):
    query = request.GET.get('q')

    if query:
        restaurants = Restaurant.objects.filter(
            Q(rest_name__icontains=query) |
            Q(rest_city__icontains=query)
        )
    else:
        restaurants = Restaurant.objects.all()

    return render(request, 'customers/index.html', {
        'restaurants': restaurants,
        'query': query
    })



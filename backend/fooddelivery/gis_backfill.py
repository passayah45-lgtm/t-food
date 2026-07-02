from fooddelivery.gis_utils import make_point, valid_coordinates


def _initial_stats():
    return {
        'updated': 0,
        'already_set': 0,
        'skipped_missing': 0,
        'skipped_invalid': 0,
    }


def _backfill_model(
    model,
    point_field,
    latitude_field,
    longitude_field,
    save_fields=None,
):
    stats = _initial_stats()
    save_fields = save_fields or [point_field]

    for instance in model.objects.all().iterator():
        if getattr(instance, point_field):
            stats['already_set'] += 1
            continue

        latitude = getattr(instance, latitude_field)
        longitude = getattr(instance, longitude_field)
        if latitude is None or longitude is None:
            stats['skipped_missing'] += 1
            continue

        coordinates = valid_coordinates(latitude, longitude)
        if coordinates is None:
            stats['skipped_invalid'] += 1
            continue

        latitude, longitude = coordinates
        setattr(instance, point_field, make_point(longitude, latitude))
        instance.save(update_fields=save_fields)
        stats['updated'] += 1

    return stats


def backfill_gis_points(apps=None):
    get_model = apps.get_model if apps is not None else None

    if get_model is None:
        from customers.models import DeliveryAddress
        from delivery.models import Delivery, DeliveryPartner
        from orders.models import Order
        from restaurants.models import Restaurant
    else:
        Restaurant = get_model('restaurants', 'Restaurant')
        DeliveryAddress = get_model('customers', 'DeliveryAddress')
        DeliveryPartner = get_model('delivery', 'DeliveryPartner')
        Delivery = get_model('delivery', 'Delivery')
        Order = get_model('orders', 'Order')

    return {
        'restaurants': _backfill_model(
            Restaurant,
            'pickup_point',
            'pickup_latitude',
            'pickup_longitude',
        ),
        'delivery_addresses': _backfill_model(
            DeliveryAddress,
            'location_point',
            'latitude',
            'longitude',
        ),
        'delivery_partners': _backfill_model(
            DeliveryPartner,
            'current_point',
            'current_latitude',
            'current_longitude',
        ),
        'deliveries': _backfill_model(
            Delivery,
            'current_point',
            'current_latitude',
            'current_longitude',
        ),
        'orders': _backfill_model(
            Order,
            'delivery_point',
            'latitude',
            'longitude',
        ),
    }

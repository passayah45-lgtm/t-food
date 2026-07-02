from decimal import Decimal, InvalidOperation

from django.conf import settings


def decimal_or_none(value):
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def valid_coordinates(latitude, longitude):
    latitude = decimal_or_none(latitude)
    longitude = decimal_or_none(longitude)
    if latitude is None or longitude is None:
        return None
    if latitude < Decimal('-90') or latitude > Decimal('90'):
        return None
    if longitude < Decimal('-180') or longitude > Decimal('180'):
        return None
    return latitude, longitude


def point_from_coordinates(longitude, latitude):
    if not settings.GEODJANGO_AVAILABLE:
        return f'SRID=4326;POINT({longitude} {latitude})'

    from django.contrib.gis.geos import Point

    return Point(float(longitude), float(latitude), srid=4326)


def make_point(longitude, latitude):
    coordinates = valid_coordinates(latitude, longitude)
    if coordinates is None:
        return None

    latitude, longitude = coordinates
    return point_from_coordinates(longitude, latitude)


def update_fields_with_point(update_fields, point_field):
    if update_fields is None:
        return None
    return set(update_fields) | {point_field}


def sync_point_from_lat_lng(
    instance,
    *,
    point_field,
    latitude_field,
    longitude_field,
    update_fields=None,
):
    update_set = set(update_fields) if update_fields is not None else None
    coordinate_fields = {latitude_field, longitude_field}

    if update_set is not None and not coordinate_fields.intersection(update_set):
        return update_fields

    existing_point = getattr(instance, point_field)
    coordinates_changed = instance.pk is None
    if instance.pk is not None:
        old_values = (
            instance.__class__.objects
            .filter(pk=instance.pk)
            .values(latitude_field, longitude_field)
            .first()
        )
        if old_values is None:
            coordinates_changed = True
        else:
            coordinates_changed = (
                decimal_or_none(old_values[latitude_field])
                != decimal_or_none(getattr(instance, latitude_field))
                or decimal_or_none(old_values[longitude_field])
                != decimal_or_none(getattr(instance, longitude_field))
            )

    if existing_point and not coordinates_changed:
        return update_fields

    latitude = getattr(instance, latitude_field)
    longitude = getattr(instance, longitude_field)
    if instance.pk is None and existing_point and (latitude is None or longitude is None):
        return update_fields

    point = make_point(
        longitude,
        latitude,
    )
    setattr(instance, point_field, point)
    return update_fields_with_point(update_fields, point_field)

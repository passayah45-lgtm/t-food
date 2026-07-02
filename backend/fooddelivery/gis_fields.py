from django.conf import settings
from django.db import models


if settings.GEODJANGO_AVAILABLE:
    from django.contrib.gis.db.models import PointField as GeoDjangoPointField

    class PointField(GeoDjangoPointField):
        def deconstruct(self):
            name, path, args, kwargs = super().deconstruct()
            path = 'fooddelivery.gis_fields.PointField'
            return name, path, args, kwargs

else:
    class PointField(models.Field):
        description = 'Compatibility point field used when GeoDjango libraries are unavailable'

        def __init__(self, *args, srid=4326, spatial_index=True, **kwargs):
            self.srid = srid
            self.spatial_index = spatial_index
            super().__init__(*args, **kwargs)

        def db_type(self, connection):
            if connection.vendor == 'postgresql':
                return f'geometry(Point,{self.srid})'
            return 'text'

        def get_internal_type(self):
            return 'TextField'

        def get_prep_value(self, value):
            if value is None or isinstance(value, str):
                return value

            wkt = getattr(value, 'wkt', None)
            if wkt:
                srid = getattr(value, 'srid', None) or self.srid
                return f'SRID={srid};{wkt}'

            return str(value)

        def from_db_value(self, value, expression, connection):
            return value

        def to_python(self, value):
            return value

        def deconstruct(self):
            name, path, args, kwargs = super().deconstruct()
            path = 'fooddelivery.gis_fields.PointField'
            if self.srid != 4326:
                kwargs['srid'] = self.srid
            if self.spatial_index is not True:
                kwargs['spatial_index'] = self.spatial_index
            return name, path, args, kwargs

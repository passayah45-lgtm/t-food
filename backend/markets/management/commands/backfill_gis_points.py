from django.core.management.base import BaseCommand

from fooddelivery.gis_backfill import backfill_gis_points


class Command(BaseCommand):
    help = 'Backfill nullable GIS point fields from existing latitude/longitude fields.'

    def handle(self, *args, **options):
        results = backfill_gis_points()
        for label, stats in results.items():
            self.stdout.write(
                '{label}: updated={updated} already_set={already_set} '
                'skipped_missing={skipped_missing} skipped_invalid={skipped_invalid}'.format(
                    label=label,
                    **stats,
                )
            )

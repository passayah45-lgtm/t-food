from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from markets.models import CommerceArea, CommerceCity, Market
from operations_access.models import (
    OperationsAccessAudit,
    OperationsStaffAreaAccess,
    OperationsStaffCityAccess,
    OperationsStaffMarketAccess,
    OperationsStaffProfile,
)


class Command(BaseCommand):
    help = 'Create scoped OperationsStaffProfile records for legacy Django staff users.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without writing profiles or scope assignments.',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='Migrate one legacy staff user by id.',
        )
        parser.add_argument(
            '--role',
            default=OperationsStaffProfile.ROLE_VIEWER,
            choices=[
                role
                for role, _label in OperationsStaffProfile.ROLE_CHOICES
                if role != OperationsStaffProfile.ROLE_GLOBAL_ADMIN
            ],
            help='Role for created profiles. Defaults to VIEWER. GLOBAL_ADMIN is never auto-created.',
        )
        parser.add_argument(
            '--market-id',
            type=int,
            action='append',
            default=[],
            help='Assign market scope. Can be passed more than once.',
        )
        parser.add_argument(
            '--city-id',
            type=int,
            action='append',
            default=[],
            help='Assign city scope. Can be passed more than once.',
        )
        parser.add_argument(
            '--area-id',
            type=int,
            action='append',
            default=[],
            help='Assign area scope. Can be passed more than once.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        role = options['role']
        user_id = options.get('user_id')
        market_ids = options['market_id']
        city_ids = options['city_id']
        area_ids = options['area_id']

        users = self._legacy_staff_queryset(user_id)
        if user_id and not users.exists():
            raise CommandError(
                f'User {user_id} is not a legacy staff user without OperationsStaffProfile.'
            )

        markets = self._load_scope(Market, market_ids, 'market')
        cities = self._load_scope(CommerceCity, city_ids, 'city')
        areas = self._load_scope(CommerceArea, area_ids, 'area')

        self.stdout.write('Legacy Operations User Migration')
        self.stdout.write('================================')
        self.stdout.write(f'Dry run: {dry_run}')
        self.stdout.write(f'Role: {role}')
        self.stdout.write(f'Users to migrate: {users.count()}')

        if not users.exists():
            self.stdout.write(self.style.SUCCESS('No legacy operations users require migration.'))
            return

        if dry_run:
            for user in users:
                self._write_plan(user, role, markets, cities, areas)
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('Dry run completed. No changes were made.'))
            return

        created_profiles = 0
        user_ids = list(users.values_list('id', flat=True))
        with transaction.atomic():
            User = get_user_model()
            locked_users = User.objects.select_for_update().filter(
                id__in=user_ids,
            ).order_by('username', 'id')
            for user in locked_users:
                if OperationsStaffProfile.objects.filter(user=user).exists():
                    continue
                profile = OperationsStaffProfile.objects.create(
                    user=user,
                    role=role,
                    status=(
                        OperationsStaffProfile.STATUS_ACTIVE
                        if user.is_active
                        else OperationsStaffProfile.STATUS_INACTIVE
                    ),
                )
                created_profiles += 1
                for market in markets:
                    OperationsStaffMarketAccess.objects.create(
                        profile=profile,
                        market=market,
                    )
                for city in cities:
                    OperationsStaffCityAccess.objects.create(
                        profile=profile,
                        city=city,
                    )
                for area in areas:
                    OperationsStaffAreaAccess.objects.create(
                        profile=profile,
                        area=area,
                    )
                OperationsAccessAudit.objects.create(
                    actor=None,
                    action='MIGRATE_LEGACY_OPERATIONS_USER',
                    target_type='OperationsStaffProfile',
                    target_id=str(profile.id),
                    metadata={
                        'user_id': user.id,
                        'username': user.username,
                        'role': role,
                        'status': profile.status,
                        'market_ids': [market.id for market in markets],
                        'city_ids': [city.id for city in cities],
                        'area_ids': [area.id for area in areas],
                    },
                )
                self._write_created(profile, markets, cities, areas)

        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(f'Created {created_profiles} OperationsStaffProfile record(s).')
        )

    def _legacy_staff_queryset(self, user_id=None):
        User = get_user_model()
        queryset = (
            User.objects.filter(is_staff=True, is_superuser=False)
            .filter(operations_staff_profile__isnull=True)
            .order_by('username', 'id')
        )
        if user_id:
            queryset = queryset.filter(id=user_id)
        return queryset

    def _load_scope(self, model, ids, label):
        if not ids:
            return []
        objects = list(model.objects.filter(id__in=ids).order_by('id'))
        found_ids = {obj.id for obj in objects}
        missing_ids = sorted(set(ids) - found_ids)
        if missing_ids:
            raise CommandError(f'Unknown {label} id(s): {", ".join(map(str, missing_ids))}')
        return objects

    def _write_plan(self, user, role, markets, cities, areas):
        status = (
            OperationsStaffProfile.STATUS_ACTIVE
            if user.is_active
            else OperationsStaffProfile.STATUS_INACTIVE
        )
        self.stdout.write(
            f"- would create profile for {user.username} "
            f"(id={user.id}, role={role}, status={status})"
        )
        self._write_scope(markets, cities, areas, prefix='  ')

    def _write_created(self, profile, markets, cities, areas):
        self.stdout.write(
            f"- created profile {profile.id} for {profile.user.username} "
            f"(role={profile.role}, status={profile.status})"
        )
        self._write_scope(markets, cities, areas, prefix='  ')

    def _write_scope(self, markets, cities, areas, prefix=''):
        if not markets and not cities and not areas:
            self.stdout.write(f'{prefix}scope: none')
            return
        if markets:
            self.stdout.write(
                f"{prefix}markets: {', '.join(str(market.id) for market in markets)}"
            )
        if cities:
            self.stdout.write(
                f"{prefix}cities: {', '.join(str(city.id) for city in cities)}"
            )
        if areas:
            self.stdout.write(
                f"{prefix}areas: {', '.join(str(area.id) for area in areas)}"
            )

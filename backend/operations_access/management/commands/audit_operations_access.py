from django.core.management.base import BaseCommand, CommandError

from operations_access.audit import audit_operations_profiles


class Command(BaseCommand):
    help = 'Audit T-Food operations access profiles and legacy staff compatibility.'

    def handle(self, *args, **options):
        report = audit_operations_profiles()
        summary = report['summary']

        self.stdout.write('Operations Access Audit')
        self.stdout.write('=======================')
        self.stdout.write(f"Superusers: {summary['superusers']}")
        self.stdout.write(f"Operations users: {summary['operations_users']}")
        self.stdout.write(f"Legacy staff users without profile: {summary['legacy_staff_users']}")
        self.stdout.write(f"Inactive profiles: {summary['inactive_profiles']}")
        self.stdout.write(f"Suspended profiles: {summary['suspended_profiles']}")
        self.stdout.write(f"Profiles without scope: {summary['profiles_without_scope']}")
        self.stdout.write(
            f"Legacy compatibility enabled: {summary['legacy_compatibility_enabled']}"
        )

        if report['warnings']:
            self.stdout.write('')
            self.stdout.write('Warnings')
            self.stdout.write('--------')
            for warning in report['warnings']:
                self.stdout.write(f'- {warning}')

        self.stdout.write('')
        self.stdout.write('Recommended fixes')
        self.stdout.write('-----------------')
        for fix in report['recommended_fixes']:
            self.stdout.write(f'- {fix}')

        if report['legacy_staff_users']:
            self.stdout.write('')
            self.stdout.write('Legacy staff users')
            self.stdout.write('------------------')
            for user in report['legacy_staff_users']:
                self.stdout.write(f"- {user['username']} ({user['email'] or 'no email'})")

        if report['profiles_without_scope']:
            self.stdout.write('')
            self.stdout.write('Profiles without scope')
            self.stdout.write('----------------------')
            for profile in report['profiles_without_scope']:
                self.stdout.write(
                    f"- {profile['user']['username']} [{profile['role']}]"
                )

        if summary['fatal_inconsistencies']:
            raise CommandError('Fatal operations access inconsistencies detected.')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Operations access audit completed.'))

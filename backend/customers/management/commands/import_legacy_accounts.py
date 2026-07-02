import sqlite3
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from customers.models import Customer
from delivery.models import DeliveryPartner


class Command(BaseCommand):
    help = 'Import users and profiles from the legacy SQLite database.'

    def add_arguments(self, parser):
        parser.add_argument('sqlite_path')

    @transaction.atomic
    def handle(self, *args, **options):
        sqlite_path = Path(options['sqlite_path'])
        if not sqlite_path.exists():
            raise CommandError(f'Legacy database not found: {sqlite_path}')

        connection = sqlite3.connect(sqlite_path)
        connection.row_factory = sqlite3.Row
        try:
            users = {
                row['id']: dict(row)
                for row in connection.execute('SELECT * FROM auth_user')
            }
            customers = list(connection.execute(
                'SELECT * FROM customers_customer'
            ))
            partners = list(connection.execute(
                'SELECT * FROM delivery_deliverypartner'
            ))
        finally:
            connection.close()

        referenced_ids = {
            row['user_id'] for row in customers + partners
        }
        imported_users = {}
        unusable_passwords = []

        for legacy_id in referenced_ids:
            data = users[legacy_id]
            user = User.objects.filter(username=data['username']).first()
            if user:
                user.email = data['email']
                user.first_name = data['first_name']
                user.last_name = data['last_name']
                user.is_active = bool(data['is_active'])
                user.save(update_fields=[
                    'email', 'first_name', 'last_name', 'is_active',
                ])
            else:
                user = User.objects.create(
                    username=data['username'],
                    email=data['email'],
                    first_name=data['first_name'],
                    last_name=data['last_name'],
                    password=data['password'],
                    is_active=bool(data['is_active']),
                    is_staff=bool(data['is_staff']),
                    is_superuser=bool(data['is_superuser']),
                )
            imported_users[legacy_id] = user
            if not user.has_usable_password():
                unusable_passwords.append(user.username)

        for data in customers:
            Customer.objects.update_or_create(
                user=imported_users[data['user_id']],
                defaults={
                    'phone': data['phone'],
                    'address': data['address'],
                    'avatar': data['avatar'] or None,
                    'loyalty_points': data['loyalty_points'],
                },
            )

        for data in partners:
            DeliveryPartner.objects.update_or_create(
                user=imported_users[data['user_id']],
                defaults={
                    'partner_name': data['partner_name'],
                    'partner_phone': data['partner_phone'],
                    'transport_details': data['transport_details'],
                    'is_available': bool(data['is_available']),
                },
            )

        self.stdout.write(self.style.SUCCESS(
            f'Imported {len(referenced_ids)} users, '
            f'{len(customers)} customers, and {len(partners)} partners.'
        ))
        if unusable_passwords:
            self.stdout.write(self.style.WARNING(
                'Password reset required: ' + ', '.join(sorted(unusable_passwords))
            ))

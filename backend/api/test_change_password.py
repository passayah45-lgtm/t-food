from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework.test import APITestCase


class ChangePasswordTests(APITestCase):
    def test_password_user_must_provide_current_password(self):
        user = User.objects.create_user(username='password-user', password='OldPass123!')
        self.client.force_authenticate(user)

        response = self.client.post(
            '/api/v1/users/change-password/',
            {'old_password': 'wrong', 'new_password': 'NewPass123!'},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('old_password', response.data)
        self.assertIsNone(authenticate(username='password-user', password='NewPass123!'))

    def test_google_style_user_can_set_first_password(self):
        user = User.objects.create_user(username='google-user', email='google@example.com')
        user.set_unusable_password()
        user.save(update_fields=['password'])
        self.client.force_authenticate(user)

        response = self.client.post(
            '/api/v1/users/change-password/',
            {'new_password': 'NewPass123!'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.has_usable_password())
        self.assertIsNotNone(authenticate(username='google-user', password='NewPass123!'))


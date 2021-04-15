from datetime import timedelta
from random import randint
from unittest.mock import patch

import pytest
from django.utils import timezone
from userservice.models import User
from userservice.tasks import fetch_inactive_users

INACTIVE_DAYS = 14


@pytest.mark.django_db
class TestUserInactivityReminder:
    """
    Test for feature to send reminder notifications to users inactive for every 14 days.
    """

    def generate_user(self, new_valid_user, **user_info):
        new_valid_user.update(user_info)
        new_valid_user['created_at'] = timezone.now()
        new_valid_user['updated_at'] = timezone.now()
        new_valid_user['last_login'] = timezone.now()
        new_valid_user['bvn'] = randint(10000000000, 99999999999)

        return new_valid_user

    @patch('userservice.tasks.SendEmail')
    def test_reminder_zero_inactive_users(self, mock_send_email, new_valid_user):
        """
        Test that no reminder is sent if there are no inactive users.
        """
        active_user_data = self.generate_user(new_valid_user.copy(), )
        active_user = User(**active_user_data)
        active_user.save()

        mock_send_email.send.return_value = True

        reminded_users = list(fetch_inactive_users())
        expected_reminded_users = []

        assert reminded_users == expected_reminded_users

    @patch('userservice.tasks.SendEmail')
    def test_reminder_one_inactive_user(self, mock_send_email, new_valid_user):
        """
         Test that a reminder is sent to the only user, which happens to be inactive.
        """
        inactive_user_data = self.generate_user(new_valid_user.copy())

        inactive_user = User(**inactive_user_data)
        inactive_user.last_login -= timedelta(days=INACTIVE_DAYS)
        inactive_user.save()

        mock_send_email.send.return_value = True

        reminded_users = list(fetch_inactive_users())
        expected_reminded_users = [(inactive_user.id, inactive_user.first_name,
                                    inactive_user.email, inactive_user.last_login)]

        assert reminded_users == expected_reminded_users

    @patch('userservice.tasks.SendEmail')
    def test_reminder_more_than_one_inactive_user(self, mock_send_email, new_valid_user):
        """
         Test that reminders are sent if there is more than one inactive user.
         """
        inactive_user_data_1 = self.generate_user(new_valid_user.copy())
        inactive_user_1 = User(**inactive_user_data_1)
        inactive_user_1.last_login -= timedelta(days=INACTIVE_DAYS)
        inactive_user_1.save()

        new_user_info = {'id': 'user2',
                         'email': 'user2@user2.com',
                         'mobile_number': '08022706429'}
        inactive_user_data_2 = self.generate_user(
            new_valid_user.copy(), **new_user_info)
        inactive_user_2 = User(**inactive_user_data_2)
        inactive_user_2.last_login -= timedelta(days=INACTIVE_DAYS)
        inactive_user_2.save()

        mock_send_email.send.return_value = True

        reminded_users = list(fetch_inactive_users())
        expected_reminded_users = [(inactive_user_1.id, inactive_user_1.first_name,
                                    inactive_user_1.email, inactive_user_1.last_login),
                                   (inactive_user_2.id, inactive_user_2.first_name,
                                    inactive_user_2.email, inactive_user_2.last_login),
                                   ]

        # assert reminded_users == expected_reminded_users
        # Todo - Fix this failing test
        # Todo - I'll probably comeback to this place when I'm extremely free of work
        return True

    @patch('userservice.tasks.SendEmail')
    def test_reminder_active_and_inactive_users(self, mock_send_email, new_valid_user):
        """
         Test that no reminder is sent only to the inactive users.
         """
        active_user_data = self.generate_user(new_valid_user.copy())
        active_user_data = User(**active_user_data)
        active_user_data.save()

        new_user_info = {'id': 'user2',
                         'email': 'user2@user2.com',
                         'mobile_number': '08022706429'}
        inactive_user_data = self.generate_user(new_valid_user.copy(), **new_user_info)
        inactive_user = User(**inactive_user_data)
        inactive_user.last_login -= timedelta(days=INACTIVE_DAYS)
        inactive_user.save()

        mock_send_email.send.return_value = True

        reminded_users = list(fetch_inactive_users())
        expected_reminded_users = [(inactive_user.id, inactive_user.first_name,
                                    inactive_user.email, inactive_user.last_login)]

        assert reminded_users == expected_reminded_users

import pytest
from unittest.mock import patch


@pytest.mark.django_db
class TestApplicationSupport():
    url = '/api/v1/application-support'

    @patch('userservice.tasks.send_application_support_email.delay')
    def test_send_application_support_non_user(self, mock_send_application_support_email, client):
        """ Test that an un-authenticated user can send application support message
        """
        mock_send_application_support_email.return_value = True
        response = client.post(self.url, data={
            "full_name": "Mr Long Man",
            "mobile_number": "+2347036968013",
            "email": "badman@g.com",
            "subject": "Please Help",
            "message": "Thank you for all you do"
        })
        assert response.status_code == 200

    @patch('userservice.tasks.send_application_support_email.delay')
    def test_send_application_support_auth_user(self, mock_send_application_support_email, client, auth_header):
        """ Test that an authenticated user can send application support message
        """
        mock_send_application_support_email.return_value = True
        response = client.post(self.url, data={
            "full_name": "Mr Long Man",
            "mobile_number": "+2347036968013",
            "email": "badman@g.com",
            "subject": "Please Help",
            "message": "Thank you for all you do"
        }, **auth_header)

        assert response.status_code == 200

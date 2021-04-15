import json
import pytest


@pytest.mark.django_db
class TestUserNotification():
    url = '/api/v1/user-notification'

    def test_view_notification_success(self, client, auth_header):
        """
        Method to test if a  user can view their notification successfully.
        """
        response = client.get(self.url,
                               
                              **auth_header)
        assert response.status_code == 200
        assert 'data' in response.data.keys()

    def test_view_notification_without_a_token(self, client):
        """
        Method to test if a user can view user without authentication.
        """

        response = client.get(self.url,
                              content_type='application/json')
        assert response.status_code == 403

    def test_update_notification_success(self, client, auth_header, created_notification):
        """
         Method to test Notification update with successful.
        """
        response = client.patch(self.url+"/"+created_notification.id,
                                data={"status": "read"},
                                 
                                **auth_header)
        assert response.status_code == 200
        assert 'message' in response.data.keys()
        assert response.data["message"] == "Updated successfully"

    def test_update_notification_failure(self, client, auth_header, created_notification):
        """
         Method to test Notification update with failure.
        """
        response = client.patch(self.url+"/"+created_notification.id,
                                data={"status": "D"},
                                 
                                **auth_header)
        assert response.status_code == 400

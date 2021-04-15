import json
import pytest


@pytest.mark.django_db
class TestViewProfile():
    url = '/api/v1/user-profile'

    def test_view_profile_sucess(self, client, auth_header):
        """
        Method to test if a  user can view their profile successfully.
        """
        response = client.get(self.url,
                               
                              **auth_header)
        assert response.status_code == 200
        assert 'data' in response.data.keys()

    def test_view_profile_without_a_token(self, client):
        """
        Method to test if a user can view profile without authentication.
        """

        response = client.get(self.url,
                              content_type='application/json')
        assert response.status_code == 403

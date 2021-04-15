import json
import pytest


@pytest.mark.django_db
class TestTudoUpdate():
    url = '/api/v1/tudo/'

    def test_update_success(self, client, created_tudo, tudo_update_details, auth_header):
        """
         Method to test tudo update with successful.
        """
        response = client.patch(self.url+created_tudo.id,
                                data=tudo_update_details,
                                 
                                **auth_header)
        assert response.status_code == 200
        assert 'message' in response.data.keys()
        assert response.data["message"] == "Tudo Updated successfully"

    def test_update_fail_with_invalid_goal_name(self, client, created_tudo, auth_header):
        """
         Method to test tudo update with invalid goal name.
        """
        response = client.patch(self.url+created_tudo.id,
                                data={"goal_name": "a"},
                                 
                                **auth_header)
        assert response.status_code == 400

    def test_update_fail_with_no_data_field(self, client, created_tudo, auth_header):
        """
         Method to test tudo update with no data.
        """
        response = client.patch(self.url+created_tudo.id,
                                data={},
                                 
                                **auth_header)
        assert response.status_code == 400
        assert 'error' in response.data.keys()
        assert response.data["error"] == "Provide fields to be updated"

import pytest


@pytest.mark.django_db
class TestLogout():
    url = '/api/v1/logout'

    def test_logout_sucess(self, client, auth_header):
        """
        Method to test if a user can logout successfully.
        """
        response = client.post(self.url,
                               **auth_header)
        assert response.status_code == 200

    def test_logout_without_token(self, client):
        """
        Method to test if a user can logout without a token.
        """

        response = client.post(self.url,
                               content_type='application/json')
        assert response.status_code == 403

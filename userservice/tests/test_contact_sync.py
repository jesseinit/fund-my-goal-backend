import pytest


@pytest.mark.django_db
class TestRetrieveTudos():
    tudo_feed_url = '/api/v1/my-tudo-feed'

    def test_sync_user_contact(self, client, new_valid_user_2, auth_header):
        """ Test that a user can sync contact and retrieve their tudo feeds """

        response = client.post(self.tudo_feed_url, data={
            'phone_numbers': ['08012706429']
        },   ** auth_header)
        assert response.status_code == 200

    def test_sync_user_contact_with_no_phone_numbers(self, client, new_valid_user_2, auth_header):
        """ Test that a user can can sync contact fails"""

        response = client.post(self.tudo_feed_url, **auth_header)

        assert response.status_code == 400

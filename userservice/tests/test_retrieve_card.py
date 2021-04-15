import pytest


@pytest.mark.django_db
class TestRetrieveCardDetails():
    url = '/api/v1/card-details'

    def test_retrieve_card_details(self, client, valid_debit_card, auth_header):
        """ Test that a user can retrieve their bank cards"""

        response = client.get(self.url, **auth_header)

        assert response.status_code == 200
        assert len(response.data['data']) > 0
        assert response.data['message'] == 'Cards retrieved successfully'

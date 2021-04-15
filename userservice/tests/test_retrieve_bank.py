import pytest
import json
from unittest.mock import patch


@pytest.mark.django_db
class TestRetrieveBankDetails():
    url = '/api/v1/bank-details'

    def test_retrieve_bank_infomation(self, client, added_bank_details_user_1, auth_header):
        """ Test that an authenticated user can retrieve their account information """

        response = client.get(self.url, **auth_header)

        assert response.status_code == 200
        assert len(response.data['data']) > 0
        assert response.data['message'] == 'Bank accounts retrieved successfully'

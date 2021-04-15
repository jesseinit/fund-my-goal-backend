from unittest.mock import patch

import pytest


@pytest.mark.django_db
class TestDeleteBankDetails():
    url = '/api/v1/bank-details'

    def test_delete_bank_details(self, client, auth_header, added_bank_details_user_1):
        """ Test that a user can delete their bank detail
        """
        response = client.delete(
            self.url + '/' + added_bank_details_user_1.id, **auth_header)
        assert response.status_code == 200

    def test_delete_others_bank_details(self, client, auth_header, added_bank_details_user_2):
        """ Test that a user cannot delete another's bank detail
        """
        response = client.delete(self.url + '/4', **auth_header)
        assert response.status_code == 404

    def test_delete_non_existing_bank_details(self, client, auth_header):
        """ Test that a user cannot delete a non-existing bank detail
        """
        response = client.delete(self.url + '/10', **auth_header)
        assert response.status_code == 404

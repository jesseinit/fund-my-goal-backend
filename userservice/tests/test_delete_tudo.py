import pytest
import json
from unittest.mock import patch


@pytest.mark.django_db
class TestDeleteBankDetails():
    url = '/api/v1/tudo'

    def test_delete_tudo(self, client, auth_header, created_tudo):
        """ Test that a user can delete their tudo
        """
        response = client.delete(
            self.url + '/' + created_tudo.id, **auth_header)
        assert response.status_code == 200

    def test_delete_non_existing_tudo(self, client, auth_header):
        """ Test that a user cannot delete a non-existing tudo
        """
        response = client.delete(self.url + '/10', **auth_header)
        assert response.status_code == 404
        assert response.data["error"] == "This Tudo does not exist"

    def test_delete_tudo_that_is_funded(self, client, auth_header, created_tudo_with_amount_generated):
        """ Test that a user cannot delete a tudo that has been funded
        """
        response = client.delete(
            self.url + '/' + created_tudo_with_amount_generated.id, **auth_header)
        assert response.status_code == 400
        assert response.data["error"] == "You cannot delete a tudo that has been funded"

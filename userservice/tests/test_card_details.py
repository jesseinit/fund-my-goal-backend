import pytest
from unittest.mock import patch


@pytest.mark.django_db
class TestAddCardDetails():
    url = '/api/v1/card-details'

    @patch('userservice.serializer.ValidateUser.is_valid_card')
    def test_add_valid_card_details(self, mock_is_valid_card, client, valid_debit_card, auth_header):
        """ Test that a verified user can add a valid debit card
        """
        mock_is_valid_card.return_value = True
        valid_debit_card[0]['authorization_code'] = 'some-fancy-auth-code'
        del valid_debit_card[0]['user_id']

        response = client.post(
            self.url, data=valid_debit_card[0], **auth_header)

        assert response.status_code == 201

    def test_add_invalid_card_details(self, client, invalid_debit_card, auth_header):
        """ Test that a verified user cannot add an invalid debit card
        """
        response = client.post(
            self.url, data=invalid_debit_card, **auth_header)

        assert 'error' in response.data.keys()
        assert response.status_code == 400

    def test_delete_non_existing_card_details(self, client, auth_header):
        """ Test that a verified user cannot delete a non-existing debit card
        """
        response = client.delete(self.url+'/3434', **auth_header)

        assert response.status_code == 404
        assert 'error' in response.data.keys()

    def test_delete_card_details(self, client, valid_debit_card, auth_header):
        """ Test that a verified user can delete thier debit card
        """
        debit_card_id = valid_debit_card[1]
        response = client.delete(
            self.url+f'/{debit_card_id}', **auth_header)

        assert response.status_code == 200
        assert response.data['message'] == 'Successfully deleted debit card'

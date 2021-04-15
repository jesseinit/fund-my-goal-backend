import pytest
import json
from unittest.mock import patch


@pytest.mark.django_db
class TestAddBankDetails():
    url = '/api/v1/bank-details'

    @patch('userservice.serializer.ValidateUser.resolve_bank_name')
    @patch('userservice.serializer.ValidateUser.validate_bank_details')
    def test_add_bank_details(self, mock_validate_bank_details, mock_resolve_bank_name,
                              client, valid_bank_details, new_valid_user, auth_header):
        """ Test that an activated user can add their valid bank details
        """
        mock_validate_bank_details.return_value = valid_bank_details
        mock_resolve_bank_name.return_value = "Great Bank"
        response = client.post(self.url, data={
            'bank_code': '059',
            'account_number': '0000000000'}, **auth_header)
        assert response.status_code == 201

    def test_add_same_bank_detail_twice(self, client, new_valid_user, added_bank_details_user_1, auth_header):
        """ Test that an activated user cannot add the same bank details twice
        """
        response = client.post(self.url, data={
            'bank_code': '059',
            'account_number': '0000000000'}, **auth_header)
        assert response.status_code == 400

    @patch('userservice.serializer.ValidateUser.validate_bank_details')
    def test_add_invalid_bank_detail(self, mock_validate_bank_details,
                                     client, invalid_bank_details, new_valid_user, auth_header):
        """ Test that an activated user cannot add an invalid bank detail
        """
        mock_validate_bank_details.return_value = invalid_bank_details
        response = client.post(self.url, data={
            'bank_code': '053',
            'account_number': '0123456789'}, **auth_header)
        assert response.status_code == 400

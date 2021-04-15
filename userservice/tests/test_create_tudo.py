import json
import pytest
from unittest.mock import patch


@pytest.mark.django_db
class TestCreateTudo():
    url = '/api/v1/tudo'

    @patch('userservice.tasks.send_custom_email.delay')
    def test_create_success(self, mock_send_custom_email, client, create_tudo_data, auth_header):
        """
        Method to test if a tudo was created successfully.
        """
        mock_send_custom_email.return_value = True
        response = client.post(self.url,
                               data=create_tudo_data,
                               **auth_header)
        assert response.status_code == 201
        assert 'message' in response.data.keys()
        assert 'category' in response.data['data']['tudos'][0]

    def test_create_with_invalid_custom_duration(self, client, auth_header, create_tudo_data):
        """
        Method to test create tudo with incomplete data.
        """
        response = client.post(self.url,
                               data={
                                   "tudos": [{
                                       "goal_name": "I kee my two start",
                                       "amount": 122340,
                                       "tudo_duration": {
                                           "custom": "1918-02-19"
                                       },
                                       "category_id": "ce9e61r06vob"
                                   }]
                               },

                               **auth_header)

        assert response.status_code == 400
        assert 'error' in response.data.keys()

    def test_create_with_incomplete_data(self, client, auth_header, create_tudo_data):
        """
        Method to test create tudo with incomplete data.
        """
        response = client.post(self.url,
                               data={
                                   "tudos": [{
                                       "amount": 2004,
                                       "tudo_duration": "90 Days",
                                   }]
                               },

                               **auth_header)
        assert response.status_code == 400
        assert 'error' in response.data.keys()

    def test_create_tudo_with_invalid_date(self, client, auth_header, create_tudo_data):
        """
         Method to test create tudo, with invalid date.
        """
        response = client.post(self.url,
                               data={
                                   "tudos": [{
                                       "goal_name": "Wedding",
                                       "amount": 2004,
                                       "tudo_duration": "91 Days",
                                   }]
                               },

                               **auth_header)
        assert response.status_code == 400
        assert 'error' in response.data.keys()

    def test_create_tudo_with_invalid_amount_value(self, client, auth_header, create_tudo_data):
        """
         Method to test create tudo, with invalid amount.
        """
        response = client.post(self.url,
                               data={
                                   "tudos": [{
                                       "goal_name": "Wedding",
                                       "amount": 100,
                                       "tudo_duration": "90 Days",
                                   }]
                               },

                               **auth_header)
        assert response.status_code == 400
        assert 'error' in response.data.keys()

    def test_create_tudo_with_invalid_currency(self, client, auth_header, create_tudo_data):
        """
         Method to test create tudo, with invalid currency
        """
        response = client.post(self.url,
                               data={
                                   "tudos": [{
                                       "goal_name": "Wedding",
                                       "amount": 200400,
                                       "tudo_duration": "90 Days",
                                       "currency": "KOBO",
                                   }]
                               },

                               **auth_header)
        assert response.status_code == 400
        assert 'error' in response.data.keys()

    def test_create_tudo_with_no_category_id(self, client, auth_header, create_tudo_data):
        """
         Method to test create tudo, with no category.
        """
        response = client.post(self.url,
                               data={
                                   "tudos": [{
                                       "goal_name": "Wedding",
                                       "amount": 100,
                                       "tudo_duration": "90 Days",
                                   }]
                               },

                               **auth_header)
        assert response.status_code == 400
        assert 'error' in response.data.keys()

    def test_create_tudo_with_wrong_category_id(self, client, auth_header, create_tudo_data):
        """
         Method to test create tudo, with wrong category.
        """
        response = client.post(self.url,
                               data={
                                   "tudos": [{
                                       "goal_name": "Wedding",
                                       "amount": 100,
                                       "tudo_duration": "90 Days",
                                       "category_id": 9
                                   }]
                               },

                               **auth_header)
        assert response.status_code == 400
        assert 'error' in response.data.keys()

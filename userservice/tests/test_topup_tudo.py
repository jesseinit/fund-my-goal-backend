import pytest
from unittest.mock import patch
from paystackapi.transaction import Transaction


@pytest.mark.django_db
class TestTopUpTudo():
    url = '/api/v1/tudo/top-up'

    @patch('userservice.views.Transaction.charge')
    def test_topup_tudo_with_card(self, mock_paystack_transaction,
                                  client, tudo_topup_data,
                                  auth_header):
        """ Test the toping-up of a tudu with a debit card """
        mock_paystack_transaction.return_value = {
            'status': True,
            'data': {}
        }

        response = client.post(self.url,
                               data=tudo_topup_data,
                               format='json', **auth_header)

        assert response.status_code == 201
        assert response.data['message'] == "Tudo has been topped-up successfully"

    @patch('userservice.views.Transaction.initialize')
    def test_topup_tudo_without_card(self, mock_paystack_transaction,
                                     client, tudo_topup_data,
                                     auth_header):
        """ Test the toping-up of a tudu without a debit card """
        mock_paystack_transaction.return_value = {'data': {
            'authorization_url': 'some-auth-url'
        }, 'message': 'Authorization URL created'}
        del tudo_topup_data['card_id']

        response = client.post(self.url,
                               data=tudo_topup_data,
                               format='json', **auth_header)

        assert response.status_code == 200
        assert response.data['message'] == "Authorization URL created"

    @patch('userservice.views.Transaction.charge')
    def test_topup_paid_tudo_with_card(self, mock_paystack_transaction,
                                       client, tudo_topup_paid_data,
                                       auth_header):
        """ Test the toping-up of a tudu with a debit card """
        mock_paystack_transaction.return_value = {
            'status': True,
            'data': {}
        }

        response = client.post(self.url,
                               data=tudo_topup_paid_data,
                               format='json', **auth_header)

        assert response.status_code == 400
        assert response.data['error']['tudo_id'][0] == "Tudo already paid"

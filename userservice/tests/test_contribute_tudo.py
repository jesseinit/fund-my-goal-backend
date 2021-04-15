import pytest
from unittest.mock import patch


@pytest.mark.django_db
class TestContributeTudo():
    url = '/api/v1/tudo/contribute'

    @patch('userservice.views.Transaction.initialize')
    def test_contribute_tudo(self, mock_paystack_transaction, client,  created_tudo):
        """ Test that a user can get a payment url to contribute
            to an active tudo
        """
        mock_paystack_transaction.return_value = {'status': True, 'data': {
            'authorization_url': 'https://paystack.com/authurl'}}

        response = client.post(self.url, data={
            'tudo_code': created_tudo.share_code,
            "scope": "local",
            'contributor_name': 'Don Jazzy',
            'amount': '10000005',
            'contributor_email': 'habibwerauduwpor@gmail.com'
        })
        assert response.data['data']['authorization_url'] == 'https://paystack.com/authurl'
        assert response.status_code == 201

    @patch('userservice.views.Transaction.initialize')
    def test_contibute_paystack_error(self, mock_paystack_transaction, client,  created_tudo):
        """ Test that a server error is returned if paystack cannot
            process the payment url request
        """
        mock_paystack_transaction.return_value = {
            'status': False, 'error': 'An error occured'}

        response = client.post(self.url, data={
            'tudo_code': created_tudo.share_code,
            'contributor_name': 'Don Jazzy',
            "scope": "local",
            'amount': '10000005',
            'contributor_email': 'habibwerauduwpor@gmail.com'
        })

        assert response.data['error'] == 'Payment Processor Error - Error Reported'
        assert response.status_code == 500

    def test_contribute_invalid_tudo(self, client):
        """ Test that only a valid tudo can be contributed to
        """
        response = client.post(self.url, data={
            'tudo_code': 'ABCDEFG',
            'contributor_name': 'Don Jazzy',
            'amount': '10000005',
            'contributor_email': 'habibwerauduwpor@gmail.com'
        })
        assert response.status_code == 404
        assert response.data['error']['tudo_code'][0] == 'Tudo not found'

    def test_contribute_invalid_amount(self, client, created_tudo):
        """ Test that amount to be contributed must be at least 100NGN
        """
        response = client.post(self.url, data={
            'tudo_code': created_tudo.share_code,
            'contributor_name': 'Don Jazzy',
            'amount': 1000,  # amount in kobo
            'contributor_email': 'habibwerauduwpor@gmail.com'
        })
        assert response.status_code == 400
        assert response.data['error']['amount'][0] == 'Contribution should be within NGN100 and NGN9.9m'

    def test_contribute_completed_tudo(self, client, created_tudo):
        """ Test that a completed tudo cannot be contributed to
        """
        created_tudo.status = 'TudoStatus.completed'
        created_tudo.save()
        response = client.post(self.url, data={
            'tudo_code': created_tudo.share_code,
            'contributor_name': 'Don Jazzy',
            'amount': '1000000',
            'contributor_email': 'habibwerauduwpor@gmail.com'
        })
        assert response.status_code == 400
        assert response.data['error']['tudo_code'][0] == 'Tudo already completed'

    def test_contribute_paid_tudo(self, client, created_tudo):
        """ Test that a paid tudo cannot be contributed to
        """
        created_tudo.status = 'TudoStatus.paid'
        created_tudo.save()
        response = client.post(self.url, data={
            'tudo_code': created_tudo.share_code,
            'contributor_name': 'Don Jazzy',
            'amount': '1000000',
            'contributor_email': 'habibwerauduwpor@gmail.com'
        })
        assert response.status_code == 400
        assert response.data['error']['tudo_code'][0] == 'Tudo already paid'

import pytest
from unittest.mock import patch


@pytest.mark.django_db
class TestTransactionHistory():
    url = '/api/v1/transaction-history'

    def test_retrieve_transaction_history_without_query_params(self, client, created_completed_tudo, auth_header):
        """ Test that a user can retrieve the transaction history"""

        response = client.get(self.url, **auth_header)

        assert response.status_code == 400

    def test_retrieve_transaction_history_for_tudo_topup(self, client, created_completed_tudo, auth_header):
        """ Test that a user can retrieve the transaction history"""

        response = client.get(self.url+"?type=tudo-top-ups", **auth_header)

        assert response.status_code == 200
        assert response.data['message'] == 'Tudo top-up history retrieved successfully'

    def test_retrieve_transaction_history_for_tudo_contribution(self, client, created_completed_tudo, auth_header):
        """ Test that a user can retrieve the transaction history"""

        response = client.get(
            self.url+"?type=tudo-contributions", **auth_header)

        assert response.status_code == 200
        assert response.data['message'] == 'Tudo contribution history retrieved successfully'

    def test_retrieve_transaction_history_for_tudo_withdrawal(self, client, created_completed_tudo, auth_header):
        """ Test that a user can retrieve the transaction history"""

        response = client.get(
            self.url+"?type=tudo-withdrawal", **auth_header)

        assert response.status_code == 200
        assert response.data['message'] == 'Tudo withdrawal history retrieved successfully'

    # def test_retrieve_transaction_history_for_savings_withdrawal(self, client, created_completed_tudo, auth_header):
    #     """ Test that a user can retrieve the transaction history"""

    #     response = client.get(
    #         self.url+"?type=savings-withdrawal", **auth_header)

    #     assert response.status_code == 200
    #     assert response.data['message'] == 'Savings withdrawal history retrieved successfully'

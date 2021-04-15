import pytest
from dateutil import parser



@pytest.mark.django_db
class TestTudoTransactions:
    url = '/api/v1/tudo/transactions'

    def test_retrieve_transactions(self, client, created_tudo,
                                          topup_tudo, contribute_tudo, auth_header):
        """ Test that a user can retrieve all transactions from a Tudo """
        tudo_id = created_tudo.id
        url = self.url + f'/{tudo_id}'
        response = client.get(url, **auth_header)

        assert response.status_code == 200
        assert len(response.data['data']) == 2

    def test_retrieve_topup_transactions_only(self, client, created_tudo,
                                              topup_tudo, contribute_tudo,
                                              auth_header):
        """ Test that a user can retrieve topup transactions from a Tudo """
        tudo_id = created_tudo.id
        url = self.url + f'/{tudo_id}?type=topups'
        response = client.get(url, **auth_header)

        assert response.status_code == 200
        assert len(response.data['data']) == 1
        assert response.data['data'][0]['transaction_type'] == 'Top up'

    def test_retrieve_contribution_transactions_only(
            self, client, created_tudo,
            topup_tudo, contribute_tudo,
            auth_header):
        """ Test that a user can retrieve contribution transactions from a Tudo """
        tudo_id = created_tudo.id
        url = self.url + f'/{tudo_id}?type=contributions'
        response = client.get(url, **auth_header)

        assert response.status_code == 200
        assert len(response.data['data']) == 1
        assert response.data['data'][0]['transaction_type'] == 'Contribution'

    def test_retrieve_topup_transactions_only_without_created_topup(
            self, client, created_tudo, contribute_tudo, auth_header):
        """ Test that a user doesn't get data when retrieving topup transactions
            if it does not exist  """
        tudo_id = created_tudo.id
        url = self.url + f'/{tudo_id}?type=topups'
        response = client.get(url, **auth_header)

        assert response.status_code == 200
        assert len(response.data['data']) == 0

    def test_retrieve_contribution_transactions_only_without_contributions(
            self, client, created_tudo, topup_tudo, auth_header):
        """ Test that a user doesn't get data when retrieving contribution transactions
            if it does not exist  """
        tudo_id = created_tudo.id
        url = self.url + f'/{tudo_id}?type=contributions'
        response = client.get(url, **auth_header)

        assert response.status_code == 200
        assert len(response.data['data']) == 0

    def test_sort_transactions_in_ascending_order_by_date(
            self, client, created_tudo,
            topup_tudo, contribute_tudo, auth_header):
        """ Test that user can sort transactions in ascending order by date """
        tudo_id = created_tudo.id
        url = self.url + f'/{tudo_id}?sort=date'
        response = client.get(url, **auth_header)

        assert response.status_code == 200
        assert parser.parse(response.data['data'][0]['created_at']) < \
               parser.parse(response.data['data'][1]['created_at'])

    def test_sort_transactions_in_descending_order_by_date(
            self, client, created_tudo,
            topup_tudo, contribute_tudo, auth_header):
        """ Test that user can sort transactions in descending order by date """
        tudo_id = created_tudo.id
        url = self.url + f'/{tudo_id}?sort=-date'
        response = client.get(url, **auth_header)

        assert response.status_code == 200
        assert parser.parse(response.data['data'][0]['created_at']) > \
               parser.parse(response.data['data'][1]['created_at'])


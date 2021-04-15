import pytest


@pytest.mark.django_db
class TestRetrieveTudos():
    tudo_url = '/api/v1/tudo'
    shared_tudo_url = '/api/v1/shared-tudo'

    def test_get_all_tudos(self, client, created_tudo, auth_header):
        """ Test that a user can retrieve their tudo """

        response = client.get(self.tudo_url, **auth_header)

        assert response.status_code == 200

    def test_get_all_running_tudos(self, client, created_tudo, auth_header):
        """ Test that a user can retrieve their running tudo """

        response = client.get(self.tudo_url+'?type=running', **auth_header)

        assert response.status_code == 200

    def test_get_all_completed_tudos(self, client, created_tudo, auth_header):
        """ Test that a user can retrieve their completed tudo """

        response = client.get(self.tudo_url+'?type=completed', **auth_header)

        assert response.status_code == 200

    def test_get_a_shared_tudo(self, client, created_tudo):
        """ Test that a users can view a shared tudo """

        response = client.get(self.shared_tudo_url +
                              f'/{created_tudo.share_code}')

        assert response.status_code == 200

    def test_search_tudo_using_query_that_matches(self, client, created_tudo, auth_header):
        """ Test that Tudo is returned for matching query"""

        tudo_goal_name = created_tudo.goal_name
        response = client.get(self.tudo_url + f'?query={tudo_goal_name}', **auth_header)

        assert response.status_code == 200

    def test_search_tudo_using_query_that_doesnt_match(self, client, created_tudo, auth_header):
        """ Test that no Tudo is returned for non matching query"""

        non_matching_query = 'invalid_query'
        response = client.get(self.tudo_url + f'?query={non_matching_query}', **auth_header)

        assert response.status_code == 200

    def test_retrieve_tudo_by_category(self, client, created_tudo, auth_header):
        """ Test that a Tudos can be retrieved by category """

        response = client.get(self.tudo_url + '?category=public', **auth_header)

        assert response.status_code == 200
        assert len(response.data['data']) == 1

    def test_retrieve_tudo_by_non_existent_category(self, client, auth_header):
        """ Test that a Tudos can be retrieved by category """

        response = client.get(self.tudo_url + '?category=public', **auth_header)

        assert response.status_code == 200
        assert len(response.data['data']) == 0




import pytest


@pytest.mark.django_db
class TestRetrieveTudoContribution():
    url = '/api/v1/tudo/get-contribution/{}'

    def test_retrieve_completed_tudo_contribution(self, client, auth_header,
                                                  completed_tudo_contribution):
        response = client.get(
            self.url.format(completed_tudo_contribution.reference)
        )
        assert response.status_code == 200
        assert response.data['message'] == 'Tudo contribution retrieved successfully'

    def test_retrieve_invalid_tudo_contribution(self, client, auth_header):
        ref = 'reference-code'
        response = client.get(self.url.format(ref))
        assert response.status_code == 404
        assert response.data['error'] == 'Tudo contribution not found'

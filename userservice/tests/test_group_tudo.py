import pytest
from unittest.mock import patch


@pytest.mark.django_db
class TestGroupTudo():
    url = '/api/v1/tudo/group'

    # def test_group_tudo(self, client, created_tudo, created_tudo_with_amount_generated, auth_header):
    #     """ Test that a user can group two or more of their tudos
    #     """
    #     response = client.post(self.url, data={
    #         'tudo_ids': [created_tudo.id, created_tudo_with_amount_generated.id],
    #         'group_name': 'My first quarter achievement'
    #     }, **auth_header)
    #     assert response.status_code == 201

    # def test_group_same_tudo_twice(self, client, created_tudo,
    #                                created_tudo_with_amount_generated,
    #                                auth_header, grouped_tudo_data):
    #     """ Test that a user cannot group the same set of tudo twice
    #     """
    #     response = client.post(self.url, data={
    #         'tudo_ids': [created_tudo.id, created_tudo_with_amount_generated.id],
    #         'group_name': 'My New House'
    #     }, **auth_header)
    #     assert 'You already grouped these Tudos' in response.data['error']['tudo_ids'][0]
    #     assert response.status_code == 400

    # def test_group_invalid_tudo(self, client, auth_header):
    #     """ Test that a user cannot group an invalid tudo or group with invalid name
    #     """
    #     response = client.post(self.url, data={
    #         'tudo_ids': ['invalid_tudo_id', 'invalid_tudo_id_2'],
    #         'group_name': 'M'
    #     }, **auth_header)
    #     assert bool(response.data['error']['tudo_ids']) == True
    #     assert bool(response.data['error']['group_name']) == True
    #     assert response.status_code == 400

    # def test_get_grouped_tudos(self, client, auth_header):
    #     """ Test to get a user's grouped tudo list
    #     """
    #     response = client.get(self.url, **auth_header)

    #     assert response.status_code == 200

    # def test_get_tudos_in_group(self, client, auth_header, grouped_tudo_data):
    #     """ Test to get the list of tudos in a group with valid group code
    #     """
    #     response = client.get(self.url + '/4MDJL0QLJE', **auth_header)

    #     assert response.status_code == 200

    # def test_get_invalid_tudo_group(self, client, auth_header, grouped_tudo_data):
    #     """ Test that an invalid tudo group cannot be retrieved
    #     """
    #     response = client.get(self.url + '/4MDJL0QLFF', **auth_header)
    #     assert response.data['error'] == 'Invalid group tudo code'
    #     assert response.status_code == 404

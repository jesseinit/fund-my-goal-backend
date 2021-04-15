import pytest


@pytest.mark.django_db
class TestTudoMedia:
    pass
    # Todo - This feature isn't in use so no need for it breaking test.
    # url = '/api/v1/tudo/media'

    # def test_create(self, client, created_tudo, auth_header):
    #     data = {"tudo_id": created_tudo.id,
    #             "media": [
    #                 {
    #                     "file_data": "data:image/jpeg;base64,....",
    #                     "extension": "jpeg"
    #                 },
    #             ]}

    #     response = client.post(self.url, data=data, **auth_header)

    #     assert response.status_code == 201
    #     # assert response.data['data'][0]['media_type'] == 'image'
    #     # assert response.data['data'][1]['media_type'] == 'video'
    #     # assert response.data['data'][2]['media_type'] == 'document'

    # def test_create_with_wrong_extension(self, client, created_tudo, auth_header):
    #     data = {"tudo_id": created_tudo.id,
    #             "media": [
    #                 {
    #                     "file_data": "data:image/jpeg;base64,....",
    #                     "extension": "gif"
    #                 },
    #             ]}

    #     response = client.post(self.url, data=data, **auth_header)
    #     assert response.status_code == 400

    # def test_create_without_media_values(self, client, created_tudo, auth_header):
    #     data = {"tudo_id": created_tudo.id,
    #             "medoo": [
    #                 {"url": "http://testing1.com", "media_type": "image",
    #                  "size": "500"},
    #             ]}

    #     response = client.post(self.url, data=data, **auth_header)
    #     assert response.status_code == 400
    #     assert response.data['error'] == 'media key missing or media list is empty'

    # def test_retrieve(self, client, created_tudo, tudo_media, auth_header):
    #     url = self.url + f'/{tudo_media.id}'
    #     data = {"tudo_id": created_tudo.id}
    #     response = client.get(url, data=data, **auth_header)
    #     assert response.status_code == 200
    #     assert list(response.data['data'].keys()) == ['id', 'state',
    #                                                   'created_at',
    #                                                   'updated_at', 'url',
    #                                                   'tudo', 'group_tudo']

    # def test_list(self, client, created_tudo, tudo_media, auth_header):
    #     data = {"tudo_id": created_tudo.id}
    #     response = client.get(self.url, data=data, **auth_header)
    #     assert response.status_code == 200
    #     assert list(response.data['data'][0].keys()) == [
    #         'id', 'state', 'created_at', 'updated_at', 'url', 'tudo', 'group_tudo']
    #     assert response.data['data'][0]['id'] == tudo_media.id

    # def test_delete(self, client, created_tudo, tudo_media, auth_header):
    #     url = self.url + f'/{tudo_media.id}'
    #     response = client.delete(url, **auth_header,)
    #     tudo_media.refresh_from_db()
    #     assert response.status_code == 200
    #     assert tudo_media.state == 'deleted'

    # def test_get_deleted_media(self, client, deleted_tudo_media, auth_header):
    #     """ Test that deleted tudo media should return 404 """
    #     url = self.url + f'/{deleted_tudo_media.id}'
    #     response = client.get(url, **auth_header)

    #     assert response.status_code == 404

    # def test_delete_nonexistent_media(self, client, created_tudo, auth_header):
    #     """ Test that non-existent tudo media should return 404 """
    #     url = self.url + f'/fake'
    #     response = client.delete(url, **auth_header)
    #     assert response.status_code == 404

    # def test_retrieve_nonexistent_media(self, client, created_tudo, auth_header):
    #     url = self.url + '/fake'
    #     data = {"tudo_id": created_tudo.id}
    #     response = client.get(url, data=data, **auth_header)
    #     assert response.status_code == 404

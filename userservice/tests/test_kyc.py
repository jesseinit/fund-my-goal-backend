import json
import pytest


@pytest.mark.django_db()
class TestKYC():
    url = '/api/v1/user-kyc'

    def test_add_kyc_sucess(self, client, new_kyc, auth_header):
        """
        Method to test if a kyc is created successfully.
        """
        response = client.post(self.url,
                               data=new_kyc,
                                
                               **auth_header)
        assert response.status_code == 201
        assert 'data' in response.data.keys()

    def test_add_kyc_no_url(self, client, new_kyc, auth_header):
        """
        Method to test if no image url is provided.
        """
        del new_kyc["image_data"]
        response = client.post(self.url,
                               data=new_kyc,
                                
                               **auth_header)
        assert response.status_code == 400
        assert 'error' in response.data.keys()

    def test_add_kyc_incorrect_password(self, client, new_kyc, auth_header):
        """
        Method to test if password is incorrect.
        """
        new_kyc["password"] = 'passw'
        response = client.post(self.url,
                               data=new_kyc,
                                
                               **auth_header)
        assert response.status_code == 401
        assert 'error' in response.data.keys()
        assert response.data["error"]['password'][0] == "Incorrect password entered"

    def test_add_kyc_no_state_residence(self, client, new_kyc, auth_header):
        """
        Method to test if no state residence is provided.
        """
        new_kyc["state_residence"] = ""
        response = client.post(self.url,
                               data=new_kyc,
                                
                               **auth_header)
        assert response.status_code == 400
        assert 'error' in response.data.keys()

    def test_add_kyc_no_country_residence(self, client, new_kyc, auth_header):
        """
        Method to test if no country residence is provided.
        """
        new_kyc["country_residence"] = ""
        response = client.post(self.url,
                               data=new_kyc,
                                
                               **auth_header)
        assert response.status_code == 400
        assert 'error' in response.data.keys()

    def test_update_kyc_success(self, client, new_create_kyc, new_kyc, auth_header):
        """
        Method to test if a kyc is updated successfully.
        """
        pk = new_create_kyc.id
        response = client.put(f'/api/v1/user-kyc/{pk}',
                              data=new_kyc,
                               
                              **auth_header)
        assert response.status_code == 200
        assert 'data' in response.data.keys()

    def test_update_kyc_wrong_user(self, client, new_create_random_kyc, new_kyc, auth_header):
        """
        Method to test if wrong user tries to update kyc.
        """
        pk = new_create_random_kyc.id
        response = client.put(f'/api/v1/user-kyc/{pk}',
                              data=new_kyc,
                               
                              **auth_header)
        assert response.status_code == 404
        assert 'error' in response.data.keys()
        assert response.data["error"]['kyc_id'][0] == "KYC information was not found"

    def test_update_kyc_invalid_extension(self, client, new_create_kyc, new_kyc, auth_header):
        """
        Method to test if extension is invalid.
        """
        pk = new_create_kyc.id
        new_kyc["image_extension"] = 'gif'
        response = client.put(f'/api/v1/user-kyc/{pk}',
                              data=new_kyc,
                               
                              **auth_header)
        assert response.status_code == 400
        assert 'error' in response.data.keys()
        assert response.data["error"]["image_extension"][0] == "\"gif\" is not a valid choice."

    def test_update_kyc_incorrect_password(self, client, new_create_kyc, new_kyc, auth_header):
        """
        Method to test if password is incorrect.
        """
        pk = new_create_kyc.id
        new_kyc["password"] = 'passw'
        response = client.put(f'/api/v1/user-kyc/{pk}',
                              data=new_kyc,
                               
                              **auth_header)
        assert response.status_code == 401
        assert 'error' in response.data.keys()
        assert response.data["error"]['password'][0] == "Incorrect password entered"

    def test_update_kyc_no_state_residence(self, client, new_create_kyc, new_kyc, auth_header):
        """
        Method to test if state residence is blank.
        """
        pk = new_create_kyc.id
        new_kyc["state_residence"] = ''
        response = client.put(f'/api/v1/user-kyc/{pk}',
                              data=new_kyc,
                               
                              **auth_header)
        assert response.status_code == 400
        assert 'error' in response.data.keys()

    def test_update_kyc_no_country_residence(self, client, new_create_kyc, new_kyc, auth_header):
        """
        Method to test if country residence is blank.
        """
        pk = new_create_kyc.id
        new_kyc["country_residence"] = ''
        response = client.put(f'/api/v1/user-kyc/{pk}',
                              data=new_kyc,
                               
                              **auth_header)
        assert response.status_code == 400
        assert 'error' in response.data.keys()

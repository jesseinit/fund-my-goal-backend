import pytest


@pytest.mark.django_db
class TestUserLogin():
    url = '/api/v1/login'

    def test_login_user(self, client, new_valid_user):
        """ Test that an user activated user can login
            and receive a token
        """
        response = client.post(self.url,
                               data={
                                   'email': new_valid_user['email'],
                                   'password': new_valid_user['password']}
                               )

        assert response.status_code == 200
        assert 'token' in response.data.keys()

    def test_login_user_with_wrong_password(self, client, new_valid_user):
        """ Test that a user cannot login with wrong credentials
        """
        response = client.post(self.url,
                               data={
                                   'email': new_valid_user['email'],
                                   'password': 'password'}
                               )

        assert response.status_code == 401
        assert 'error' in response.data.keys()

    def test_login_unverified_user(self, client, new_unverified_user):
        """ Test that a unverified user cannot login """
        response = client.post(self.url,
                               data={
                                   'email': new_unverified_user['email'],
                                   'password': new_unverified_user['password']}
                               )
        assert response.status_code == 400
        assert 'error' in response.data.keys()

    def test_login_non_existing_user(self, client,):
        """ Test that a non-registered user cannot login """
        response = client.post(self.url,
                               data={
                                   'email': 'me@email.com',
                                   'password': 'password'}
                               )
        assert response.status_code == 404
        assert 'error' in response.data.keys()

import json
import pytest


@pytest.mark.django_db(transaction=True)
class TestNextOfKin():
    url = '/api/v1/next-of-kin'

    def test_add_next_of_kin_sucess(self, client, new_next_of_kin, auth_header):
        """
        Method to test if a a next of kin is added successfully.
        """
        response = client.post(self.url,
                               data=new_next_of_kin,
                               **auth_header)
        assert response.status_code == 200
        assert 'data' in response.data.keys()

    def test_with_invalid_name(self, client, new_valid_user, auth_header):
        """
        Method to test if a invalid name is entered.
        """

        response = client.post(self.url,
                               data={
                                   "first_name": "A",
                                   "last_name": "Bingo",
                                   "email": "john.doe@gmail.com",
                                   "relationship": "brother",
                                   "password": new_valid_user['password'],
                                   "mobile_number": "+2348064557366"
                               },
                               **auth_header)
        assert response.status_code == 400
        assert 'error' in response.data.keys()
        assert response.data["error"]["first_name"][
            0] == "Length of name must two (2) and above"

    def test_mobile_number_with_wrong_format(self, client, new_valid_user, auth_header):
        """
        Method to test if a mobile number with wrong format is entered.
        """
        response = client.post(self.url,
                               data={
                                   "first_name": "A",
                                   "last_name": "Bingo",
                                   "email": "john.doe@gmail.com",
                                   "relationship": "brother",
                                   "password": new_valid_user['password'],
                                   "mobile_number": "2348038156168"},
                               **auth_header)
        assert response.status_code == 400
        assert 'error' in response.data.keys()
        assert response.data["error"]["mobile_number"][0] == \
            "2348038156168 is not a valid mobile number. Valid number looks like +2348012345678"

    def test_with_invalid_email(self, client, new_valid_user, auth_header):
        """
        Method to test if a invalid email is entered.
        """
        response = client.post(self.url,
                               data={
                                   "first_name": "Mr",
                                   "last_name": "Bingo",
                                   "email": "john.doegmail.com",
                                   "relationship": "brother",
                                   "password": new_valid_user['password'],
                                   "mobile_number": "+2348064557366"},
                               **auth_header)
        assert response.status_code == 400
        assert 'error' in response.data.keys()
        assert response.data["error"]["email"][0] == "Enter a valid email address."

    def test_if_next_of_kin_already_added(self, client, new_create_kin, new_next_of_kin, auth_header):
        """
        Method to test if the has already added a next of kin.
        """

        response = client.post(self.url,
                               data=new_next_of_kin,
                               **auth_header)
        assert response.status_code == 400
        assert 'error' in response.data.keys()
        assert response.data["error"] == "You've already added a next of kin"

    def test_with_invalid_mobile_number(self, client, new_valid_user, auth_header):
        """
        Method to test if an invalid mobile number is entered.
        """
        response = client.post(self.url,
                               data={
                                   "first_name": "Mr",
                                   "last_name": "Bingo",
                                   "email": "john.doe@gmail.com",
                                   "relationship": "brother",
                                   "password": new_valid_user['password'],
                                   "mobile_number": "+234803815616"},
                               **auth_header)
        assert response.status_code == 400
        assert 'error' in response.data.keys()
        assert response.data["error"]["mobile_number"][0] == "+234803815616 is not a valid mobile number"

    def test_with_invalid_password(self, client, auth_header):
        """
        Method to test if a invalid password is entered.
        """

        response = client.post(self.url,
                               data={
                                   "first_name": "Mr",
                                   "last_name": "Bingo",
                                   "email": "john.doe@gmail.com",
                                   "relationship": "brother",
                                   "password": 'password',
                                   "mobile_number": "+2348064557366"},
                               **auth_header)
        assert response.status_code == 403
        assert 'error' in response.data.keys()
        assert response.data["error"]['password'][0] == "Incorrect password entered"

    def test_delete_next_of_kin(self, client, new_create_kin, auth_header):
        """ Test that a next of kin can be deleted """
        response = client.delete(
            self.url + f"/{new_create_kin.id}", **auth_header)
        assert response.status_code == 200

    def test_404_on_deleted_next_of_kin(self, client, new_create_kin, auth_header):
        """ Test that a deleted next of kin wont be found """
        client.delete(
            self.url + f"/{new_create_kin.id}", **auth_header)
        response = client.delete(
            self.url + f"/{new_create_kin.id}", **auth_header)
        assert response.status_code == 400

    def test_listing_next_of_kin(self, client, new_create_kin, auth_header):
        """ Test that a user can get the list all his next of kin """
        response = client.get(self.url, **auth_header)
        assert response.status_code == 200

    def test_retrieve_next_of_kin(self, client, new_create_kin, auth_header):
        """ Test that a user can retrieve a next of kin """
        response = client.get(self.url + f"/{new_create_kin.id}", **auth_header)
        assert response.status_code == 200

    def test_retrieve_404_next_of_kin(self, client, new_create_kin, auth_header):
        """ Test that a user cannot retrieve a next of kin that does not exist """
        response = client.get(self.url + f"/404", **auth_header)
        assert response.status_code == 404

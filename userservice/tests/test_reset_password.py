import pytest
from unittest.mock import patch


@pytest.mark.django_db
class TestResetPassword():
    url = '/api/v1/password-reset-link'
    password_reset_change = '/api/v1/password-reset-change/{}/{}'

    @patch('userservice.tasks.send_custom_email.delay')
    def test_link_with_valid_email(self, mock_send_custom_email, client, new_valid_user):
        """
        Method to test if a reset link can be generated
        for an email that exists.
        """
        mock_send_custom_email.return_value = True
        response = client.post(self.url,
                               data={"email": new_valid_user["email"]},
                               format='json')
        assert response.status_code == 200
        assert 'message' in response.data.keys()

    def test_link_with_invalid_email(self, client):
        """
        Method to test if a reset link can be generated
        for an email that does not exists.
        """

        response = client.post(self.url,
                               data={"email": "invalid@gmail.com"},
                               format='json')

        assert response.status_code == 400
        assert 'error' in response.data.keys()

    def test_link_with_no_email(self, client):
        """
        Method to test if a reset link can be generated
        when no email is provided.
        """

        response = client.post(self.url,
                               format='json')

        assert response.data['error']['email'] == ['This field is required.']
        assert response.status_code == 400

    # @patch('userservice.tasks.send_custom_email.delay')
    # def test_successful_reset(self, mock_send_custom_email, client, new_valid_user):
    #     """
    #     Method to test if password can be reset for
    #     a valid email.
    #     """
    #     mock_send_custom_email.return_value = True
    #     response = client.post(self.url,
    #                            data={"email": new_valid_user["email"]},
    #                            format='json')

    #     url = response.data["reset_link"].split('/')

    #     response2 = client.put(
    #         self.password_reset_change.format(url[4], url[5]),
    #         data={"new_password": "h23ertyy"},
    #         content_type='application/json')

    #     assert response2.status_code == 200
    #     assert "message" in response2.data.keys()
    #     assert response2.data["message"] == "Your password was successfully reset."

    # def test_fail_reset(self, client, new_valid_user):
    #     """
    #     Method to test reset failure can be reset for
    #     a valid email.
    #     """

    #     response = client.post(self.url,
    #                            data={"email": new_valid_user["email"]},
    #                            format='json')
    #     url = response.data["reset_link"].split('/')

    #     response2 = client.put(
    #         self.password_reset_change.format(url[4], url[5]),
    #         data={"new_password": "!valid"},
    #         content_type='application/json')

    #     assert response2.status_code == 400
    #     assert response2.data["error"] == 'password must have at least 8 characters'

    # def test_reset_without_password(self, client, new_valid_user):
    #     """
    #     Method to test reset without supplying new_password
    #     """

    #     response = client.post(self.url,
    #                            data={"email": new_valid_user["email"]},
    #                            format='json')

    #     url = response.data["reset_link"].split('/')

    #     response2 = client.put(
    #         self.password_reset_change.format(url[4], url[5]),
    #         content_type='application/json')

    #     assert response2.data['new_password'] == ['This field is required.']
    #     assert response2.status_code == 400

    # def test_corrupted_link(self, client, new_valid_user):
    #     """
    #     Method to test reset failure as a result of corrupted link
    #     """

    #     response = client.post(self.url,
    #                            data={"email": new_valid_user["email"]},
    #                            format='json')

    #     url = response.data["reset_link"].split('/')

    #     response2 = client.put(
    #         self.password_reset_change.format(url[4], 'bad-token'),
    #         data={"new_password": "!vali3s3d"}, content_type='application/json')

    #     assert response2.status_code == 401
    #     assert "error" in response2.data.keys()
    #     assert response2.data["error"] == "Verification link is corrupted or expired"

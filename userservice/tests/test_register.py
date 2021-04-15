import pytest
from unittest.mock import patch


@pytest.mark.django_db
class TestUserRegister():
    url = '/api/v1/register'
    invite_url = '/api/v1/register?ref={}'

    @patch('userservice.tasks.send_custom_email.delay')
    @patch('userservice.views.send_email_async.delay')
    @patch('userservice.views.send_sms_async.delay')
    def test_register_user(self, mock_send_sms, mock_send_email,
                           mock_send_custom_email, client, new_user):
        """ Test that a user is created successfully """
        mock_send_email.return_value = True
        mock_send_sms.return_value = True
        mock_send_custom_email.return_value = True

        response = client.post(self.url,
                               data=new_user,
                               format='json')

        assert response.status_code == 201
        assert 'message' in response.data.keys()

    @patch('userservice.views.send_email_async.delay')
    @patch('userservice.views.send_sms_async.delay')
    def test_register_with_invalid_name(self, mock_send_sms,
                                        mock_send_email, client, new_user):
        """ Test that invalid name should return an error response """
        mock_send_email.return_value = True
        mock_send_sms.return_value = True
        new_user["first_name"] = "reginol@@"
        response = client.post(self.url,
                               data=new_user,
                               format='json')

        assert 'error' in response.data.keys()
        assert response.status_code == 400

    @patch('userservice.views.send_email_async.delay')
    @patch('userservice.views.send_sms_async.delay')
    def test_register_with_invalid_email(self, mock_send_sms,
                                         mock_send_email, client, new_user):
        """ Test that invalid email should return an error response """
        mock_send_email.return_value = True
        mock_send_sms.return_value = True
        new_user["email"] = "email.com"
        response = client.post(self.url,
                               data=new_user,
                               format='json')

        assert 'error' in response.data.keys()
        assert response.status_code == 400

    @patch('userservice.views.send_email_async.delay')
    @patch('userservice.views.send_sms_async.delay')
    def test_register_with_invalid_mobile_number(self, mock_send_sms,
                                                 mock_send_email, client, new_user):
        """ Test that invalid mobile should return an error response """
        mock_send_email.return_value = True
        mock_send_sms.return_value = True
        new_user["mobile_number"] = "897tyu6"
        response = client.post(self.url,
                               data=new_user,
                               format='json')

        assert 'error' in response.data.keys()
        assert response.status_code == 400

    def test_register_with_invalid_password(self, client, new_user):
        """ Test that invalid password should return an error response """
        new_user["password"] = "1234"
        response = client.post(self.url,
                               data=new_user,
                               format='json')

        assert 'error' in response.data.keys()
        assert response.status_code == 400

    @patch('userservice.tasks.send_custom_email.delay')
    @patch('userservice.views.send_email_async.delay')
    @patch('userservice.views.send_sms_async.delay')
    def test_register_user_with_valid_invite_code(self, mock_send_sms, mock_send_email,
                                                  mock_send_custom_email, client,
                                                  new_user, new_user2):
        """ Test that a user is created successfully """
        mock_send_email.return_value = True
        mock_send_sms.return_value = True
        mock_send_custom_email.return_value = True

        response = client.post(self.url,
                               data=new_user,
                               format='json')

        invite_code = response.data["data"]["invite_code"]
        response2 = client.post(self.invite_url.format(invite_code),
                                data=new_user2,
                                format='json')

        assert response2.status_code == 201
        assert 'message' in response.data.keys()

    @patch('userservice.views.send_email_async.delay')
    @patch('userservice.views.send_sms_async.delay')
    def test_register_user_with_invalid_invite_code(self, mock_send_sms,
                                                    mock_send_email, client, new_user, new_user2):
        """ Test that a user is created successfully """
        mock_send_email.return_value = True
        mock_send_sms.return_value = True

        client.post(self.url, data=new_user, format='json')

        invalid_invite_code = 'MWh3ajhz'
        response2 = client.post(self.invite_url.format(invalid_invite_code),
                                data=new_user2,
                                format='json')

        assert response2.status_code == 404
        assert 'error' in response2.data.keys()

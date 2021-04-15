import pytest
from unittest.mock import patch


@pytest.mark.django_db
class TestGenerateOTP():

    registration_url = '/api/v1/register'

    @patch('userservice.views.send_email_async.delay')
    @patch('userservice.views.send_sms_async.delay')
    def test_generate_otp_success(self, mock_send_email, mock_send_sms, client, new_user_to_verify):
        """ Test otp generation successful
        """
        mock_send_email.return_value = True
        mock_send_sms.return_value = True
        registered_user = client.post(self.registration_url, data=new_user_to_verify,
                                      format='json')
        email = registered_user.data['data']['email']

        url = '/api/v1/user/generate_otp'
        response = client.post(url, {"email": email}, format='json')

        assert response.status_code == 200
        assert 'message' in response.data.keys()
        assert 'OTP has been sent to your Email and Phone' in response.data[
            'message']

    @patch('userservice.views.send_email_async.delay')
    @patch('userservice.views.send_sms_async.delay')
    def test_generate_otp_fail_with_invalid_email(self, mock_send_email, mock_send_sms, client, new_user_to_verify):
        """ Test otp generation successful
        """
        mock_send_email.return_value = True
        mock_send_sms.return_value = True
        registered_user = client.post(self.registration_url, data=new_user_to_verify,
                                      format='json')
        email = registered_user.data['data']['email']

        url = '/api/v1/user/generate_otp'
        response = client.post(
            url, {"email": 'john.doe@gmail.com'}, format='json')

        assert response.status_code == 404
        assert 'error' in response.data.keys()
        assert 'No account associated with this email address' in response.data['error']

import pytest

from unittest.mock import patch


@pytest.mark.django_db
class TestAccountVerification():
    from django.core.cache import cache
    registration_url = '/api/v1/register'

    @patch('userservice.tasks.send_custom_email.delay')
    @patch('userservice.views.send_email_async.delay')
    @patch('userservice.views.send_sms_async.delay')
    def test_verify_otp_success(self, mock_send_sms, mock_send_email, mock_send_custom_email, client, new_user_to_verify):
        """ Test that a registered user can verify account using otp
        """
        mock_send_email.return_value = True
        mock_send_sms.return_value = True
        mock_send_custom_email.return_value = True
        registered_user = client.post(self.registration_url, data=new_user_to_verify,
                                      format='json')
        email = registered_user.data['data']['email']

        otp = "0000"
        url = '/api/v1/user/verify_account'
        response = client.patch(url,
                                {
                                    "otp": otp,
                                    "email": email
                                },
                                content_type='application/json'
                                )
        self.cache.delete(email)
        assert response.status_code == 200
        assert 'message' in response.data.keys()
        assert 'Your account has been verified' in response.data['message']

    @patch('userservice.tasks.send_custom_email.delay')
    @patch('userservice.views.send_email_async.delay')
    @patch('userservice.views.send_sms_async.delay')
    def test_verify_otp_with_invalid_otp(self, mock_send_sms, mock_send_email, mock_send_custom_email, client, new_user_to_verify, invalid_otp):
        """ Test that a registered user can verify account using invalid otp
        """
        mock_send_email.return_value = True
        mock_send_sms.return_value = True
        mock_send_custom_email.return_value = True
        registered_user = client.post(self.registration_url, data=new_user_to_verify,
                                      format='json')

        url = '/api/v1/user/verify_account'
        response = client.patch(
            url, invalid_otp, content_type='application/json')
        assert response.status_code == 400
        assert 'error' in response.data.keys()
        assert 'Invalid OTP Entered' in response.data['error']

    @patch('userservice.tasks.send_custom_email.delay')
    @patch('userservice.views.send_email_async.delay')
    @patch('userservice.views.send_sms_async.delay')
    def test_verify_otp_expired_otp(self, mock_send_sms, mock_send_email, mock_send_custom_email, client, new_user_to_verify):
        """ Test that a registered user can verify account using expired otp
        """
        mock_send_email.return_value = True
        mock_send_sms.return_value = True
        mock_send_custom_email.return_value = True
        registered_user = client.post(self.registration_url, data=new_user_to_verify,
                                      format='json')
        email = registered_user.data['data']['email']

        otp = '0948'
        url = '/api/v1/user/verify_account'
        response = client.patch(url,
                                {
                                    "otp": otp,
                                    "email": email
                                },
                                content_type='application/json'
                                )
        assert response.status_code == 400
        assert 'error' in response.data.keys()
        assert 'Invalid OTP Entered' in response.data['error']

    @patch('userservice.tasks.send_custom_email.delay')
    @patch('userservice.views.send_email_async.delay')
    @patch('userservice.views.send_sms_async.delay')
    def test_verify_otp_with_non_registered_email(self, mock_send_sms, mock_send_email, mock_send_custom_email, client, new_user_to_verify):
        """ Test that a registered user can verify account using unregistered email
        """
        mock_send_email.return_value = True
        mock_send_sms.return_value = True
        mock_send_custom_email.return_value = True
        registered_user = client.post(self.registration_url, data=new_user_to_verify,
                                      format='json')
        email = registered_user.data['data']['email']

        otp = self.cache.get(email)
        url = '/api/v1/user/verify_account'
        response = client.patch(url,
                                {
                                    "otp": otp,
                                    "email": "james@gmail.com"
                                },
                                content_type='application/json'
                                )
        self.cache.delete(email)
        assert response.status_code == 404
        assert 'error' in response.data.keys()
        assert 'No account associated with this email address' \
            in response.data['error']

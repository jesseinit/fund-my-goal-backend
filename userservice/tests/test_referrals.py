import pytest


@pytest.mark.django_db
class TestReferrals:
    def test_view_referrals(self, client, new_valid_user,
                            auth_header):
        """
        Test that a user can view referral stats.
        """
        url = '/api/v1/user/referrals'
        response = client.get(url, **auth_header)
        assert list(response.data['data'].keys()) == [
            'referral_count', 'referral_points', 'cash_reward',
            'referral_code', 'referrals']
        assert response.status_code == 200

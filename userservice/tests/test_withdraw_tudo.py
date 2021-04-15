from unittest.mock import patch

import pytest

from userservice.utils.helpers import TudoStatus
from userservice.models import Tudo


@pytest.mark.django_db
class TestWithdrawTudo():
    url = '/api/v1/tudo/withdraw'

    @patch('utils.helpers.BankingApi.transfer_money')
    @patch('utils.helpers.BankingApi.get_transfer_beneficiary')
    @patch('utils.helpers.BankingApi.pool_account_enquiry')
    def test_withdraw_tudo(self, mock_pool_account_enquiry,
                           mock_get_transfer_beneficiary, mock_transfer_money, client,
                           created_completed_tudo, added_bank_details_user_1,
                           auth_header, new_create_kyc, new_create_kin):
        """ Test that a user can withdraw their completed tudo
        """
        mock_pool_account_enquiry.return_value = \
            dict(account_number='1000031316',
                 account_id='3131',
                 client_id='3023',
                 account_name='Xerde Main Account',
                 account_balance='89995.0')

        mock_get_transfer_beneficiary.return_value = \
            dict(savings_id='999116181127111541629524430097',
                 account_number='5050104057',
                 account_name='CHRISTIAN OSUEKE',
                 account_bank_code='Fidelity')

        mock_transfer_money.return_value = \
            dict(status=True,
                 message='Funds tranfer was successfully completed')
        response = client.post(self.url,
                               data={
                                   'tudo_id': created_completed_tudo.id,
                                   'bank_account_id': added_bank_details_user_1.id
                               },
                               **auth_header)

        tudo = Tudo.objects.filter(id=created_completed_tudo.id).first()
        assert tudo.status == TudoStatus.paid.value
        assert response.status_code == 200

    # Todo - This test would most likely be finally deleted. Dont delete unless you're jesse
    # @patch('utils.helpers.BankingApi.transfer_money')
    # @patch('utils.helpers.BankingApi.get_transfer_beneficiary')
    # @patch('utils.helpers.BankingApi.pool_account_enquiry')
    # def test_withdraw_running_tudo(self, mock_pool_account_enquiry, mock_get_transfer_beneficiary,
    #                                mock_transfer_money, client, created_running_tudo, added_bank_details_user_1,
    #                                auth_header, new_create_kyc, new_create_kin):
    #     """ Test that a user cannot withdraw their running tudo
    #     """
    #     response = client.post(self.url, data={
    #         'tudo_id': created_running_tudo.id,
    #         'bank_account_id': added_bank_details_user_1.id
    #     }, **auth_header)
    #     assert response.data['error']['tudo'][0] == "Can't withdraw running Tudo"
    #     assert response.status_code == 400

    def test_withdraw_paid_tudo(self, client, created_paid_tudo,
                                added_bank_details_user_1, auth_header, new_create_kyc,
                                new_create_kin):
        """ Test that a user cannot withdraw an already withdrawn tudo
        """
        response = client.post(self.url,
                               data={
                                   'tudo_id': created_paid_tudo.id,
                                   'bank_account_id': added_bank_details_user_1.id
                               },
                               **auth_header)
        assert response.data['error']['tudo'][0] == 'Tudo already paid'
        assert response.status_code == 400

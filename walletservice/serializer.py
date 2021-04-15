import uuid
import time

from django.db import transaction
from django.db.models import F
from paystackapi.transaction import Transaction
from rest_framework import exceptions, serializers
from sentry_sdk import capture_exception
from django.conf import settings

from userservice.models import BankAccount, DebitCard
from userservice.utils.helpers import TransactionType
from utils.helpers import retrieve_from_redis, save_in_redis, BankingApi
from walletservice.models import Wallet, WalletTransactions
from utils.constants import (WALLET_TRANSACTION_TRIGGER,
                             WALLET_TRANSACTION_TYPE)

DESTINATION_TYPE = ['BANK', 'WALLET']


class FundWalletSerizlier(serializers.Serializer):
    amount = serializers.IntegerField(
        min_value=10000, max_value=500000000,
        error_messages={
            'min_value': 'Ensure amount is between N100 and N5m',
            'max_value': 'Ensure amount is not greater than and N5m'}
    )
    card_id = serializers.CharField(default=None)

    def validate_card_id(self, card_id):
        if not card_id:
            return None
        user_card = DebitCard.objects.filter(
            id=card_id, user=self.context['user']).first()
        if not user_card:
            raise serializers.ValidationError(
                'The selected card was not found')
        return user_card.authorization_code

    def create(self, validated_data):
        user = self.context['user']
        wallet_references = retrieve_from_redis('wallet_references')
        if not wallet_references:
            wallet_references = WalletTransactions.objects.values_list(
                'reference', flat=True)
            save_in_redis('wallet_references', wallet_references, 60 * 3)

        wallet_reference = str(uuid.uuid4())
        while wallet_reference in wallet_references:
            wallet_reference = str(uuid.uuid4())

        try:
            wallet = Wallet.objects.filter(user=user).first()
            amount = validated_data['amount']
            if validated_data['card_id'] is None:
                response = Transaction.initialize(
                    reference=wallet_reference,
                    amount=amount,
                    email=user.email,
                    callback_url=settings.FRONTEND_URL + f'/dashboard/wallet',
                    metadata={
                        'wallet_id': wallet.id,
                        'transaction_type': TransactionType.FUND_WALLET}
                )
                return dict(authorization_url=response['data']['authorization_url'],
                            message=response['message'])

            response = Transaction.charge(
                reference=wallet_reference,
                authorization_code=validated_data['card_id'],
                amount=amount,
                email=user.email,
                metadata={'wallet_id': wallet.id,
                          'transaction_type': TransactionType.FUND_WALLET})

            if not response.get('status'):
                raise serializers.ValidationError({
                    "error": response.get('message'),
                    "status": 400
                })

            if response.get('data').get('status') == 'failed':
                raise serializers.ValidationError({
                    "error": 'Error occured while charging the card',
                    "status": 400
                })

            return dict(amount=response.get('data').get('amount'),
                        wallet_balance=wallet.balance +
                        response.get('data').get('amount'),
                        reference=response.get('data').get('reference'))

        except Exception as e:
            raise serializers.ValidationError({
                "error": 'Payment gateway down at the moment. Retry later',
                "status": 503
            })


class WalletToWalletTransferSerizlier(serializers.Serializer):
    beneficiary_email = serializers.EmailField()
    transfer_amount = serializers.IntegerField(
        min_value=10000, max_value=500000000)

    def validate_beneficiary_email(self, beneficiary_email):
        current_user = self.context.get('user')
        beneficiary_email = beneficiary_email.lower()
        if beneficiary_email == current_user.email:
            raise serializers.ValidationError(
                "Cannot make wallet transfers to yourself")
        wallet = Wallet.objects.filter(user__email=beneficiary_email).exclude(
            user__email=current_user.email).first()
        if not wallet:
            raise serializers.ValidationError(
                "Wallet account was not found for this user")
        return beneficiary_email

    def validate_transfer_amount(self, transfer_amount):
        wallet = self.context['wallet']
        if transfer_amount > wallet.balance:
            raise serializers.ValidationError(
                f"Your wallet does not have up to N{transfer_amount/100} in it")
        return transfer_amount

    def create(self, validated_data):
        try:
            with transaction.atomic():
                transaction_list = []
                beneficiary_email = validated_data['beneficiary_email']
                transfer_amount = validated_data['transfer_amount']
                my_wallet = self.context['wallet']
                beneficiary_wallet = Wallet.objects.filter(
                    user__email=beneficiary_email).first()
                transaction_reference = str(uuid.uuid4())

                my_wallet.balance = F('balance') - transfer_amount
                transaction_list.append(
                    WalletTransactions(
                        amount=transfer_amount,
                        reference=transaction_reference,
                        transaction_type=WALLET_TRANSACTION_TYPE[0][0],
                        transaction_trigger=WALLET_TRANSACTION_TRIGGER[4][0],
                        wallet_id=my_wallet.id)
                )

                beneficiary_wallet.balance = F('balance') + transfer_amount
                transaction_list.append(
                    WalletTransactions(
                        amount=transfer_amount,
                        reference=transaction_reference,
                        transaction_type=WALLET_TRANSACTION_TYPE[1][0],
                        transaction_trigger=WALLET_TRANSACTION_TRIGGER[4][0],
                        wallet_id=beneficiary_wallet.id)
                )
                my_wallet.save()
                my_wallet.refresh_from_db()
                beneficiary_wallet.save()
                WalletTransactions.objects.bulk_create(transaction_list)

            return dict(reference=transaction_reference,
                        amount_transfered=transfer_amount,
                        my_wallet_balance=my_wallet.balance)

        except Exception as e:
            capture_exception(e)
            raise serializers.ValidationError(
                "Error occured completing wallet-to-wallet transfer")


class WalletToBankTransferSerizlier(serializers.Serializer):
    bank_code = serializers.CharField(max_length=6, min_length=6)
    bank_account_no = serializers.CharField(max_length=10)
    transfer_amount = serializers.IntegerField(
        min_value=10000, max_value=500000000)

    def validate_transfer_amount(self, transfer_amount):
        wallet = self.context['wallet']
        if transfer_amount > wallet.balance:
            raise serializers.ValidationError(
                f"Your wallet does not have up to N{transfer_amount/100} in it")
        return transfer_amount

    def validate(self, validated_data):
        bank_details = BankingApi.get_transfer_beneficiary(
            account_number=validated_data['bank_account_no'],
            bank_code=validated_data['bank_code'])
        if not bank_details:
            raise serializers.ValidationError(
                {'bank_account_no': ['We could not fetch your provided bank information']})
        return {**validated_data, **bank_details}

    def create(self, validated_data):
        try:
            with transaction.atomic():
                # Take money from wallet
                account_bank_code = validated_data['account_bank_code']
                account_number = validated_data['account_number']
                transfer_amount = validated_data['transfer_amount']
                sender = self.context['user']
                my_wallet = self.context['wallet']
                # Hit core banking transfer api
                reference = 'xerde-' + \
                    str(uuid.uuid4())[:14] + f'{int(time.time())}'
                transfer_response = BankingApi.transfer_money(
                    amount=transfer_amount / 100,
                    account_number=account_number,
                    bank_code=account_bank_code,
                    transfer_type='inter',
                    transaction_reference=reference,
                    remark=f"Wallet Tranfer from {sender.first_name}"
                )

                if transfer_response.get('status') is not True:
                    raise serializers.ValidationError(
                        "Couldn't complete the transfer")

                my_wallet.balance = F('balance') - transfer_amount
                my_wallet.save()
                my_wallet.refresh_from_db()
                # Create transaction
                WalletTransactions(amount=transfer_amount,
                                   reference=reference,
                                   transaction_type=WALLET_TRANSACTION_TYPE[0][0],
                                   transaction_trigger=WALLET_TRANSACTION_TRIGGER[5][0],
                                   wallet_id=my_wallet.id).save()

                return dict(reference=reference,
                            amount_transfered=transfer_amount,
                            my_wallet_balance=my_wallet.balance)
        except Exception as e:
            capture_exception(e)
            raise serializers.ValidationError(
                "Couldn't complete the transfer")
            # return dict(reference="error occured")


class WalletTransactionsSerizlier(serializers.ModelSerializer):
    class Meta:
        model = WalletTransactions
        fields = '__all__'

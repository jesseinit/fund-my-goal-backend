from django.db import models

from userservice.models import User
from utils.helpers import BaseAbstractModel
from utils.constants import WALLET_TRANSACTION_TYPE, WALLET_TRANSACTION_TRIGGER


class Wallet(BaseAbstractModel):
    balance = models.BigIntegerField(default=0)
    user = models.OneToOneField(User, on_delete=models.CASCADE)


class WalletTransactions(BaseAbstractModel):
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE)
    amount = models.BigIntegerField(default=0)
    reference = models.CharField(max_length=50)
    transaction_type = models.CharField(
        max_length=50, choices=WALLET_TRANSACTION_TYPE)
    transaction_trigger = models.CharField(
        max_length=50, choices=WALLET_TRANSACTION_TRIGGER)

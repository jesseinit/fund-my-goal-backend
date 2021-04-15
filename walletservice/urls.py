from django.conf.urls import url
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from walletservice.views import (WalletBalanceViewset, WalletFundViewset,
                                 WalletToBankTransferViewset,
                                 WalletToWalletTransferViewset,
                                 WalletTransactionViewset)

router = DefaultRouter(trailing_slash=False)
router.register(r'/balance', WalletBalanceViewset, basename='wallet-balance')
router.register(r'/fund', WalletFundViewset, basename='wallet-fund')
router.register(r'/transfer/wallet', WalletToWalletTransferViewset,
                basename='wallet-wallet-transfer')
router.register(r'/transfer/bank', WalletToBankTransferViewset,
                basename='wallet-bank-transfer')
router.register(r'/transactions', WalletTransactionViewset,
                basename='wallet-transaction')

urlpatterns = [url(r'wallet', include(router.urls))]

import uuid

from django.conf import settings
from paystackapi.transaction import Transaction
from django.conf import settings
from rest_framework import mixins, viewsets
from rest_framework.status import (HTTP_200_OK, HTTP_201_CREATED,
                                   HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED,
                                   HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND,
                                   HTTP_500_INTERNAL_SERVER_ERROR,
                                   HTTP_503_SERVICE_UNAVAILABLE)

from userservice.models import DebitCard
from userservice.utils.helpers import format_response
from utils.helpers import (CustomPaginator, parse_query_params,
                           retrieve_from_redis, save_in_redis)
from walletservice.models import Wallet, WalletTransactions
from walletservice.serializer import (FundWalletSerizlier,
                                      WalletToBankTransferSerizlier,
                                      WalletToWalletTransferSerizlier,
                                      WalletTransactionsSerizlier)


class WalletBalanceViewset(mixins.ListModelMixin, viewsets.GenericViewSet):

    def list(self, request):
        wallet = Wallet.objects.get(user=request.user)
        return format_response(
            data={"id": wallet.id, "balance": wallet.balance},
            status=HTTP_200_OK)


class WalletFundViewset(mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = FundWalletSerizlier

    def create(self, request):
        user = request.user
        serializer = self.serializer_class(
            data=request.data, context={'user': user})
        if not serializer.is_valid():
            return format_response(error=serializer.errors,
                                   status=HTTP_400_BAD_REQUEST)
        serializer = serializer.save()
        return format_response(data=serializer,
                               status=HTTP_200_OK)


class WalletToWalletTransferViewset(mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = WalletToWalletTransferSerizlier

    def create(self, request):
        user = request.user
        wallet = Wallet.objects.get(user=user)
        serializer = self.serializer_class(
            data=request.data, context={'user': user, 'wallet': wallet})

        if not serializer.is_valid():
            return format_response(error=serializer.errors,
                                   status=HTTP_400_BAD_REQUEST)

        created_transfer = serializer.save()

        return format_response(data=created_transfer,
                               status=HTTP_200_OK)


class WalletToBankTransferViewset(mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = WalletToBankTransferSerizlier

    def create(self, request):
        user = request.user
        if user.bvn is None:
            return format_response(
                error="Kindly add your BVN number to your profile",
                status=HTTP_400_BAD_REQUEST)

        wallet = Wallet.objects.get(user=user)
        serializer = self.serializer_class(
            data=request.data, context={'user': user, 'wallet': wallet})

        if not serializer.is_valid():
            return format_response(error=serializer.errors, status=HTTP_400_BAD_REQUEST)

        created_transfer = serializer.save()
        return format_response(data=created_transfer, status=HTTP_200_OK)


class WalletTransactionViewset(viewsets.ViewSet):
    serializer_class = WalletTransactionsSerizlier

    def list(self, request):
        user = request.user
        wallet = Wallet.objects.get(user=user)
        wallet_transactions = WalletTransactions.objects.filter(wallet=wallet)
        paginator = CustomPaginator(url_suffix="api/v1/wallet/transactions")
        paginated_transactions = paginator.paginate_queryset(
            wallet_transactions, request)
        wallet_transactions = self.serializer_class(paginated_transactions, many=True)
        return paginator.get_paginated_response(data=wallet_transactions.data,
                                                query_params=parse_query_params(
                                                    request),
                                                status=HTTP_200_OK)


class WalletWithdrawViewset(viewsets.ViewSet):
    pass

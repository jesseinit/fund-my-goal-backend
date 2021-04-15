import base64
import hashlib
import os
import uuid

import boto3
import requests
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.utils import timezone
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.utils.urls import replace_query_param
from rest_framework.status import (HTTP_200_OK)
from sentry_sdk import capture_exception

from utils.constants import (FUNDS_TRANFER_FAILURE, FUNDS_TRANFER_SUCCESS,
                             GROUP_MEMBER_ROLES, INSUFFICIENT_BALANCE,
                             INVITE_STATUS, NOTIFICATION_ENTITY,
                             NOTIFICATION_INVITE_TEXT, NOTIFICATION_TYPE,
                             USER_TYPES)
from utils.enums import StateType


def generate_id():
    return uuid.uuid4().hex


def parse_query_params(request):
    if not request.query_params:
        return None
    query_str = ''
    query_str_list = list(request.query_params.items())
    for index, value in enumerate(request.query_params.items()):
        if (index + 1) == len(query_str_list):
            query_str += f"{value[0]}={value[1]}"
            break
        query_str += f"{value[0]}={value[1]}&"
    return query_str


def retrieve_from_redis(key):
    """
        This function retrieve from redis
        1. This function take one arguments {key}
        2. Retrieve the data of the key passed in
    """
    return cache.get(key)


def delete_from_redis(key):
    """ This function deteles a key and its data from redis"""
    return cache.delete(key)


def save_in_redis(key, data, timeout=None):
    """
        This function save in redis
        1. This function take three arguments key,
            data to be saved and timeout value
        2. Save the data with {key} arg as the key in redis
    """
    cache.set(key, data, timeout=timeout)


def parse_user_type(instance):
    from userservice.models import User
    return USER_TYPES[0].lower() if isinstance(instance, User) \
         else USER_TYPES[1].lower()


def format_response(**kwargs):
    ''' Helper function to format response '''
    if kwargs.get('error'):
        return Response({'error': kwargs.get('error'), **kwargs},
                        status=kwargs.get('status', 400))

    return Response({**kwargs}, status=kwargs.get('status', 200))


class BaseAbstractModel(models.Model):
    """ Base Abstract Model """
    id = models.CharField(max_length=60,
                          primary_key=True,
                          default=generate_id,
                          editable=False)
    state = models.CharField(max_length=50,
                             choices=[(state.name, state.value) for state in StateType],
                             default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(default=None)

    class Meta:
        abstract = True
        ordering = ['-created_at']

    def update(self, **kwargs):
        if self._state.adding:
            raise self.DoesNotExist
        for field, value in kwargs.items():
            setattr(self, field, value)
        self.save(update_fields=kwargs.keys())
        return self


class BankingApi():
    """
        Abstracted Banking API Class
        ----------------------------
        Helper class that consolidates all helper methods for interfacing
        with the Core Banking API
    """

    wallet_credentials = settings.VFD_WALLET
    access_token = settings.VFD_ACCESS_TOKEN
    headers = {'Authorization': 'Bearer {}'.format(access_token)}
    params = {'wallet-credentials': wallet_credentials}

    @classmethod
    def transfer_money(cls, **kwargs):
        '''
            This function helps to transfer money from Xerde's pool account
            to a tudo user's account:

            Parameters
            ----------
            - amount [int]: amount to withdraw in naira.
            - account_number [int]: account number of recipient
            - bank_code [str] - bank code for bank
            - transaction_reference [str]- bank code for bank
            - transfer_type [str]- bank code for bank
            - remark [str]- Transaction remark/description

            Returns
            -------
            [dict] - Funds transfer response dictionary
        '''
        try:
            amount_to_tranfer = kwargs.get('amount')
            beneficiary_account_number = kwargs.get('account_number')
            beneficiary_bank_code = kwargs.get('bank_code')
            transaction_reference = kwargs.get('transaction_reference')
            transfer_type = kwargs.get('transfer_type')
            remark = kwargs.get('remark')

            params = {'wallet-credentials': cls.wallet_credentials}
            headers = {'Authorization': 'Bearer {}'.format(cls.access_token)}

            pool_account = cls.pool_account_enquiry()
            if pool_account and pool_account.get('account_balance') < amount_to_tranfer:
                raise Exception(INSUFFICIENT_BALANCE)

            beneficiary_data = cls.get_transfer_beneficiary(
                account_number=beneficiary_account_number,
                bank_code=beneficiary_bank_code)

            if not beneficiary_data.get('is_resolved'):
                raise Exception("Beneficiary account couldn't be resolved")

            signature = hashlib.sha512(
                (pool_account.get('account_number') +
                 beneficiary_data.get('account_number')).encode('utf-8')).hexdigest()
            body = {
                'reference': transaction_reference,
                'remark': remark,
                'amount': str(round(amount_to_tranfer, 2)),
                'transferType': transfer_type,
                'signature': signature,
                'fromAccount': pool_account.get('account_number'),
                'fromSavingsId': pool_account.get('account_id'),
                'fromClientId': pool_account.get('client_id'),
                'fromClient': pool_account.get('account_name'),
                'fromBvn': settings.VFD_XERDE_POOL_ACCOUNT_BVN,
                'toAccount': beneficiary_data.get('account_number'),
                'toClient': beneficiary_data.get('account_name'),
                'toBank': beneficiary_data.get('account_bank_code'),
                'toSession': beneficiary_data.get('to_session'),
                'toKyc': beneficiary_data.get('to_kyc'),
                'toBvn': ''
            }

            if beneficiary_data.get('is_intra_transfer'):
                body['toSavingsId'] = beneficiary_data.get('toSavingsId')
                body['toClientId'] = beneficiary_data.get('toClientID')
                body['toBvn'] = beneficiary_data.get('toBvn')
                body['transferType'] = 'intra'
                del body['toSession']
                del body['toKyc']

            tranfer_response = requests.post(url=settings.VFD_URL + '/transfer',
                                             json=body,
                                             params=params,
                                             headers=headers,
                                             timeout=20).json()
            if tranfer_response.get('Status') != '00':
                raise Exception(tranfer_response)
            return dict(status=True, message=FUNDS_TRANFER_SUCCESS)
        except Exception as e:
            capture_exception(e)
            return dict(status=False, message=FUNDS_TRANFER_FAILURE)

    @classmethod
    def get_transfer_beneficiary(cls, transfer_type='inter', **kwargs):
        """ Retrieves details of a transfer beneficiary """
        try:
            headers = {'Authorization': 'Bearer {}'.format(cls.access_token)}
            params = {
                'transfer_type': transfer_type,
                'accountNo': kwargs.get('account_number') if settings.ENV == 'production' else settings.VFD_DEV_TO_ACCOUNT,
                'bank': kwargs.get('bank_code') if settings.ENV == 'production' else settings.VFD_DEV_BANK_CODE,
                'wallet-credentials': cls.wallet_credentials
            }

            params['transfer_type'] = 'intra' if params['bank'] == '999999' else transfer_type
            is_intra_transfer = True if params['transfer_type'] == 'intra' else False

            recipient_response = requests.get(url=settings.VFD_URL + '/transfer/recipient',
                                              params=params,
                                              headers=headers,
                                              timeout=20)

            recipient_response = recipient_response.json()
            if recipient_response.get('Status') != "00":
                return dict()

            recipient_payload = {
                'is_intra_transfer': is_intra_transfer,
                'is_resolved': True,
                'account_name': recipient_response['Data']['name'],
                'account_number': recipient_response['Data']['account']['number'],
                'account_bank_code': params['bank'],
                'to_session': recipient_response['Data']['account']['id'],
                'to_kyc': recipient_response['Data']['status']
            }

            if is_intra_transfer:
                del recipient_payload['to_session']
                del recipient_payload['to_kyc']
                recipient_payload['toClientID'] = recipient_response['Data']['clientId']
                recipient_payload['toSavingsId'] = \
                     recipient_response['Data']['account'][
                    'id']
                recipient_payload['toBvn'] = recipient_response['Data']['bvn']

            return recipient_payload
        except Exception as e:
            capture_exception(e)
            return dict()

    @classmethod
    def pool_account_enquiry(cls):
        """ Returns detail of the wallets pool account """
        try:
            pool_account_response = requests.get(url=settings.VFD_URL +
                                                 '/account/enquiry',
                                                 params=cls.params,
                                                 headers=cls.headers,
                                                 timeout=20).json()

            pool_account_number = pool_account_response['Data']['accountNo']
            pool_account_id = pool_account_response['Data']['accountId']
            pool_client_id = pool_account_response['Data']['clientId']
            pool_account_name = pool_account_response['Data']['client']
            pool_account_balance = \
                 float(pool_account_response['Data']['accountBalance'])
            return dict(account_number=pool_account_number,
                        account_id=pool_account_id,
                        client_id=pool_client_id,
                        account_name=pool_account_name,
                        account_balance=pool_account_balance)
        except (requests.exceptions.RequestException, KeyError) as e:
            capture_exception(e)
            return dict(account_balance=0)

    @classmethod
    def retrieve_bank_list(cls):
        try:
            cached_bank_list = retrieve_from_redis('bank-list')
            if not cached_bank_list:
                bank_list = requests.get(url=settings.VFD_URL + '/bank',
                                         headers=cls.headers,
                                         timeout=20).json()
                if not bank_list.get('Status') == '00':
                    return None
                parsed_bank_list = [
                    dict(code=bank_data['code'], name=bank_data['name'])
                    for bank_data in bank_list['Data']['bank']
                ]
                save_in_redis('bank-list', parsed_bank_list, 30 * 86400)
                return parsed_bank_list
            return cached_bank_list
        except Exception as e:
            capture_exception(e)
            return None

    @classmethod
    def bvn_enquiry(cls, bvn):
        # if settings.ENV != 'production':
        #     return dict(Status='00')
        try:
            params = {'wallet-credentials': cls.wallet_credentials, 'bvn': bvn}
            headers = {'Authorization': 'Bearer {}'.format(cls.access_token)}
            bvn_response = requests.get(url=settings.VFD_URL + '/client',
                                        params=params,
                                        headers=headers,
                                        timeout=20).json()
            bvn_status = bvn_response.get('Status')
            if bvn_status != '00':
                return None
            else:
                return dict(data=bvn_response['Data'])
        except Exception as e:
            capture_exception(e)
            return None


class FlutterWaveAPI:
    SECRET_KEY = settings.FLUTTERWAVE_SECRET_KEY
    PUBLIC_KEY = settings.FLUTTERWAVE_PUBLIC_KEY
    BASE_URL = "https://api.ravepay.co/flwv3-pug/getpaidx/api/v2"

    @classmethod
    def initialize(cls, *args, **kwargs):
        try:
            response = requests.post(url=cls.BASE_URL + '/hosted/pay',
                                     json={
                                         **kwargs, "PBFPubKey": cls.PUBLIC_KEY
                                     }).json()
            return response
        except Exception as e:
            capture_exception(e)
            return None

    @classmethod
    def verify(cls, trans_ref=None):
        try:
            response = requests.post(url=cls.BASE_URL + '/verify',
                                     json={
                                         'txref': trans_ref,
                                         "SECKEY": cls.SECRET_KEY
                                     }).json()
            return response
        except Exception as e:
            capture_exception(e)
            return dict(status='failure', e=str(e))


class MediaHandler:
    """ Helper class that upload media assets to s3 or spaces """
    # Creds
    ACCESS_KEY_ID = settings.SPACE_ACCESS_KEY_ID
    SECRET_ACCESS_KEY = settings.SPACE_SECRET_ACCESS_KEY
    BUCKET_NAME = settings.SPACE_STORAGE_BUCKET_NAME
    REGION = settings.SPACE_REGION
    IS_VALID_ENV = settings.ENV.lower() in ['production', 'staging']
    SPACE_ENDPOINT = settings.SPACE_ENDPOINT

    s3_client = boto3.resource('s3',
                               region_name=REGION,
                               endpoint_url=SPACE_ENDPOINT,
                               aws_access_key_id=ACCESS_KEY_ID,
                               aws_secret_access_key=SECRET_ACCESS_KEY)

    @classmethod
    def upload_link(cls, url, file_name):
        try:
            if cls.IS_VALID_ENV:
                url_response = requests.get(url, stream=True)
                if not url_response.status_code == 200:
                    capture_exception(Exception('Error getting file'))
                    return None

                cls.s3_client.Object(cls.BUCKET_NAME,
                                     file_name).put(Body=url_response.content,
                                                    ACL='public-read')
            return f'https://{cls.BUCKET_NAME}.{cls.REGION}.digitaloceanspaces.com/{file_name}'
        except Exception as e:
            capture_exception(e)
            return None

    @classmethod
    def upload_raw(cls, data, file_name):
        try:
            if cls.IS_VALID_ENV:
                cls.s3_client.Object(cls.BUCKET_NAME,
                                     file_name).put(Body=base64.b64decode(data),
                                                    ACL='public-read')

            return f'https://{cls.BUCKET_NAME}.{cls.REGION}.digitaloceanspaces.com/{file_name}'
        except Exception as e:
            capture_exception(e)
            return None


class CustomPaginator(PageNumberPagination):
    """ Custom page pagination class """
    page_size = 7
    page_size_query_param = 'page_size'

    def __init__(self, **kwargs):
        if kwargs.get('url_suffix'):
            self.url_suffix = kwargs['url_suffix']
        else:
            self.url_suffix = ''

    def paginate_queryset(self, queryset, request, view=None):
        from django.core.paginator import InvalidPage
        page_size = self.get_page_size(request)
        if not page_size:
            return None

        paginator = self.django_paginator_class(queryset, page_size)
        page_number = request.query_params.get(self.page_query_param, 1)
        if page_number in self.last_page_strings:
            page_number = paginator.num_pages

        try:
            self.page = paginator.page(page_number)
        except InvalidPage:
            from rest_framework.exceptions import NotFound
            raise NotFound(
                dict(error='The requested page does not exists', status=404))

        if paginator.num_pages > 1 and self.template is not None:
            self.display_page_controls = True

        self.request = request
        return list(self.page)

    def get_paginated_response(self, data, query_params=None, **kwargs):
        status = kwargs.get('status', HTTP_200_OK)
        return Response({**kwargs,
                         'total_pages': self.page.paginator.num_pages,
                         'next': self.get_next_link(query_params),
                         'previous': self.get_previous_link(query_params),
                         'data': data},
                        status=status)

    def get_next_link(self, query_params):
        if not self.page.has_next():
            return None
        page_number = self.page.next_page_number()
        if query_params:
            url = os.environ.get('BACKEND_URL', '0.0.0.0:1000') + \
                self.url_suffix + "?" + query_params
        else:
            url = os.environ.get(
                'BACKEND_URL', '0.0.0.0:1000') + self.url_suffix
        return replace_que nry_param(url, self.page_query_param, page_number)

    def get_previous_link(self, query_params):
        if not self.page.has_previous():
            return None
        page_number = self.page.previous_page_number()
        if query_params:
            url = os.environ.get('BACKEND_URL', '0.0.0.0:1000') + \
                self.url_suffix + "?" + query_params
        else:
            url = os.environ.get(
                'BACKEND_URL', '0.0.0.0:1000') + self.url_suffix
        return replace_query_param(url, self.page_query_param, page_number)

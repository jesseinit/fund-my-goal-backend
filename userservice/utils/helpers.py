import datetime
import os
import random
import uuid
from enum import Enum
from functools import reduce
from itertools import chain

import africastalking
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.mail import send_mail
from django.db.models import Q
from django.utils.http import int_to_base36
from paystackapi.transaction import Transaction
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK
from rest_framework.utils.urls import replace_query_param

from utils.enums import RewardPoints
from utils.helpers import parse_query_params, parse_user_type

ENV = settings.ENV


def format_response(**kwargs):
    ''' Helper function to format response '''
    if kwargs.get('error'):
        return Response({'error': kwargs.get('error'), **kwargs},
                        status=kwargs.get('status', 400))

    return Response({**kwargs}, status=kwargs.get('status', 200))


def generate_otp():
    """
        This function generate random 6 digits number as otp
    """
    OTP = ""
    for i in range(4):
        OTP += str(random.randint(1, 9))

    return OTP


def verify_otp(email, otp):
    """
        This function verify otp
        1. This function take two arguments email and otp
        2. Return True if otp in redis equal otp in argument else returns False
    """
    saved_otp = cache.get(email) if ENV == 'production' else '0000'
    if saved_otp and saved_otp == otp:
        cache.delete(email)
        return True
    else:
        return False


def save_in_redis(key, data, timeout):
    """
        This function save in redis
        1. This function take three arguments key,
            data to be saved and timeout value
        2. Save the data with {key} arg as the key in redis
    """
    cache.set(key, data, timeout=timeout)


def send_email(email, otp):
    """
        This function save otp
        1. This function take two arguments email and otp
        2. Sends email containing otp to the user email address
    """
    recipient_mail = settings.DEFAULT_FROM_EMAIL
    return send_mail('Tudo Account Verification',
                     'Your Tudo verification code is: ' + otp, recipient_mail, [email], fail_silently=False)


def send_sms(phone_no, otp):
    """
        This function save otp
        1. This function take two arguments phone number and otp
        2. Sends sms containing otp to the user phone number
    """
    africastalking.initialize(
        settings.SMS_GATEWAY_USERNAME, settings.SMS_GATEWAY_TOKEN)
    sms = africastalking.SMS
    response = sms.send("<#> Your Tudo verification code is: " + otp
                        + f'\n{settings.MOBILE_APP_ID}', [phone_no],
                        sender_id=settings.SMS_GATEWAY_SENDER_ID)
    return [dict(number=rep['number'], status=rep['status']) for rep in response['SMSMessageData']['Recipients']]


class StateType(Enum):
    active = "active"
    deleted = "deleted"


def decode_invite_code(invite_code):
    User = get_user_model()  # Todo - Add business model check here
    try:
        inviter = User.objects.get(invite_code=invite_code)
    except User.DoesNotExist:
        inviter = None
    return inviter


def generate_code(word):
    return create_invite_code(word)


class GoalStatus(Enum):
    """ Different status of Goal """
    running = 'running'
    completed = 'completed'
    paid = 'paid'
    processing_withdrawal = 'processing_withdrawal'


class GoalDuration(Enum):
    """ Different duration of Goal """
    One_month = '30 Days'
    Two_month = '60 Days'
    Three_month = '90 Days'


class TransactionStatus(Enum):
    PENDING = 'Pending'
    SUCCESS = 'Success'
    FAILED = 'Failed'


class GoalContributionType(Enum):
    TOPUP = 'TopUp'
    USERCONTRIBUTION = 'UserContribution'


class NotificationStatus(Enum):
    read = "read"
    unread = "unread"


class UserRole(Enum):
    default_user = 'default_user'
    admin = 'admin'


class TransactionType():
    """Determines the transaction being processed by webhook"""
    Goal_CONTRIBUTION = "Goal_CONTRIBUTION"
    Goal_TOPUP = "TTUDO_TOPUP"
    ADDED_CARD = "ADDED_CARD"
    FUND_WALLET = "FUND_WALLET"


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
        return replace_query_param(url, self.page_query_param, page_number)

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


def get_tudos(request, query_set, tudo_state_type):
    """
    This method is helps to map a tudo's state to a queryset and 
    then returns a HTTP response with data matching the specified tudo state.

    Args:
        request: A http request object
        query_set: A database query set object instance
        tudo_state_type: A string representing the tudo state

    """
    from userservice.serializer import TudoModelSerializer
    user_type = parse_user_type(request.user)
    field_opts = dict(personal=dict(user=request.user),
                      business=dict(business=request.user))[user_type]

    paginator = CustomPaginator(url_suffix='api/v1/tudo')
    if 'QuerySet' in query_set.__class__.__name__:
        tudos = paginator.paginate_queryset(
            query_set.filter(**field_opts), request)
    else:
        tudos = paginator.paginate_queryset(
            query_set().filter(**field_opts), request)
    serializer = TudoModelSerializer(tudos, many=True)
    return paginator.get_paginated_response(data=serializer.data,
                                            query_params=parse_query_params(
                                                request),
                                            message=f'{tudo_state_type.capitalize()} tudos retrieved successfully',
                                            status=200)


def search_tudos(request, query, tudos_type):
    from userservice.serializer import TudoModelSerializer
    from userservice.models import Tudo, Business
    keywords = query.split()
    user_type = 'business' if isinstance(
        request.user, Business) else 'personal'
    filters_opts = dict(
        business=request.user) if user_type == 'business' else dict(user=request.user)

    if len(keywords) > 1:
        full_query_tudos = Tudo.objects.filter(
            goal_name__icontains=query.strip())
    else:
        full_query_tudos = []

    tokenized_query_tudos = list(chain(
        Tudo.objects.filter(
            goal_name__istartswith=keywords[0], **filters_opts),
        Tudo.objects.filter(reduce(lambda x, y: x | y,
                                   [Q(goal_name__icontains=word)
                                    for word in keywords]),
                            **filters_opts)
    ))

    filtered_tudos_with_duplicates = list(
        chain(full_query_tudos, tokenized_query_tudos))
    filtered_tudos_without_duplicates = []
    for tudo in filtered_tudos_with_duplicates:
        if tudo not in filtered_tudos_without_duplicates:
            filtered_tudos_without_duplicates.append(tudo)

    paginator = CustomPaginator(url_suffix='api/v1/tudo')
    paginated_tudos = paginator.paginate_queryset(
        filtered_tudos_without_duplicates, request)
    serializer = TudoModelSerializer(paginated_tudos, many=True)
    if serializer.data:
        return paginator.get_paginated_response(data=serializer.data,
                                                query_params=parse_query_params(
                                                    request),
                                                message='Tudos retrieved successfully',
                                                status=HTTP_200_OK)
    else:
        return paginator.get_paginated_response(data=serializer.data,
                                                query_params=None,
                                                message='Your search returned to matching results',
                                                status=HTTP_200_OK)


class EmailSubjects(Enum):
    contribution_receiver = 'Yaay! You just got N{}! 🎉🎈🍾'
    contribution_sender = 'Thank you! 😁'
    tudo_goal_reached = 'Goal Smashed! 🎯💪🏽🍾'
    tudo_expired = 'Yikes! You didn’t reach this goal. ☹️'
    withdrawal = 'Your withdrawal was successful! 🎉'
    savings_topup = 'Tudo Top Up Successful!'
    new_tudo_list = 'New Tudo List Created!'
    signup = 'Welcome to Tudo! 🎉🎉'
    new_savings = 'New Savings Plan Created!'
    if RewardPoints.signup.value == 1:
        successful_invite = f'{RewardPoints.signup.value} point earned, Good job!🎉'
    else:
        successful_invite = f'{RewardPoints.signup.value} points earned, Good job!🎉'
    inactivity = 'It’s been {} weeks! We miss you ☹️'
    password_reset = 'Password Reset'
    verfication_code = 'Your Verificaiton OTP Has Arrived 😋'
    scheduled_saving_success = 'Hurray! Your Savings Plan Has Commenced 🎉'
    scheduled_saving_failure = 'Your Savings Plan Can\'t Commence ☹️'
    grouped_tudo_invite = 'Group goal invitation 🎈'
    grouped_tudo_invite_acceptance = 'Group Tudo invite accepted 🎉'


default_tudo_description = ("Hey! I'm trying to reach this goal as soon as possible, "
                            "and I'd be glad to have your support on this journey. "
                            "Your contribution would go a long way. Thank you!")


def charge_customer(serializer_data, transaction_type):
    """
    This method makes a call to paystack's api to charge a user when creating a savings plan with a card
    Args:
        serializer_data: Holds serialized plan data
        transaction_type: Refers to the type of transaction on billing should occur
    """
    return Transaction.charge(
        reference=serializer_data.get('transaction_ref'),
        authorization_code=serializer_data.get(
            'card').get('authorization_code'),
        email=serializer_data['user']['email'],
        amount=serializer_data.get('start_amount'),
        metadata={'savings_data': serializer_data,
                  'transaction_type': transaction_type})


def retrieve_from_redis(key):
    """
        This function retrieve from redis
        1. This function take one arguments {key}
        2. Retrieve the data of the key passed in
    """
    return cache.get(key)


class PlanType(Enum):
    """ Refers to the various plans type a savings plan can be created with """
    target = 'Targeted'
    periodic = 'Periodic'
    locked = 'Locked'


class UserActionStatus(Enum):
    success = 'SUCCESSFUL'
    failure = 'FAILED'


class SavingStatus(Enum):
    paused = 'PAUSED'
    completed = 'COMPLETED'
    running = 'RUNNING'
    pending = 'PENDING'
    paid = 'PAID'
    processing_withdrawal = 'PROCESSING_WITHDRAWAL'


class BackgroundActionType(Enum):
    compute_locked_savings_interest = 'compute locked savings interest'
    compute_targeted_savings_interest = 'compute targeted savings interest'


class TudoServiceChargesRates(Enum):
    complete = 0.015
    incomplete = 0.015


class MediaType(Enum):
    document = 'document'
    image = 'image'
    video = 'video'

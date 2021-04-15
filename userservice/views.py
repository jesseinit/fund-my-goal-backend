import hashlib
import hmac
import time
import uuid
from datetime import datetime
from decimal import Decimal as D
from functools import reduce
from itertools import chain
from textwrap import shorten

import jwt
from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import AnonymousUser
from django.db.models import F, Q
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django_filters import rest_framework as filters
from fcm_django.models import FCMDevice
from paystackapi.transaction import Transaction
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.status import (HTTP_200_OK, HTTP_201_CREATED,
                                   HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED,
                                   HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND,
                                   HTTP_500_INTERNAL_SERVER_ERROR,
                                   HTTP_503_SERVICE_UNAVAILABLE)
from rest_framework.views import APIView
from savingservice.models import Savings as SavingsModel
from savingservice.models import SavingsTransaction
from sentry_sdk import capture_exception
from walletservice.models import Wallet, WalletTransactions

from userservice.authentication import AllowAnyUser
from utils.constants import (BUSINESS_SUPPORTED_COUNTRY, CUSTOM_GOAL_TEXT,
                             FOLLOWING_STATUS, GROUPTUDO_TRANSACTION_TYPE,
                             INVITE_STATUS, LIKE_STATUS, NGN_PER_POINT,
                             REWARDTYPES, SERVICE_RATE,
                             WALLET_TRANSACTION_TRIGGER,
                             WALLET_TRANSACTION_TYPE)
from utils.enums import RewardPoints
from utils.helpers import (BankingApi, FlutterWaveAPI, delete_from_redis,
                           parse_query_params, parse_user_type, save_in_redis)

from .filters import TudoSearchFilter, UserSearchFilter
from .models import (BankAccount, Business, DebitCard, GroupTudo,
                     GroupTudoContribution, GroupTudoMembers, NextOfKin,
                     Notification, Rewards, Tudo, TudoComments,
                     TudoContribution, TudoFollowers, TudoLikes, TudoMedia,
                     TudoWithdrawal, User, UserKYC)
from .permissions import AllowListRetrieveOnly
from .serializer import (AccountVerificationSerializer,
                         ApplicationSupportSerializer, BankDetailsSerializer,
                         BusinessUserProfileSerializer, DebitCardSerializer,
                         LoginSerializer, NextOfKinSerializer,
                         NotificationSerializer, OTPGenerateSerializer,
                         PasswordResetLinkSerializer, PasswordResetSerializer,
                         PersonalUserProfileSerializer, ReferralSerializer,
                         RegisterBusinessSerializer, RegisterSerializer,
                         TrendingTudoSerializer, TudoCommentListSerializer,
                         TudoCommentSerializer, TudoContactFeedSerializer,
                         TudoContributionSerializer, TudoFeedSerializer,
                         TudoLikesSerializer, TudoMediaModelSerializer,
                         TudoMediaSerializer, TudoModelSerializer,
                         TudoSerializer, TudoTopUpSerializer,
                         TudoTransactionSerializer, TudoTransactionsSerializer,
                         TudoWithdrawTransactionSerializer, UserKYCSerializer,
                         WithdrawTudoSerializer)
from .tasks import (send_application_support_email, send_email_async,
                    send_new_tudo_list_email, send_password_reset_email,
                    send_sms_async, send_successful_signup_email,
                    send_successful_user_invite_email,
                    send_tudo_withdrawal_email, send_unsupported_country_email,
                    send_verification_email)
from .utils.helpers import (CustomPaginator, NotificationStatus, StateType,
                            TransactionStatus, TransactionType,
                            TudoContributionType, TudoServiceChargesRates,
                            TudoStatus, format_response, generate_otp,
                            get_tudos, retrieve_from_redis, search_tudos,
                            verify_otp)
from .utils.password_reset import activation_token, decode_token
from .utils.transaction_handler import TransactionHandler

FRONTEND_URL = settings.FRONTEND_URL


class RegisterUserViewSet(viewsets.ViewSet):
    """ View to register a user """

    serializer_class = RegisterSerializer
    permission_classes = ()
    authentication_classes = ()

    def create(self, request):
        data = request.data
        serializer = self.serializer_class(data=data)

        if not serializer.is_valid():
            return format_response(
                error=serializer.errors.get("errors", serializer.errors),
                status=HTTP_400_BAD_REQUEST,
            )

        if request.query_params:
            invite_code = request.query_params.get("ref")
            inviter = (User.objects.filter(invite_code=invite_code).first()
                       or Business.objects.filter(invite_code=invite_code).first()
                       if invite_code else None)

            if inviter:
                new_user = serializer.save()
                new_user.update(invited_by=inviter.id)
            else:
                return format_response(
                    error={"invite_code": ["You've entered an invalid code"]},
                    status=HTTP_404_NOT_FOUND,
                )
        else:
            new_user = serializer.save()

        is_prod_env = settings.ENV.lower() == "production"
        otp = generate_otp() if is_prod_env else "0000"
        email = new_user.email
        phone_no = new_user.mobile_number

        save_in_redis(email, otp, 60 * 5)
        send_verification_email.delay(
            user_email=new_user.email,
            otp=otp,
            full_name=new_user.first_name.title())
        if phone_no and is_prod_env:
            send_sms_async.delay(phone_no, otp)

        return format_response(
            data=serializer.data,
            message="You have successfully registered with Tudo",
            status=HTTP_201_CREATED,
        )


class RegisterBusinessViewSet(viewsets.ViewSet):
    """ View to register a user """

    serializer_class = RegisterBusinessSerializer
    permission_classes = ()
    authentication_classes = ()

    def create(self, request):
        data = request.data
        serializer = self.serializer_class(data=data)

        if not serializer.is_valid():
            return format_response(
                error=serializer.errors.get("errors", serializer.errors),
                status=HTTP_400_BAD_REQUEST,
            )

        if request.query_params:
            invite_code = request.query_params.get("ref")
            inviting_business = (Business.objects.filter(
                invite_code=invite_code).first() or User.objects.filter(
                    invite_code=invite_code).first() if invite_code else None)

            if inviting_business:
                new_user = serializer.save()
                new_user.invited_by = inviting_business.id
                new_user.save()
                actor_name = f"{new_user.first_name} {new_user.last_name}"
                log = f"Successfully registered with Tudo through {invite_code}"
            else:
                return format_response(
                    error={"invite_code": ["You've entered an invalid code"]},
                    status=HTTP_404_NOT_FOUND,
                )
        else:
            new_user = serializer.save()
            actor_name = f"{new_user.first_name} {new_user.last_name}"
            log = "Successfully registered with Tudo"

        is_prod_env = settings.ENV.lower() == "production"
        otp = generate_otp() if is_prod_env else "0000"
        email = new_user.email
        phone_no = new_user.mobile_number
        save_in_redis(email, otp, 60 * 5)
        country = new_user.country

        if country in [country[0] for country in BUSINESS_SUPPORTED_COUNTRY]:
            # send_email_async.delay(email, otp)
            send_verification_email.delay(
                user_email=new_user.email,
                otp=otp,
                full_name=new_user.business_name.title())
            if phone_no and is_prod_env:
                send_sms_async.delay(phone_no, otp)
        else:
            send_unsupported_country_email.delay(actor_name, email)

        return format_response(
            data=serializer.data,
            message="You have successfully registered your business with Tudo",
            actor_name=actor_name,
            log=log,
            status=HTTP_201_CREATED,
        )


class LoginUserViewSet(viewsets.ViewSet):
    """ View to handle login in the user """

    serializer_class = LoginSerializer
    permission_classes = ()
    authentication_classes = ()

    def create(self, request):
        serializer = self.serializer_class(data=request.data)

        if not serializer.is_valid():
            return format_response(error=serializer.errors, status=HTTP_400_BAD_REQUEST)

        acct_type = serializer.data["acct_type"]
        email = serializer.data["email"].lower()
        password = serializer.data["password"]
        auth_type = serializer.data["auth_type"]

        user_account = dict(
            personal=User.objects.filter(email=email).first(),
            business=Business.objects.filter(email=email).first(),
        )
        user = user_account[acct_type]

        if not user:
            return format_response(
                error="No account associated with this email address",
                status=HTTP_404_NOT_FOUND,
            )

        pwd_valid = check_password(password, user.password)
        if auth_type == 'social':
            pwd_valid = check_password(password, user.social_password)

        if not pwd_valid:
            return format_response(error="Invalid email or password",
                                   status=HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return format_response(error="Your account has not been activated",
                                   status=HTTP_400_BAD_REQUEST)

        user.last_login = timezone.now()
        user.save()
        token = jwt.encode(
            {
                "uid": user.id,
                "type": "personal" if isinstance(user, User) else "business",
                "iat": settings.JWT_SETTINGS["ISS_AT"](),
                "exp": settings.JWT_SETTINGS["EXP_AT"](),
            },
            settings.SECRET_KEY,
        )

        from fcm_django.models import FCMDevice
        device_id = serializer.data['device_id']
        device_registration_id = serializer.data['device_registration_id']
        device_name = serializer.data['device_name']
        device_os_type = serializer.data['device_os_type']
        if all([device_id, device_registration_id, device_name, device_os_type]):
            FCMDevice.objects.update_or_create(
                user=user, device_id=device_id,
                defaults=dict(registration_id=device_registration_id,
                              name=device_name, type=device_os_type))

        return format_response(
            token=token,
            message="Your login was successful",
            status=HTTP_200_OK,
        )


class VerificationViewSet(mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = AccountVerificationSerializer
    otp_serializer_class = OTPGenerateSerializer
    permission_classes = ()
    authentication_classes = ()

    @action(detail=False, methods=["patch"])
    def verify_account(self, request):
        serializer = self.serializer_class(data=request.data)

        if not serializer.is_valid():
            return format_response(error=serializer.errors, status=HTTP_400_BAD_REQUEST)

        email = serializer.data.get("email").lower()
        otp = serializer.data.get("otp")
        acct_type = serializer.data.get("acct_type")

        user_account = dict(
            personal=User.objects.filter(email=email).first(),
            business=Business.objects.filter(email=email).first(),
        )
        user = user_account[acct_type]

        if not user:
            return format_response(
                error="No account associated with this email address",
                status=HTTP_404_NOT_FOUND,
            )

        if verify_otp(email, otp):
            user.update(is_active=True)
            if acct_type == "personal":
                send_successful_signup_email.delay(user_first_name=user.first_name,
                                                   user_email=user.email)
            else:
                send_successful_signup_email.delay(user_first_name=user.business_name,
                                                   user_email=user.email)

            if acct_type == "personal":
                # This handles invitation for a user that was invited to a group goal
                # At this time, the case is that he doesn't have an account yet
                # So when he creates an account and login he'd automatically get an invite
                pending_group_invite_data = retrieve_from_redis(
                    f"pending-group-invite-{user.email}")
                if pending_group_invite_data:
                    group_instance = GroupTudo.objects.filter(
                        id=pending_group_invite_data['goal_id'],
                        status='RUNNING').first()
                    group_instance.member_count = F('member_count') + 1
                    group_instance.save()
                    created_membership_instance = GroupTudoMembers.objects.create(
                        member=user,
                        invite_status=INVITE_STATUS[0][0],
                        role='REGULAR',
                        group_tudo=group_instance)
                    if created_membership_instance:
                        Notification.objects.create(
                            **pending_group_invite_data['notification_data'], user=user)
                        delete_from_redis(f"pending-group-invite-{user.email}")

                # ++++++++++++++++++++++++++++ #
                # This code below was comment because management no longer
                # awards points to inviters.
                # Its possible that they may want to in the future hence me leaving it.
                # ++++++++++++++++++++++++++++ #
                # if user.invited_by:
                #     inviter = User.objects.get(id=user.invited_by)
                #     inviter.points = F("points") + RewardPoints.signup.value
                #     inviter.save()
                #     rewards_data = {
                #         "inviter": inviter,
                #         "invitee": user,
                #         "type": REWARDTYPES[0][0],
                #         "points": RewardPoints.signup.value,
                #     }
                #     Rewards(**rewards_data).save()
                #     send_successful_user_invite_email.delay(
                #         invitee_first_name=user.first_name,
                #         user_first_name=inviter.first_name,
                #         user_email=inviter.email,
                #     )
                #     Notification.objects.create(
                #         user_id=user.invited_by,
                #         triggered_by_id=user.id,
                #         summary="Invite code notification",
                #         notification_text=f"Hello {inviter.first_name}, \
                #             {user.first_name} just used your invite code to register, \
                #            you have earned {RewardPoints.signup.value} point, Good job!🎉",
                #         actor_name=user.first_name,
                #     )

            return format_response(
                message="Your account has been verified",
                status=HTTP_200_OK,
            )
        else:
            return format_response(error="Invalid OTP Entered",
                                   status=HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    def generate_otp(self, request):

        serializer = self.otp_serializer_class(data=request.data)

        if not serializer.is_valid():
            return format_response(error=serializer.errors, status=HTTP_400_BAD_REQUEST)

        email = serializer.data.get("email").lower()
        acct_type = serializer.data.get("acct_type")

        user_account = dict(
            personal=User.objects.filter(email=email).first(),
            business=Business.objects.filter(email=email).first(),
        )
        user = user_account[acct_type]

        if not user:
            return format_response(
                error="No account associated with this email address",
                status=HTTP_404_NOT_FOUND,
            )

        if user.is_active:
            return format_response(error="Your account is already verified",
                                   status=HTTP_400_BAD_REQUEST)

        is_prod_env = settings.ENV.lower() == "production"
        otp = generate_otp() if is_prod_env else "0000"
        save_in_redis(email, otp, 60 * 5)
        if acct_type == "personal":
            send_verification_email.delay(
                user_email=user.email,
                otp=otp, full_name=user.first_name.title())
        else:
            send_verification_email.delay(
                user_email=user.email,
                otp=otp, full_name=user.business_name.title())
        # send_email_async.delay(email, otp)
        if user.mobile_number and is_prod_env:
            send_sms_async.delay(user.mobile_number, otp)

        actor_name = f"{user.first_name} {user.last_name}"
        return format_response(
            message="OTP has been sent to your Email and Phone",
            log=f"Requested for verification OTP",
            actor_name=actor_name,
            status=HTTP_200_OK,
        )


class GetPasswordResetLinkView(APIView):

    success = "Please check your email for a password reset link."
    serializer_class = PasswordResetLinkSerializer
    permission_classes = ()
    authentication_classes = ()

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return format_response(error=serializer.errors)
        email = serializer.data["email"]
        user = (User.objects.filter(email=email).first()
                or Business.objects.filter(email=email).first())
        token = activation_token.account_activation_token.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.id))

        reset_link = "{}/password-reset-change/{}/{}".format(FRONTEND_URL, uid, token)
        send_password_reset_email.delay(user.email,
                                        user.first_name,
                                        details={"reset_link": reset_link})

        log = "Successfully requested password reset link"
        actor_name = f"{user.first_name} {user.last_name}"
        return format_response(
            message="Please check your email for a password reset link.",
            log=log,
            actor_name=actor_name,
            status=HTTP_200_OK,
        )


class PasswordResetView(APIView):
    permission_classes = ()
    authentication_classes = ()
    serializer_class = PasswordResetSerializer

    def put(self, request, uidb64, token):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return format_response(error=serializer.errors)

        check_token, user = decode_token.decode_token(uidb64, token)
        if check_token and user:
            new_password = serializer.data.get("new_password")
            user.set_password(new_password)
            user.save()
            log = f"successfully reset password"
            actor_name = f"{user.first_name} {user.last_name}"
            response = {
                "log": log,
                "message": "Your password was successfully reset.",
                "actor_name": actor_name,
            }
            return format_response(**response, status=HTTP_200_OK)
        else:
            return format_response(
                error="Verification link is corrupted or expired",
                status=HTTP_401_UNAUTHORIZED,
            )


class BankDetailsViewSet(viewsets.ViewSet):
    """View to add bank details for a user"""

    serializer_class = BankDetailsSerializer

    def create(self, request):
        bank_details = request.data
        user = request.user
        serializer = self.serializer_class(data=bank_details,
                                           context={"request": request})

        if not serializer.is_valid():
            return format_response(error=serializer.errors, status=HTTP_400_BAD_REQUEST)

        actor_name = f"{user.first_name} {user.last_name}"
        return format_response(
            data=serializer.data,
            message="Bank detail successfully added",
            log="successfully added bank detail",
            actor_name=actor_name,
            status=HTTP_201_CREATED,
        )

    def list(self, request):
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]
        queryset = BankAccount.objects.filter(**field_opts)
        serializer = BankDetailsSerializer(queryset, many=True)
        actor_name = f"{user.first_name} {user.last_name}"
        return format_response(
            data=serializer.data,
            log="successfully retrieved all bank detail",
            actor_name=actor_name,
            message="Bank accounts retrieved successfully",
            status=HTTP_200_OK,
        )

    def destroy(self, request, pk):
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]
        try:
            account_detail = BankAccount.objects.get(pk=pk, **field_opts)
        except BankAccount.DoesNotExist:
            return format_response(
                error="Account detail does not exist for user",
                status=HTTP_404_NOT_FOUND,
            )
        account_detail.state = StateType.deleted.value
        account_detail.save()
        actor_name = f"{user.first_name} {user.last_name}"
        return format_response(
            message="Successfully deleted bank detail",
            log=f"successfully deleted bank detail",
            actor_name=actor_name,
            status=HTTP_200_OK,
        )


class BankListView(mixins.ListModelMixin, viewsets.GenericViewSet):
    """View to add bank details for a user"""

    def list(self, request):
        bank_list = BankingApi.retrieve_bank_list()
        if not bank_list:
            format_response(error="Could not retrieve bank list")
        return format_response(data=bank_list, message="successfully retrived bank list")


class ProfileView(APIView):
    personal_serializer_class = PersonalUserProfileSerializer
    business_serializer_class = BusinessUserProfileSerializer

    def patch(self, request):
        data = request.data
        user = request.user

        if data.get("password") is not None:
            if not data.get("old_password"):
                return format_response(
                    error="You must supply both old and new password",
                    status=HTTP_400_BAD_REQUEST,
                )
            old_password = data.get("old_password")
            check_old_password = user.check_password(old_password)

            if not check_old_password:
                return format_response(
                    error="password does not match old password!",
                    status=HTTP_400_BAD_REQUEST,
                )

        user_type = parse_user_type(user)
        serializer_opts = dict(
            personal=self.personal_serializer_class,
            business=self.business_serializer_class,
        )

        serializer = serializer_opts[user_type]
        serializer = serializer(user, data=data, partial=True, context=dict(user=user))

        if not serializer.is_valid():
            return format_response(errors=serializer.errors, status=HTTP_400_BAD_REQUEST)

        serializer.save()

        return format_response(
            data=serializer.data,
            message="Profile Updated successfully",
            status=HTTP_200_OK,
        )

    def get(self, request):
        user = request.user
        user_type = parse_user_type(user)
        serializer_opts = dict(
            personal=self.personal_serializer_class,
            business=self.business_serializer_class,
        )
        serializer = serializer_opts[user_type]
        serialized_data = serializer(user).data
        return format_response(
            data=serialized_data,
            log="Successfully viewed profile",
            status=HTTP_200_OK,
        )


class UpdateBusinessView(APIView):
    """
     Functions of this view class:
     1. take in business update details
     2. update business
    """

    serializer_class = BusinessUserProfileSerializer

    def patch(self, request):
        data = request.data
        business = Business.objects.get(user_ptr_id=request.user.id)

        if data.get("password") is not None:
            if not data.get("old_password"):
                return format_response(
                    error="You must supply both old and new password",
                    status=HTTP_400_BAD_REQUEST,
                )
            old_password = data.get("old_password")
            check_old_password = business.check_password(old_password)

            if not check_old_password:
                return format_response(
                    error="password does not match old password!",
                    status=HTTP_400_BAD_REQUEST,
                )

        serializer = self.serializer_class(business, data=data, partial=True)

        if not serializer.is_valid():
            return format_response(errors=serializer.errors, status=HTTP_400_BAD_REQUEST)
        serializer.save()
        actor_name = f"{business.first_name} {business.last_name}"
        return format_response(
            messagez="Business profile Updated successfully",
            log="successfully updated business profile",
            actor_name=actor_name,
            status=HTTP_200_OK,
        )

    def get(self, request):
        business = Business.objects.get(user_ptr_id=request.user.id)
        serializer = self.serializer_class(business)
        actor_name = f"{business.first_name} {business.last_name}"
        return format_response(
            data=serializer.data,
            log="successfully viewed business profile",
            actor_name=actor_name,
            status=HTTP_200_OK,
        )


class KYCViewSet(viewsets.ViewSet):
    """View to add and update KYC"""

    serializer_class = UserKYCSerializer

    def create(self, request):
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]
        password = request.data.get("password", "")
        pwd_valid = check_password(password, user.password)
        if not pwd_valid:
            return format_response(
                error={"password": ["Incorrect password entered"]},
                status=HTTP_401_UNAUTHORIZED,
            )

        kyc = UserKYC.objects.filter(**field_opts).first()
        if kyc:
            return format_response(error="You already have added your KYC",
                                   status=HTTP_400_BAD_REQUEST)

        serializer = self.serializer_class(data=request.data,
                                           context={"user": {
                                               **field_opts
                                           }})
        if not serializer.is_valid():
            return format_response(error=serializer.errors, status=HTTP_400_BAD_REQUEST)
        serializer.save()
        return format_response(data=serializer.data, status=HTTP_201_CREATED)

    def update(self, request, pk):
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]
        password = request.data.get("password", "")
        pwd_valid = check_password(password, user.password)
        if not pwd_valid:
            return format_response(
                error={"password": ["Incorrect password entered"]},
                status=HTTP_401_UNAUTHORIZED,
            )

        kyc = UserKYC.objects.filter(pk=pk, **field_opts).first()
        if not kyc:
            return format_response(
                error={"kyc_id": ["KYC information was not found"]},
                status=HTTP_404_NOT_FOUND,
            )

        serializer = self.serializer_class(kyc, data=request.data, partial=True)

        if not serializer.is_valid():
            return format_response(error=serializer.errors, status=HTTP_400_BAD_REQUEST)
        serializer.save()

        return format_response(data=serializer.data,
                               message="KYC updated successfully",
                               status=HTTP_200_OK)

    def retrieve(self, request, pk):
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]
        kyc = UserKYC.objects.filter(pk=pk, **field_opts).first()
        if not kyc:
            return format_response(
                error={"kyc_id": "KYC information was not found"},
                status=HTTP_404_NOT_FOUND,
            )
        serializer = self.serializer_class(kyc)
        return format_response(data=serializer.data, status=HTTP_200_OK)

    def list(self, request):
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]
        kyc = UserKYC.objects.filter(**field_opts)
        serializer = self.serializer_class(kyc, many=True)
        return format_response(data=serializer.data, status=HTTP_200_OK)


class NextOfKinViewSet(viewsets.ViewSet):
    serializer_class = NextOfKinSerializer

    def create(self, request):
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]
        password = request.data.get("password", "")
        pwd_valid = check_password(password, user.password)
        if not pwd_valid:
            return format_response(
                error={"password": ["Incorrect password entered"]},
                status=HTTP_403_FORBIDDEN,
            )

        next_of_kin = NextOfKin.objects.filter(**field_opts).first()
        if next_of_kin:
            return format_response(
                error="You've already added a next of kin",
                status=HTTP_400_BAD_REQUEST,
            )

        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return format_response(error=serializer.errors, status=HTTP_400_BAD_REQUEST)
        serializer.save(user=user)
        return format_response(data=serializer.data, status=HTTP_200_OK)

    def retrieve(self, request, pk):
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]
        next_of_kin = NextOfKin.objects.filter(pk=pk, **field_opts).first()
        if not next_of_kin:
            return format_response(
                error={"id": "Next of kin information was not found"},
                status=HTTP_404_NOT_FOUND,
            )
        serializer = self.serializer_class(next_of_kin)
        return format_response(data=serializer.data, status=HTTP_200_OK)

    def list(self, request):
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]
        next_of_kin = NextOfKin.objects.filter(**field_opts)
        serializer = self.serializer_class(next_of_kin, many=True)
        return format_response(data=serializer.data, status=HTTP_200_OK)

    def delete(self, request, pk):
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]
        next_of_kin = NextOfKin.objects.filter(pk=pk, **field_opts).first()
        if not next_of_kin:
            return format_response(message="Next of kin data not found.",
                                   status=HTTP_400_BAD_REQUEST)
        # next_of_kin.status = StateType.deleted.value
        next_of_kin.delete()
        return format_response(message="Your next of kin has been deleted",
                               status=HTTP_200_OK)


class DebitCardViewSet(viewsets.ViewSet):
    """ View set to handle operations on a users card """

    serializer_class = DebitCardSerializer

    def create(self, request):
        card_details = request.data
        user = request.user
        serializer = self.serializer_class(data=card_details,
                                           context={"request": request})
        if not serializer.is_valid():
            return format_response(
                error=serializer.errors.get("errors", serializer.errors),
                status=HTTP_400_BAD_REQUEST,
            )
        actor_name = f"{user.first_name} {user.last_name}"
        return format_response(
            data=serializer.data,
            message="Card details successfully added",
            log="Successfully added debit card",
            actor_name=actor_name,
            status=HTTP_201_CREATED,
        )

    def destroy(self, request, pk):
        try:
            user = request.user
            user_type = parse_user_type(user)
            field_opts = dict(personal=dict(user=user),
                              business=dict(business=user))[user_type]
            debit_card = DebitCard.objects.get(pk=pk, **field_opts)
            debit_card.state = StateType.deleted
            debit_card.save()
            actor_name = f"{user.first_name} {user.last_name}"
            return format_response(
                message="Successfully deleted debit card",
                log="successfully deleted debit card",
                actor_name=actor_name,
                status=HTTP_200_OK,
            )
        except DebitCard.DoesNotExist:
            return format_response(error="This debit card does not exist",
                                   status=HTTP_404_NOT_FOUND)

    def list(self, request):
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]
        queryset = DebitCard.objects.filter(**field_opts)
        serializer = DebitCardSerializer(queryset, many=True)
        actor_name = f"{user.first_name} {user.last_name}"
        return format_response(
            data=serializer.data,
            message="Cards retrieved successfully",
            log="successfully retrieved debit cards",
            actor_name=actor_name,
            status=HTTP_200_OK,
        )


class LogoutView(APIView):
    """
     Functions of this view class:
     1. takes the token from the header
     2. logsout the user
    """

    permission_classes = ()

    def post(self, request):
        user = request.user
        token = "".join(request.headers.get("authorization", []).split())[6:]

        black_listed_tokens = retrieve_from_redis("blacklisted_tokens")
        backlist_data = {"user_id": user.id,
                         "token": token, "logout_at": timezone.now()}

        if black_listed_tokens is None:
            black_listed_tokens = []
            black_listed_tokens.append(backlist_data)
            save_in_redis("blacklisted_tokens", black_listed_tokens)
            actor_name = f"{user.first_name} {user.last_name}"
            return format_response(
                data=backlist_data,
                log=f"{actor_name} Logged out",
                actor_name=actor_name,
                status=HTTP_200_OK,
            )

        invalid_tokens = [
            invalid_token["token"] for invalid_token in black_listed_tokens
            if invalid_token["user_id"] == user.id
        ]

        if token in invalid_tokens:
            return format_response(error="You are already logged out",
                                   status=HTTP_400_BAD_REQUEST)
        else:
            black_listed_tokens.append(backlist_data)
            save_in_redis("blacklisted_tokens", black_listed_tokens)
            actor_name = f"{user.first_name} {user.last_name}"
            return format_response(
                data=backlist_data,
                log=f"{actor_name} Logged out",
                actor_name=actor_name,
                status=HTTP_200_OK,
            )


class TudoViewset(viewsets.ViewSet):

    serializer_class = TudoSerializer

    def create(self, request):
        if "tudos" not in request.data.keys() or not isinstance(
                request.data.get("tudos"), list):
            return format_response(error="Tudo key missing or Tudo list is empty",
                                   status=400)

        serializer = self.serializer_class(data=request.data,
                                           context={"request": request})

        if not serializer.is_valid():
            return format_response(
                error=serializer.errors.get("tudos").get("errors", serializer.errors),
                status=HTTP_400_BAD_REQUEST,
            )

        user = request.user
        user_first_name = user.first_name
        user_email = user.email
        send_new_tudo_list_email.delay(
            user_first_name=user_first_name,
            user_email=user_email,
            details={"tudo_list": serializer.data["tudos"]},
        )
        actor_name = f"{user.first_name} {user.last_name}"
        return format_response(
            data=serializer.data,
            message="You've successfully created a Tudo list",
            log="successfully created a Tudo list",
            actor_name=actor_name,
            status=HTTP_201_CREATED,
        )

    def partial_update(self, request, pk):
        if not request.data:
            return format_response(error="Provide fields to be updated",
                                   status=HTTP_400_BAD_REQUEST)
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]
        tudo = Tudo.tudo_status.running().filter(pk=pk, **field_opts).first()
        if not tudo:
            return format_response(error="Goal does not exist",
                                   status=HTTP_404_NOT_FOUND)

        serializer = TudoModelSerializer(
            tudo,
            data=request.data,
            partial=True,
            context={
                "user_type": user_type,
                "user": {
                    **field_opts
                }
            },
        )

        if not serializer.is_valid():
            return format_response(error=serializer.errors, status=HTTP_400_BAD_REQUEST)
        serializer.save()
        actor_name = f"{user.first_name} {user.last_name}"

        return format_response(
            data=serializer.data,
            message="Tudo Updated successfully",
            log="successfully updated Tudo",
            actor_name=actor_name,
            status=HTTP_200_OK,
        )

    def list(self, request):
        tudos_type = request.query_params.get("type")
        user = request.user
        category = request.query_params.get("category", ".+")

        if tudos_type and tudos_type in ["running", "completed", "paid"]:
            if tudos_type == "running":
                tudos = Tudo.tudo_status.running
            elif tudos_type == "completed":
                tudos = Tudo.tudo_status.completed
            elif tudos_type == "paid":
                tudos = Tudo.tudo_status.paid
            tudos_by_category = tudos().filter(
                category__category__iregex=r"^{}$".format(category))
            tudos = get_tudos(request, tudos_by_category, tudos_type)
            return tudos

        query = request.query_params.get("query")
        if query:
            return search_tudos(request, query, parse_query_params(request))

        paginator = CustomPaginator(url_suffix="api/v1/tudo")
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]

        user_tudos = Tudo.objects.filter(**field_opts)

        tudos = paginator.paginate_queryset(
            user_tudos.filter(category__category__iregex=r"^{}$".format(category)),
            request,
        )

        serializer = TudoModelSerializer(tudos, many=True)
        actor_name = f"{user.first_name} {user.last_name}"
        return paginator.get_paginated_response(
            data=serializer.data,
            message="Tudos retrieved successfully",
            log="successfully retrieved all Tudos",
            actor_name=actor_name,
            status=HTTP_200_OK,
        )

    def retrieve(self, request, pk=None):
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]
        tudo = Tudo.objects.filter(pk=pk, **field_opts).first()
        if tudo is None:
            return format_response(error="This goal was not found",
                                   status=HTTP_404_NOT_FOUND)

        serializer = TudoModelSerializer(tudo)
        approved_tudo_contributions = TudoContribution.objects.filter(
            tudo_code=tudo.share_code, status=TransactionStatus.SUCCESS.value)

        transactions = TudoTransactionSerializer(approved_tudo_contributions, many=True)
        data = serializer.data
        data["transactions"] = transactions.data

        actor_name = f"{user.first_name} {user.last_name}"
        return format_response(
            data=data,
            message="Tudo retrieved successfully",
            log=f"successfully retrieved {tudo.goal_name} Tudo",
            actor_name=actor_name,
            status=HTTP_200_OK,
        )

    def destroy(self, request, pk=None):
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]

        tudo = Tudo.objects.filter(pk=pk, **field_opts).first()
        if not tudo:
            return format_response(error="This Tudo does not exist",
                                   status=HTTP_404_NOT_FOUND)

        if tudo.amount_generated == 0:
            tudo.state = StateType.deleted.value
            tudo.save()
            actor_name = f"{user.first_name} {user.last_name}"
            return format_response(
                message="Successfully deleted Tudo",
                log=f"successfully deleted {tudo.goal_name} Tudo",
                actor_name=actor_name,
                status=HTTP_200_OK,
            )
        else:
            return format_response(
                error="You cannot delete a tudo that has been funded",
                status=HTTP_400_BAD_REQUEST,
            )


class TudoContributionViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    permission_classes = ()
    authentication_classes = ()
    serializer_class = TudoContributionSerializer

    def create(self, request):
        contribution = request.data
        if contribution.get("tudo_code"):
            tudo_instance = Tudo.objects.filter(
                share_code=contribution["tudo_code"]).first()
            if not tudo_instance:
                return format_response(error={"tudo_code": ["Tudo not found"]},
                                       status=HTTP_404_NOT_FOUND)
            if tudo_instance.status == "TudoStatus.completed":
                return format_response(
                    error={"tudo_code": ["Tudo already completed"]},
                    status=HTTP_400_BAD_REQUEST,
                )
            if tudo_instance.status == "TudoStatus.paid":
                return format_response(
                    error={"tudo_code": ["Tudo already paid"]},
                    status=HTTP_400_BAD_REQUEST,
                )

        serializer = self.serializer_class(data=contribution,
                                           context={"request": request})

        if not serializer.is_valid():
            return format_response(error=serializer.errors, status=HTTP_400_BAD_REQUEST)

        validated_data = serializer.data
        transaction_reference = str(uuid.uuid4())
        user = tudo_instance.user or tudo_instance.business
        shortend_goal_title = shorten(tudo_instance.goal_name.title(),
                                      20,
                                      placeholder='...')
        payload = dict(txref=transaction_reference,
                       amount=validated_data["amount"] / 100,
                       currency=tudo_instance.currency,
                       customer_email=validated_data["contributor_email"],
                       redirect_url=settings.FRONTEND_URL + "/paymentSuccess",
                       custom_title=CUSTOM_GOAL_TEXT.format(user.first_name,
                                                            shortend_goal_title))

        if validated_data["scope"] == "international":
            save_in_redis(
                f"ref-meta-{transaction_reference}",
                dict(
                    transaction_type=TransactionType.TUDO_CONTRIBUTION,
                    contributor_email=validated_data["contributor_email"],
                    contributor_name=validated_data["contributor_name"],
                    tudo_code=validated_data["tudo_code"],
                ),
                timeout=86400,  # 24hrs validity
            )
            response = FlutterWaveAPI.initialize(**payload)

            if response is None:
                delete_from_redis(f"ref-meta-{transaction_reference}")
                return format_response(error="Payment Processor Error",
                                       status=HTTP_503_SERVICE_UNAVAILABLE)
        else:
            response = Transaction.initialize(
                reference=transaction_reference,
                amount=validated_data["amount"],
                currency=tudo_instance.currency,
                email=validated_data["contributor_email"],
                metadata={
                    **validated_data,
                    "transaction_type": TransactionType.TUDO_CONTRIBUTION,
                },
                callback_url=settings.FRONTEND_URL + "/paymentSuccess",
            )

        if response["status"] == "success" or response["status"] is True:
            return format_response(
                data={
                    "authorization_url":
                    response["data"].get("link")
                    or response["data"].get("authorization_url")
                },
                message="Authorization URL created",
                status=HTTP_201_CREATED,
            )

        return format_response(
            error="Payment Processor Error - Error Reported",
            status=HTTP_500_INTERNAL_SERVER_ERROR,
        )


class GetTudoContributionViewset(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = ()
    authentication_classes = ()
    serializer_class = TudoContributionSerializer

    def retrieve(self, request, pk=None):
        tudo_contribution_reference = pk
        user = request.user
        if tudo_contribution_reference:
            tudo_contribution = TudoContribution.objects.filter(
                reference=tudo_contribution_reference).first()

            if not tudo_contribution:
                return format_response(error="Tudo contribution not found",
                                       status=HTTP_404_NOT_FOUND)

            serializer = TudoContributionSerializer(tudo_contribution)
            contributed_amount = serializer.data.pop("amount")
            contribution_current = tudo_contribution.tudo_code.amount_generated
            contribution_target = tudo_contribution.tudo_code.amount
            contribution_percentage_current = round(
                (D(contribution_current) / D(contribution_target)) * 100, 2)
            data = {
                "status": tudo_contribution.status,
                "contributed_at": tudo_contribution.updated_at,
                "contributed_amount": contributed_amount,
                "contribution_current": contribution_current,
                "contribution_current_percentage": contribution_percentage_current,
                "contribution_target": contribution_target,
                "tudo_media": tudo_contribution.tudo_code.tudo_media,
                "beneficiary_name": tudo_contribution.tudo_code.user.first_name,
            }
            data.update(serializer.data)
            del data["amount"]
            del data["contributor_email"]
            if user.id:
                actor_name = f"{user.first_name} {user.last_name}"
            else:
                actor_name = "Anonymous"
            log = f"successfully retrieved Tudo contribution"
            return format_response(
                data=data,
                message="Tudo contribution retrieved successfully",
                log=log,
                actor_name=actor_name,
                status=HTTP_200_OK,
            )
        else:
            return format_response(status=HTTP_404_NOT_FOUND)


class TransactionWebHook(viewsets.ViewSet):
    """ Webhook to complete update transactions """

    authentication_classes = ()
    permission_classes = ()

    def create(self, request):
        try:
            payment_gateway = None
            is_valid_signature = False
            if request.headers.get("x-paystack-signature"):
                computed_hmac = hmac.new(
                    bytes(settings.PAYSTACK_SECRET_KEY, "utf-8"),
                    str.encode(request.body.decode("utf-8")),
                    digestmod=hashlib.sha512,
                ).hexdigest()
                is_valid_signature = hmac.compare_digest(
                    computed_hmac, str(request.headers.get("x-paystack-signature")))
                payment_gateway = "paystack"
            elif request.headers.get("verif-hash"):
                is_valid_signature = settings.FLUTTERWAVE_HASH == request.headers.get(
                    "verif-hash")
                payment_gateway = "flutterwave"

            if not is_valid_signature:
                return format_response(
                    error="You're not permitted to access this resource",
                    status=HTTP_403_FORBIDDEN,
                )

            if payment_gateway == "flutterwave":
                data = request.data
                transaction_ref = data.get('txRef')
                if 'data' in data.keys():
                    transaction_ref = data['data']['tx_ref']
                response = FlutterWaveAPI.verify(trans_ref=transaction_ref)
                if response["status"] == "success":
                    cached_trans_key = f"ref-meta-{transaction_ref}"
                    cached_request_meta = retrieve_from_redis(cached_trans_key)
                    transaction_type = cached_request_meta.get("transaction_type")
                    if transaction_type == TransactionType.TUDO_CONTRIBUTION:
                        params = dict(
                            reference=response["data"]["txref"],
                            amount=int(response["data"]["amount"] * 100),
                            metadata=dict(
                                tudo_code=cached_request_meta.get("tudo_code"),
                                contributor_email=cached_request_meta.get(
                                    "contributor_email"),
                                contributor_name=cached_request_meta.get(
                                    "contributor_name"),
                            ),
                        )

                        if TransactionHandler.process_tudo_contribution(params):
                            delete_from_redis(cached_trans_key)
                            return format_response(
                                message=TransactionType.TUDO_CONTRIBUTION,
                                status=HTTP_200_OK,
                            )

                    if transaction_type == TransactionType.GROUP_TUDO_CONTRIBUTION:
                        record_data = {
                            "group_tudo_id": cached_request_meta["group_tudo_id"],
                            "contributor_id": cached_request_meta["contributor_id"],
                            "amount_contributed": int(response["data"]["amount"] * 100),
                            "reference": response["data"]["txref"],
                            "currency": response["data"]["currency"],
                            "transaction_type": GROUPTUDO_TRANSACTION_TYPE[0][0],
                        }
                        GroupTudoContribution.objects.create(**record_data)
                        GroupTudoMembers.objects.filter(
                            member_id=record_data["contributor_id"],
                            group_tudo_id=record_data["group_tudo_id"],
                        ).update(amount_generated=F("amount_generated") +  # noqa
                                 record_data["amount_contributed"])
                        GroupTudo.objects.filter(id=record_data["group_tudo_id"])\
                            .update(
                                amount_generated=F("amount_generated") +  # noqa
                                record_data["amount_contributed"])
                        group_tudo = GroupTudo.objects.filter(
                            id=record_data["group_tudo_id"]).first()
                        if group_tudo:
                            if group_tudo.amount_generated >= group_tudo.target_amount:
                                group_tudo.update(status="COMPLETED")
                            # Todo - Send email to all members of the group with group summary
                            members_to_notify = GroupTudoMembers.objects.filter(
                                group_tudo_id=record_data["group_tudo_id"]).select_related('member')
                            contributing_member = members_to_notify.filter(
                                member_id=record_data["contributor_id"]).first()
                            for group_member in members_to_notify.exclude(id=contributing_member.id):
                                member_device = FCMDevice.objects.filter(
                                    user=group_member.member).order_by('-date_created').first()
                                if member_device:
                                    formated_contributed_amount = "{:,.2f}".format(
                                        int(record_data['amount_contributed']))
                                    member_device.send_message(
                                        data=dict(
                                            goal_id=record_data["group_tudo_id"], goal_type='group'),
                                        title="Group Goal Contribution Received",
                                        body=f"{contributing_member.member.first_name.title()} has contributed {record_data['currency']}{formated_contributed_amount} to {group_tudo.name} group goal"
                                    )

                        delete_from_redis(cached_trans_key)

                        return format_response(
                            message="GROUP_TUDO_CONTRIBUTION", status=HTTP_200_OK)

            if payment_gateway == "paystack":
                request_payload = request.data
                request_meta = (
                    request_payload["data"].get("metadata") if
                    not isinstance(request_payload["data"].get("metadata"), str) else {})
                transaction_type = request_meta.get("transaction_type")

                if request_payload["event"] == "charge.success":
                    if transaction_type == TransactionType.TUDO_CONTRIBUTION:
                        if TransactionHandler.process_tudo_contribution(
                                request_payload["data"]):
                            tudo_code = request_meta.get("tudo_code")
                            amount_kobo = int(request_meta.get("amount"))
                            tudo = Tudo.objects.filter(share_code=tudo_code).first()
                            user = tudo.user or tudo.business_account
                            actor_name = f"{user.first_name} {user.last_name}"

                            return format_response(
                                message=TransactionType.TUDO_CONTRIBUTION,
                                status=HTTP_200_OK,
                            )

                    if transaction_type == TransactionType.TUDO_TOPUP:
                        if TransactionHandler.process_tudo_topup(
                                request_payload["data"]):
                            amount_kobo = request_payload["data"]["amount"]
                            actor_name = request_meta.get("contributor_name")
                            goal_name = request_meta.get("goal_name")
                            return format_response(
                                message="Ok",
                                log=f"topped up {goal_name} Tudo with NGN{int(amount_kobo)/100}",
                                actor_name=actor_name,
                                status=HTTP_200_OK,
                            )

                    if transaction_type == TransactionType.LOCKED_SAVINGS:
                        transaction_ref = request_payload["data"]["reference"]
                        purpose = request_meta["savings_data"].get("purpose")
                        user = request_meta["savings_data"].get("user")
                        SavingsModel.objects.filter(
                            transaction_ref=transaction_ref).update(
                                transaction_status="SUCCESS", saving_status="RUNNING")
                        savings_instance = SavingsModel.objects.filter(
                            transaction_ref=transaction_ref).first()
                        if request_meta.get("is_scheduled"):
                            savings_instance.saved_amount = (
                                savings_instance.scheduled_start_amount)
                            savings_instance.scheduled_start_amount = 0
                            savings_instance.save()

                        data = {
                            "user_id": user.get("id"),
                            "savings_id": savings_instance.id,
                            "amount": request_payload["data"]["amount"],
                            "status": request_payload["data"]["status"],
                            "reference": transaction_ref,
                            "transaction_type": request_meta.get("transaction_type"),
                        }
                        user = User.objects.filter(id=user.get("id")).first()
                        existing_transaction = SavingsTransaction.objects.filter(
                            user=user).first()
                        if not existing_transaction:
                            inviter = User.objects.filter(id=user.invited_by).first()
                            if inviter:
                                inviter.points = (F("points") +
                                                  RewardPoints.savings_topup.value)
                                inviter.save()
                                rewards_data = {
                                    "inviter": inviter,
                                    "invitee": user,
                                    "type": REWARDTYPES[2][0],
                                    "points": RewardPoints.savings_topup.value,
                                }
                                Rewards(**rewards_data).save()

                        SavingsTransaction(**data).save()
                        # actor_name = f"{user.first_name} {user.last_name}"
                        return format_response(
                            message="ok",
                            # log=f"added to {purpose} locked savings",
                            # actor_name=actor_name,
                            status=HTTP_200_OK,
                        )

                    if transaction_type == TransactionType.TARGETED_SAVINGS:
                        transaction_ref = request_payload["data"]["reference"]
                        purpose = request_meta["savings_data"].get("purpose")
                        user = request_meta["savings_data"].get("user")
                        SavingsModel.objects.filter(
                            transaction_ref=transaction_ref).update(
                                transaction_status="SUCCESS", saving_status="RUNNING")
                        savings_instance = SavingsModel.objects.filter(
                            transaction_ref=transaction_ref).first()
                        if request_meta.get("is_scheduled"):
                            savings_instance.saved_amount = (
                                savings_instance.scheduled_start_amount)
                            savings_instance.scheduled_start_amount = 0
                            savings_instance.save()

                        data = {
                            "user_id": user.get("id"),
                            "savings_id": savings_instance.id,
                            "amount": request_payload["data"]["amount"],
                            "status": request_payload["data"]["status"],
                            "reference": transaction_ref,
                            "transaction_type": request_meta.get("transaction_type"),
                        }

                        user = User.objects.filter(id=user.get("id")).first()
                        existing_transaction = SavingsTransaction.objects.filter(
                            user=user).first()
                        if not existing_transaction:
                            inviter = User.objects.filter(id=user.invited_by).first()
                            if inviter:
                                inviter.points = (F("points") +
                                                  RewardPoints.savings_topup.value)
                                inviter.save()
                                rewards_data = {
                                    "inviter": inviter,
                                    "invitee": user,
                                    "type": REWARDTYPES[2][0],
                                    "points": RewardPoints.savings_topup.value,
                                }
                                Rewards(**rewards_data).save()

                        SavingsTransaction(**data).save()
                        # actor_name = f"{user.first_name} {user.last_name}"
                        return format_response(
                            message="ok",
                            # log=f"added to {purpose} targeted savings",
                            # actor_name=actor_name,
                            status=HTTP_200_OK,
                        )

                    if transaction_type == TransactionType.PERIODIC_SAVINGS:
                        transaction_ref = request_payload["data"]["reference"]
                        purpose = request_meta["savings_data"].get("purpose")
                        user = request_meta["savings_data"].get("user")
                        SavingsModel.objects.filter(
                            transaction_ref=transaction_ref).update(
                                transaction_status="SUCCESS", saving_status="RUNNING")
                        savings_instance = SavingsModel.objects.filter(
                            transaction_ref=transaction_ref).first()

                        if request_meta.get("is_scheduled"):
                            savings_instance.saved_amount = (
                                savings_instance.scheduled_start_amount)
                            savings_instance.scheduled_start_amount = 0
                            savings_instance.save()

                        data = {
                            "user_id": user.get("id"),
                            "savings_id": savings_instance.id,
                            "amount": request_payload["data"]["amount"],
                            "status": request_payload["data"]["status"],
                            "reference": transaction_ref,
                            "transaction_type": request_meta.get("transaction_type"),
                        }

                        user = User.objects.filter(id=user.get("id")).first()
                        existing_transaction = SavingsTransaction.objects.filter(
                            user=user).first()
                        if not existing_transaction:
                            inviter = User.objects.filter(id=user.invited_by).first()
                            if inviter:
                                inviter.points = (F("points") +
                                                  RewardPoints.savings_topup.value)
                                inviter.save()
                                rewards_data = {
                                    "inviter": inviter,
                                    "invitee": user,
                                    "type": REWARDTYPES[2][0],
                                    "points": RewardPoints.savings_topup.value,
                                }
                                Rewards(**rewards_data).save()

                        SavingsTransaction(**data).save()

                        # actor_name = f"{user.get('first_name')} {user.get('last_name')}"

                        return format_response(
                            message="ok",
                            # log=f"added to {purpose} periodic savings",
                            # actor_name=actor_name,
                            status=HTTP_200_OK,
                        )

                    if transaction_type == TransactionType.SAVINGS_TOPUP:
                        savings_id = request_meta.get("savings_id")
                        amount = request_payload["data"]["amount"]
                        actor_name = request_meta.get("full_name")
                        purpose = request_meta.get("purpose")
                        SavingsModel.objects.filter(id=savings_id).update(
                            saved_amount=F("saved_amount") + amount)
                        savings = SavingsModel.objects.filter(id=savings_id).first()

                        if (savings and not savings.plan_type.type == "Locked"
                                and savings.target_amount <= savings.saved_amount):
                            savings.saving_status = "COMPLETED"
                            savings.save()

                        if savings:
                            data = {
                                "user_id": savings.user_id,
                                "savings_id": savings.id,
                                "amount": amount,
                                "status": request_payload["data"]["status"],
                                "reference": request_payload["data"]["reference"],
                                "transaction_type": request_meta.get("transaction_type"),
                            }

                            user = User.objects.filter(id=savings.user_id).first()
                            existing_transaction = SavingsTransaction.objects.filter(
                                user=user).first()
                            if not existing_transaction:
                                inviter = User.objects.filter(
                                    id=user.invited_by).first()
                                if inviter:
                                    inviter.points = (F("points") +
                                                      RewardPoints.savings_topup.value)
                                    inviter.save()
                                    rewards_data = {
                                        "inviter": inviter,
                                        "invitee": user,
                                        "type": REWARDTYPES[2][0],
                                        "points": RewardPoints.savings_topup.value,
                                    }
                                    Rewards(**rewards_data).save()
                            SavingsTransaction(**data).save()

                        return format_response(
                            message="Ok",
                            # log=f"sucessfully topped up {purpose} Savings with NGN{int(amount)/100}",
                            # actor_name=actor_name,
                            status=HTTP_200_OK,
                        )

                    if transaction_type == TransactionType.ADDED_CARD:
                        # TODO - Add contibutions to users wallet
                        wallet = Wallet.objects.filter(
                            user__email=request_payload["data"]["customer"]['email'].lower()).first()
                        if not wallet:
                            capture_exception(error=Exception('Wallet not found'))
                            return format_response(message="ADDED_CARD", status=HTTP_200_OK)

                        amount = request_payload["data"]["amount"] - \
                            request_payload["data"]["fees"]
                        wallet.balance = (F("balance") + amount)
                        wallet.save()
                        WalletTransactions.objects.create(
                            amount=amount,
                            reference=request_payload["data"]["reference"],
                            transaction_type=WALLET_TRANSACTION_TYPE[1][0],
                            transaction_trigger="ADDED_CARD",
                            wallet=wallet,
                        )

                        return format_response(message="ADDED_CARD", status=HTTP_200_OK)

                    if transaction_type == TransactionType.GROUP_TUDO_CONTRIBUTION:
                        record_data = {
                            "group_tudo_id": request_meta["group_tudo_id"],
                            "contributor_id": request_meta["contributor_id"],
                            "amount_contributed": request_payload["data"]["amount"],
                            "reference": request_payload["data"]["reference"],
                            "currency": request_payload["data"]["currency"],
                            "transaction_type": GROUPTUDO_TRANSACTION_TYPE[0][0],
                        }
                        GroupTudoContribution.objects.create(**record_data)
                        GroupTudoMembers.objects.filter(
                            member_id=record_data["contributor_id"],
                            group_tudo_id=record_data["group_tudo_id"],
                        ).update(amount_generated=F("amount_generated") +
                                 record_data["amount_contributed"])
                        GroupTudo.objects.filter(id=record_data["group_tudo_id"]).update(
                            amount_generated=F("amount_generated") +
                            record_data["amount_contributed"])
                        return format_response(message="GROUP_TUDO_CONTRIBUTION",
                                               status=HTTP_200_OK)

                    if transaction_type == TransactionType.FUND_WALLET:
                        wallet = Wallet.objects.filter(
                            id=request_meta["wallet_id"]).first()
                        wallet.balance = (F("balance") +
                                          request_payload["data"]["amount"])
                        wallet.save()
                        WalletTransactions.objects.create(
                            amount=request_payload["data"]["amount"],
                            reference=request_payload["data"]["reference"],
                            transaction_type=WALLET_TRANSACTION_TYPE[1][0],
                            transaction_trigger=WALLET_TRANSACTION_TRIGGER[0][0],
                            wallet_id=request_meta["wallet_id"],
                        )
                        return format_response(message=TransactionType.FUND_WALLET,
                                               status=HTTP_200_OK)

            return format_response(error="An unexpected error occured",
                                   status=HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            capture_exception(error=e)
            return format_response(error=str(e), status=HTTP_500_INTERNAL_SERVER_ERROR)


class SharedTudoViewset(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = TudoSerializer
    authentication_classes = (AllowAnyUser, )
    permission_classes = (AllowListRetrieveOnly, )

    def retrieve(self, request, pk):
        tudo = Tudo.objects.filter(share_code=pk).first()
        user = request.user
        is_anonymous_user = True if isinstance(user, AnonymousUser) else False

        if tudo is None:
            return format_response(error="This Tudo was not found",
                                   status=HTTP_404_NOT_FOUND)

        serializer = TudoModelSerializer(
            tudo,
            context={
                "is_authenticated": False if is_anonymous_user else True,
                "user": user,
            },
        )

        if user.id:
            actor_name = f"{user.first_name} {user.last_name}"
        else:
            actor_name = "Anonymous"

        tudo_owner = tudo.user or tudo.business
        log = f"retrieved {tudo_owner.first_name} {tudo_owner.last_name}'s shared {tudo.goal_name} Tudo"

        return format_response(
            data=serializer.data,
            log=log,
            actor_name=actor_name,
            message="Tudo retrieved successfully",
            status=HTTP_200_OK,
        )


class TopUpTudoViewset(mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = TudoTopUpSerializer

    def create(self, request):
        serializer = self.serializer_class(data=request.data,
                                           context={"request": request})
        user = request.user

        if not serializer.is_valid():
            return format_response(error=serializer.errors, status=HTTP_400_BAD_REQUEST)

        tudo_contribution_references = retrieve_from_redis(
            "tudo_contribution_references")
        if not tudo_contribution_references:
            tudo_contribution_references = TudoContribution.objects.values_list(
                "reference", flat=True)
            save_in_redis("tudo_contribution_references", tudo_contribution_references,
                          60 * 3)

        transaction_reference = str(uuid.uuid4())
        while transaction_reference in tudo_contribution_references:
            transaction_reference = str(uuid.uuid4())

        tudo = Tudo.objects.filter(id=serializer.data["tudo_id"]).first()
        amount = serializer.data["topup_amount"]
        if serializer.data["card_id"] is None:
            response = Transaction.initialize(
                reference=transaction_reference,
                amount=amount,
                email=user.email,
                metadata={
                    **serializer.data,
                    "contributor_name": f"{user.first_name} {user.last_name}",
                    "goal_name": tudo.goal_name,
                    "transaction_type": TransactionType.TUDO_TOPUP,
                },
                callback_url=settings.FRONTEND_URL +
                f'/dashboard/tudo-single/{serializer.data["tudo_id"]}',
            )
            return format_response(
                data={"authorization_url": response["data"]["authorization_url"]},
                message=response["message"],
                status=HTTP_200_OK,
            )

        card = DebitCard.objects.filter(
            id=serializer.data["card_id"], user=user).first()
        response = Transaction.charge(
            reference=transaction_reference,
            authorization_code=card.authorization_code,
            amount=amount,
            email=user.email,
            metadata={
                **serializer.data,
                "contributor_name": f"{user.first_name} {user.last_name}",
                "transaction_type": TransactionType.TUDO_TOPUP,
            },
        )

        if not response.get("status"):
            return format_response(
                error="Error occured while charging the card",
                message=response.get("message"),
                status=HTTP_400_BAD_REQUEST,
            )

        if response.get("data").get("status") == "failed":
            return format_response(
                error="Error occured while charging the card",
                message=response.get("message"),
                status=HTTP_400_BAD_REQUEST,
            )

        actor_name = f"{user.first_name} {user.last_name}"

        return format_response(
            data={
                "amount": response.get("data").get("amount"),
                "reference": response.get("data").get("reference"),
            },
            message="Tudo has been topped-up successfully",
            log=f"successfully topped-up {tudo.goal_name} Tudo with NGN{amount/100}",
            actor_name=actor_name,
            status=HTTP_201_CREATED,
        )


class TudoFeedViewset(viewsets.ViewSet):
    serializer_class = TudoFeedSerializer

    def post(self, request):
        data = request.data
        user = request.user
        serializer = self.serializer_class(data=data)

        if not serializer.is_valid():
            return format_response(error=serializer.errors, status=HTTP_400_BAD_REQUEST)

        phone_nos = serializer.data["phone_numbers"]
        formated_nos = []
        for phone_no in phone_nos:
            formated_nos.append(phone_no)

        registered_contacts = User.objects.filter(
            reduce(lambda x, y: x | y, [Q(mobile_number__icontains=mobile_no) for mobile_no in formated_nos])).exclude(id=user.id).values_list("mobile_number", flat=True)

        save_in_redis(
            "syncedcontact-" + user.id,
            {
                "synced_time": datetime.now(),
                "synced_contacts": list(registered_contacts),
            },
        )

        contacts_running_goals = Tudo.objects.filter(
            user__mobile_number__in=list(registered_contacts)).filter(
            is_visible=True, status=TudoStatus.running.value)

        paginator = CustomPaginator(url_suffix="api/v1/my-tudo-feed")
        tudos_feeds = paginator.paginate_queryset(contacts_running_goals, request)
        tudo_feed_serializer = TudoContactFeedSerializer(tudos_feeds, many=True)
        return paginator.get_paginated_response(
            data=tudo_feed_serializer.data,
            query_params=parse_query_params(request),
            message="Contact Synced and Tudo Feeds retrieved successfully",
            status=HTTP_200_OK,
        )

    def list(self, request):
        user = request.user
        synced_contacts = retrieve_from_redis("syncedcontact-" + user.id)

        if not synced_contacts:
            return format_response(
                error="Feeds cannot be populated at this time. Kindly sync contacts",
                status=HTTP_404_NOT_FOUND,
            )

        available_contact_ids = User.objects.filter(
            mobile_number__in=synced_contacts["synced_contacts"]).values_list("id",
                                                                              flat=True)
        paginator = CustomPaginator(url_suffix="api/v1/my-tudo-feed")
        tudos_feeds = paginator.paginate_queryset(
            Tudo.objects.filter(user_id__in=available_contact_ids).filter(
                is_visible=True, status=TudoStatus.running.value),
            request,
        )
        tudo_feed_serializer = TudoContactFeedSerializer(tudos_feeds, many=True)
        return paginator.get_paginated_response(
            data=tudo_feed_serializer.data,
            query_params=parse_query_params(request),
            synced_time=synced_contacts["synced_time"],
            message="Tudo Feeds retrieved successfully",
            status=HTTP_200_OK,
        )


class WithdrawTudoViewSet(viewsets.ViewSet):

    serializer_class = WithdrawTudoSerializer

    @classmethod
    def set_tudo_status(cls, tudo, transaction_status):
        if (timezone.now().date() < tudo.completion_date.date()
                and tudo.amount_generated < tudo.amount):
            tudo.status = TudoStatus.running.value
        elif transaction_status == TransactionStatus.SUCCESS:
            tudo.status = TudoStatus.paid.value
        elif transaction_status == TransactionStatus.FAILED:
            tudo.status = TudoStatus.completed.value
        return tudo

    @classmethod
    def reverse_transaction(cls, tudo_id, user, transaction_status):
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]
        tudo = Tudo.objects.filter(id=tudo_id,
                                   status=TudoStatus.processing_withdrawal.value,
                                   **field_opts).first()
        WithdrawTudoViewSet.set_tudo_status(tudo, transaction_status).save()

    def create(self, request):
        withdraw_details = request.data
        serializer = self.serializer_class(
            data=withdraw_details,
            context={
                "user_type": parse_user_type(request.user),
                "user": request.user
            },
        )
        if not serializer.is_valid():
            return format_response(error=serializer.errors, status=HTTP_400_BAD_REQUEST)
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]

        # Todo - Removes checks for BVN, KYC and Next-of-Kin
        # is_valid_kyc = validate_kyc(user)
        # if not is_valid_kyc:
        #     return format_response(
        #         error='To make withdrawals you need to provide your BVN, a valid identity card, residential address and a next of kin',
        #         status=HTTP_403_FORBIDDEN)

        tudo_id = serializer.data["tudo_id"]
        bank_account_id = serializer.data["bank_account_id"]

        tudo_locked = Tudo.objects.filter(
            id=tudo_id, **field_opts, status=TudoStatus.completed.value).update(
                status=TudoStatus.processing_withdrawal.value)
        if not tudo_locked:
            return format_response(error="Withdrawal in progress",
                                   status=HTTP_400_BAD_REQUEST)

        tudo_to_withdraw = Tudo.objects.filter(
            id=tudo_id, status=TudoStatus.processing_withdrawal.value,
            **field_opts).first()

        amount_withdrawable_kobo = (tudo_to_withdraw.amount_generated -
                                    tudo_to_withdraw.amount_withdrawn)

        if amount_withdrawable_kobo < 10000:
            self.reverse_transaction(tudo_id, request.user, TransactionStatus.FAILED)
            return format_response(
                error="Cannot withdraw amount less than NGN100",
                status=HTTP_400_BAD_REQUEST,
            )

        service_charge_kobo = amount_withdrawable_kobo * SERVICE_RATE
        amount_to_withdraw_kobo = amount_withdrawable_kobo - service_charge_kobo

        bank_account = BankAccount.objects.filter(
            id=bank_account_id, **field_opts).first()

        account_number = bank_account.account_number
        bank_code = bank_account.bank_code
        reference = "xerde-" + str(uuid.uuid4())[:14] + str(int(time.time()))
        transfer_response = BankingApi.transfer_money(
            amount=amount_to_withdraw_kobo / 100,
            account_number=account_number,
            bank_code=bank_code,
            transfer_type="inter",
            transaction_reference=reference,
            remark="{} Tudo Withdrawal".format(tudo_to_withdraw.goal_name),
        )

        if transfer_response.get("status") is True:
            tudo = Tudo.objects.filter(id=tudo_id, **field_opts).first()
            tudo.amount_withdrawn = F("amount_withdrawn") + amount_withdrawable_kobo

            WithdrawTudoViewSet.set_tudo_status(tudo, TransactionStatus.SUCCESS).save()
            TudoWithdrawal.objects.create(
                reference=reference,
                tudo=tudo_to_withdraw,
                bank_id=bank_account_id,
                amount=amount_to_withdraw_kobo,
                service_charge=service_charge_kobo,
                currency=tudo_to_withdraw.currency,
                **field_opts,
            )

            details = {
                "goal_name": tudo_to_withdraw.goal_name,
                "currency": tudo_to_withdraw.currency,
                "amount_generated": tudo_to_withdraw.amount_generated,
                "net_amt_withdrawn": amount_to_withdraw_kobo,
                "withdrawn_amount": amount_withdrawable_kobo,
                "service_charge": service_charge_kobo,
                "destination_bank_name": bank_account.bank_name,
                "charge_rate": round(SERVICE_RATE * 100),
                "destination_account_number": bank_account.account_number,
            }

            if tudo_to_withdraw.user:
                send_tudo_withdrawal_email.delay(
                    user_first_name=tudo_to_withdraw.user.first_name,
                    user_email=tudo_to_withdraw.user.email,
                    details=details,
                )
                actor_name = f"{user.first_name} {user.last_name}"

            elif tudo_to_withdraw.business:
                send_tudo_withdrawal_email.delay(
                    user_first_name=tudo_to_withdraw.business.business_name,
                    user_email=tudo_to_withdraw.business.email,
                    details=details,
                )
                actor_name = f"{tudo_to_withdraw.business.business_name}"

            return format_response(
                data={
                    "target_amount": tudo_to_withdraw.amount,
                    "amount_generated": tudo_to_withdraw.amount_generated,
                    "amount_withdrawable": amount_withdrawable_kobo,  # GROSS
                    "net_amt_withdrawn": amount_to_withdraw_kobo,  # NET
                    "service_charge": service_charge_kobo,
                },
                message="Withdrawal successful",
                log=f"Successfully withdraws from {tudo_to_withdraw.goal_name} Tudo",
                actor_name=actor_name,
                status=HTTP_200_OK,
            )

        self.reverse_transaction(tudo_id, request.user, TransactionStatus.FAILED)

        return format_response(error="Unable to complete transaction",
                               status=HTTP_503_SERVICE_UNAVAILABLE)


class NotificationViewSet(viewsets.ViewSet):
    """ View set to handle operations on user notification """

    serializer_class = NotificationSerializer

    def list(self, request):
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]
        paginator = CustomPaginator(url_suffix="api/v1/user-notification")
        notifications = paginator.paginate_queryset(
            Notification.objects.filter(**field_opts),
            request,
        )
        unread_count = Notification.objects.filter(
            status=NotificationStatus.unread.value,
            **field_opts,
        )
        serializer = self.serializer_class(notifications, many=True)
        actor_name = f"{user.first_name} {user.last_name}"
        return paginator.get_paginated_response(
            data=serializer.data,
            query_params=None,
            notification_count=unread_count.count(),
            message="Notification Retrieved successfully",
            log="successfully retrieved notifications",
            actor_name=actor_name,
            status=HTTP_200_OK,
        )

    def partial_update(self, request, pk):
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]
        notification = Notification.objects.filter(pk=pk, **field_opts).first()

        if not notification:
            return format_response(error="Notification does not exist",
                                   status=HTTP_404_NOT_FOUND)

        serializer = self.serializer_class(notification,
                                           data=request.data,
                                           partial=True,
                                           context={"user": user})

        if not serializer.is_valid():
            return format_response(error=serializer.errors.get('error',
                                                               serializer.errors),
                                   status=HTTP_400_BAD_REQUEST)

        serializer.save()
        actor_name = f"{user.first_name} {user.last_name}"
        return format_response(
            data=serializer.data,
            message="Updated successfully",
            log="successfully updated notifications",
            actor_name=actor_name,
            status=HTTP_200_OK,
        )


class TransactionHistoryViewSet(viewsets.ViewSet):
    def list(self, request):
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]
        transaction_type = request.query_params.get("type")
        tudo_codes = Tudo.objects.filter(**field_opts).values_list("share_code",
                                                                   flat=True)

        if transaction_type == "tudo-top-ups":
            paginator = CustomPaginator(url_suffix="api/v1/transaction-history")
            tudo_top_ups = paginator.paginate_queryset(
                TudoContribution.objects.filter(
                    tudo_code__in=tudo_codes,
                    contribution_type=TudoContributionType.TOPUP,
                ),
                request,
            )

            topup_serializer = TudoTransactionSerializer(tudo_top_ups, many=True)

            actor_name = f"{user.first_name} {user.last_name}"
            return paginator.get_paginated_response(
                data=topup_serializer.data,
                query_params=parse_query_params(request),
                message="Tudo top-up history retrieved successfully",
                log="successfully retrieved Tudo top-up history",
                actor_name=actor_name,
                status=HTTP_200_OK,
            )

        if transaction_type == "tudo-contributions":
            paginator = CustomPaginator(url_suffix="api/v1/transaction-history")
            tudo_contributions = paginator.paginate_queryset(
                TudoContribution.objects.filter(
                    tudo_code__in=tudo_codes,
                    contribution_type=TudoContributionType.USERCONTRIBUTION,
                ),
                request,
            )

            contribution_serializer = TudoTransactionSerializer(tudo_contributions,
                                                                many=True)
            actor_name = f"{user.first_name} {user.last_name}"
            return paginator.get_paginated_response(
                data=contribution_serializer.data,
                query_params=parse_query_params(request),
                message="Tudo contribution history retrieved successfully",
                log="successfully retrieved Tudo contribution history",
                actor_name=actor_name,
                status=HTTP_200_OK,
            )

        if transaction_type == "tudo-withdrawal":
            paginator = CustomPaginator(url_suffix="api/v1/transaction-history")
            tudo_withdrawal = paginator.paginate_queryset(
                TudoWithdrawal.objects.filter(**field_opts), request)

            tudo_withdrawal_serializer = TudoWithdrawTransactionSerializer(
                tudo_withdrawal, many=True)
            actor_name = f"{user.first_name} {user.last_name}"
            return paginator.get_paginated_response(
                data=tudo_withdrawal_serializer.data,
                query_params=parse_query_params(request),
                message="Tudo withdrawal history retrieved successfully",
                log="successfully retrieved Tudo withdrawal history",
                actor_name=actor_name,
                status=HTTP_200_OK,
            )

        # if transaction_type == "savings-withdrawal":
        #     paginator = CustomPaginator(
        #         url_suffix='api/v1/transaction-history')
        #     savings_withdrawal = paginator.paginate_queryset(
        #         SavingsWithdrawalModel.objects.filter(**field_opts), request)

        #     savings_withdrawal_serializer = SavingsWithdrawTransactionSerializer(
        #         savings_withdrawal, many=True)
        #     actor_name = f"{user.first_name} {user.last_name}"
        #     return paginator.get_paginated_response(
        #         data=[],
        #         query_params=parse_query_params(
        #             request),
        #         message='Savings withdrawal history retrieved successfully',
        #         log='successfully retrieved Savings withdrawal history',
        #         actor_name=actor_name,
        #         status=HTTP_200_OK)

        # if transaction_type == "savings-credited":
        #     paginator = CustomPaginator(
        #         url_suffix='api/v1/transaction-history')
        #     savings = paginator.paginate_queryset(
        #         SavingsModel.objects.filter(
        #             transaction_status='SUCCESS', **field_opts), request)

        #     savings_serializer = SavingsSerializer(savings, many=True)
        #     actor_name = f"{user.first_name} {user.last_name}"
        #     return paginator.get_paginated_response(
        #         data=[],
        #         query_params=parse_query_params(
        #             request),
        #         message='Saving credits history retrieved successfully',
        #         log='successfully retrieved Savings credits history',
        #         actor_name=actor_name,
        #         status=HTTP_200_OK)

        else:
            return format_response(error="Provide valid query params",
                                   status=HTTP_400_BAD_REQUEST)


class ApplicationSupportView(mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = ApplicationSupportSerializer
    authentication_classes = [AllowAnyUser]
    permission_classes = [AllowAny]

    def create(self, request):
        serializer = self.serializer_class(
            data=request.data,
            context={
                "user": request.user,
                "is_authenticated":
                True if request.user.is_authenticated is True else False,
            },
        )

        if not serializer.is_valid():
            return format_response(error=serializer.errors, status=HTTP_400_BAD_REQUEST)

        user_message = {
            "id": str(uuid.uuid4()),
            "full_name": serializer.data["full_name"],
            "mobile_number": serializer.data["mobile_number"],
            "email": serializer.data["email"],
            "subject": serializer.data["subject"],
            "message": serializer.data["message"],
        }

        send_application_support_email.delay(
            subject=serializer.data["subject"],
            message=serializer.data["message"],
            email=serializer.data["email"],
            full_name=serializer.data["full_name"],
        )

        support_messages = retrieve_from_redis("support-messages")
        if not support_messages:
            support_messages = []
            support_messages.append(user_message)
            save_in_redis("support-messages", support_messages, None)
        else:
            support_messages.append(user_message)
            save_in_redis("support-messages", support_messages, None)

        return format_response(
            message="Your enquire has been sent to " +
            "support, you will get a response shortly",
            data=serializer.data,
        )


class TrendingTudoViewset(mixins.ListModelMixin, viewsets.GenericViewSet):
    """View to add bank details for a user"""

    authentication_classes = [AllowAnyUser]
    permission_classes = [AllowAny]

    def list(self, request):
        paginator = CustomPaginator(url_suffix="api/v1/tudo/trending")
        trending_tudos = paginator.paginate_queryset(
            Tudo.objects.get_all(),
            request,
        )

        serialized_trending_tudos = TrendingTudoSerializer(
            trending_tudos,
            many=True,
            context={
                "user": request.user,
                "is_authenticated":
                True if request.user.is_authenticated is True else False,
            },
        )
        return paginator.get_paginated_response(
            data=serialized_trending_tudos.data,
            query_params=parse_query_params(request),
            status=HTTP_200_OK,
        )


class LikeTudoViewset(viewsets.ViewSet):
    """ Viewset that handles liking and un-liking a tudo """

    lookup_field = "tudo_id"
    authentication_classes = [
        AllowAnyUser,
    ]
    permission_classes = [
        AllowListRetrieveOnly,
    ]

    def create(self, request):
        if "tudo_id" not in request.data.keys():
            return format_response(error=dict(tudo_id=["Please enter a tudo id"]),
                                   status=400)
        tudo_id = request.data["tudo_id"]
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]

        tudo = Tudo.objects.filter(id=tudo_id).first()

        if not tudo:
            return format_response(error=dict(tudo_id=["Tudo goal not found"]),
                                   status=HTTP_404_NOT_FOUND)

        liked_tudo = TudoLikes.objects.filter(tudo=tudo, **field_opts).first()

        if liked_tudo and liked_tudo.like_status == LIKE_STATUS[0][0]:
            liked_tudo.like_status = LIKE_STATUS[1][0]
            liked_tudo.save()
            likes_count = TudoLikes.objects.filter(
                tudo=tudo, like_status=LIKE_STATUS[0][0]).count()
            return format_response(
                data=dict(tudo_id=tudo.id, likes_count=likes_count, action="unliked"),
                status=HTTP_200_OK,
            )
        elif liked_tudo and liked_tudo.like_status == LIKE_STATUS[1][0]:
            liked_tudo.like_status = LIKE_STATUS[0][0]
            liked_tudo.save()
            likes_count = TudoLikes.objects.filter(
                tudo=tudo, like_status=LIKE_STATUS[0][0]).count()
            return format_response(
                data=dict(tudo_id=tudo.id, likes_count=likes_count, action="liked"),
                status=HTTP_200_OK,
            )

        TudoLikes.objects.create(tudo=tudo, like_status=LIKE_STATUS[0][0], **field_opts)

        likes_count = TudoLikes.objects.filter(tudo=tudo,
                                               like_status=LIKE_STATUS[0][0]).count()

        return format_response(
            data=dict(tudo_id=tudo.id, likes_count=likes_count, action="liked"),
            status=HTTP_201_CREATED,
        )

    def retrieve(self, request, tudo_id):

        tudo_likes = TudoLikes.objects.filter(tudo_id=tudo_id,
                                              like_status=LIKE_STATUS[0][0])
        paginator = CustomPaginator(url_suffix="api/v1/tudo/likes", page_size=10)
        likes = paginator.paginate_queryset(tudo_likes, request)
        likes = TudoLikesSerializer(likes, many=True)
        return paginator.get_paginated_response(data=likes.data, status=HTTP_200_OK)


class FollowTudoViewset(viewsets.ViewSet):
    """ Viewset that handles following and un-following a tudo """

    def create(self, request):
        if "tudo_id" not in request.data.keys():
            return format_response(error=dict(tudo_id=["Please enter a tudo id"]),
                                   status=400)
        tudo_id = request.data["tudo_id"]
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]

        tudo = Tudo.objects.filter(id=tudo_id).first()
        if not tudo:
            return format_response(error=dict(tudo_id=["Tudo goal not found"]),
                                   status=HTTP_404_NOT_FOUND)

        followed_tudo = TudoFollowers.objects.filter(tudo=tudo, **field_opts).first()

        if followed_tudo and followed_tudo.follow_status == FOLLOWING_STATUS[0][0]:
            followed_tudo.follow_status = FOLLOWING_STATUS[1][0]
            followed_tudo.save()
            follower_count = TudoFollowers.objects.filter(
                tudo=tudo, follow_status=FOLLOWING_STATUS[0][0]).count()
            return format_response(
                data=dict(tudo_id=tudo.id,
                          follower_count=follower_count,
                          action="unfollowed"),
                status=HTTP_200_OK,
            )

        elif followed_tudo and followed_tudo.follow_status == FOLLOWING_STATUS[1][0]:
            followed_tudo.follow_status = FOLLOWING_STATUS[0][0]
            followed_tudo.save()
            follower_count = TudoFollowers.objects.filter(
                tudo=tudo, follow_status=FOLLOWING_STATUS[0][0]).count()
            return format_response(
                data=dict(tudo_id=tudo.id,
                          follower_count=follower_count,
                          action="followed"),
                status=HTTP_200_OK,
            )

        TudoFollowers.objects.create(tudo=tudo,
                                     follow_status=FOLLOWING_STATUS[0][0],
                                     **field_opts)
        follower_count = TudoFollowers.objects.filter(
            tudo=tudo, follow_status=FOLLOWING_STATUS[0][0]).count()

        return format_response(
            data=dict(tudo_id=tudo.id, follower_count=follower_count, action="followed"),
            status=HTTP_201_CREATED,
        )


class CommentTudoViewset(viewsets.ViewSet):
    """ Viewset to manage coments """

    authentication_classes = [
        AllowAnyUser,
    ]
    permission_classes = [
        AllowListRetrieveOnly,
    ]
    serializer_class = TudoCommentSerializer
    lookup_field = "tudo_id"

    def create(self, request):
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]
        serializer = self.serializer_class(data=request.data,
                                           context={"user": {
                                               **field_opts
                                           }})
        if not serializer.is_valid():
            return format_response(
                error=serializer.errors.get("error", serializer.errors),
                status=HTTP_400_BAD_REQUEST,
            )
        serializer.save()
        return format_response(data=serializer.data, status=HTTP_201_CREATED)

    def retrieve(self, request, tudo_id):
        """ Retrieve Tudo Comments """
        comments_queryset = TudoComments.objects.filter(tudo_id=tudo_id)
        paginator = CustomPaginator(url_suffix="api/v1/tudo/comment", page_size=10)
        comment_paginated_qs = paginator.paginate_queryset(comments_queryset, request)
        comments = TudoCommentListSerializer(comment_paginated_qs, many=True)
        return paginator.get_paginated_response(data=comments.data, status=HTTP_200_OK)


class PublicSearchTudoViewset(mixins.ListModelMixin, viewsets.GenericViewSet):
    filter_backends = (filters.DjangoFilterBackend, )
    filterset_class = TudoSearchFilter
    serializer_class = TudoModelSerializer
    authentication_classes = [AllowAnyUser]
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = Tudo.objects.filter(is_visible=True)
        tudos = TudoSearchFilter(self.request.GET, queryset=qs)
        return tudos.qs

    def list(self, request):
        qs = self.filter_queryset(self.get_queryset())
        paginator = CustomPaginator(url_suffix="api/v1/tudo/search")
        tudos = paginator.paginate_queryset(qs, request)
        serialized_tudos = self.serializer_class(tudos, many=True, context={
            "user": request.user,
            "is_authenticated": True if request.user.is_authenticated is True else False,
        })
        return paginator.get_paginated_response(data=serialized_tudos.data,
                                                query_params=parse_query_params(request))


class TudoMediaViewset(viewsets.ViewSet):
    def create(self, request):
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]
        data = request.data
        media = data.get("media")

        if not media or not isinstance(media, list):
            return format_response(error="media key missing or media list is empty")

        serializer = TudoMediaSerializer(data=data,
                                         context={
                                             "tudo_id": data.get("tudo_id"),
                                             "user": {
                                                 **field_opts
                                             }
                                         })

        if not serializer.is_valid():
            return format_response(
                error=serializer.errors.get("errors", serializer.errors),
                status=HTTP_400_BAD_REQUEST,
            )

        media_data = serializer.save()
        return format_response(data=media_data, status=HTTP_201_CREATED)

    def retrieve(self, request, pk):
        tudo_media = TudoMedia.objects.filter(id=pk).first()

        if not tudo_media:
            return format_response(error="Media file not found",
                                   status=HTTP_404_NOT_FOUND)

        serializer = TudoMediaModelSerializer(tudo_media)

        return format_response(data=serializer.data, status=HTTP_200_OK)

    def list(self, request):
        tudo_id = request.query_params.get("tudo_id", None)
        if not tudo_id:
            return format_response(error="tudo_id parameter not specified",
                                   status=HTTP_400_BAD_REQUEST)

        tudo_media = TudoMedia.objects.filter(tudo__id=tudo_id)

        serializer = TudoMediaModelSerializer(tudo_media, many=True)

        return format_response(data=serializer.data, status=HTTP_200_OK)

    def destroy(self, request, pk):
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(tudo__user=user),
                          business=dict(tudo__business=user))[user_type]

        tudo_media = TudoMedia.objects.filter(id=pk, **field_opts).first()

        if not tudo_media:
            return format_response(error="Media file not found",
                                   status=HTTP_404_NOT_FOUND)

        tudo_media.state = StateType.deleted.value
        tudo_media.save()

        return format_response(message="Media file deleted", status=HTTP_200_OK)


class TudoTransactionsViewset(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    def retrieve(self, request, pk):
        user = request.user
        transaction_type = request.query_params.get("type", "all").lower()
        if transaction_type == "contributions":
            contributions = TudoContribution.objects.filter(
                tudo_code__id=pk,
                tudo_code__user=user,
                contribution_type=TudoContributionType.USERCONTRIBUTION,
            )
            withdrawals = TudoWithdrawal.objects.none()
        elif transaction_type == "topups":
            contributions = TudoContribution.objects.filter(
                tudo_code__id=pk,
                tudo_code__user=user,
                contribution_type=TudoContributionType.TOPUP,
            )
            withdrawals = TudoWithdrawal.objects.none()
        elif transaction_type == "withdrawals":
            contributions = TudoContribution.objects.none()
            withdrawals = TudoWithdrawal.objects.filter(tudo__id=pk, user=user)
        elif transaction_type == "all":
            contributions = TudoContribution.objects.filter(tudo_code__id=pk,
                                                            tudo_code__user=user)
            withdrawals = TudoWithdrawal.objects.filter(tudo__id=pk, user=user)
        else:
            contributions = TudoContribution.objects.none()
            withdrawals = TudoWithdrawal.objects.none()

        if request.query_params.get("sort", None) == "-date":
            descending_date = True
        else:
            descending_date = False

        all_transactions = sorted(
            chain(contributions, withdrawals),
            key=lambda x: x.created_at,
            reverse=descending_date,
        )

        paginator = CustomPaginator(url_suffix=f"api/v1/tudo/transactions/{pk}")
        paginated_transactions = paginator.paginate_queryset(all_transactions, request)
        serializer = TudoTransactionsSerializer(paginated_transactions, many=True)

        return paginator.get_paginated_response(
            data=serializer.data,
            query_params=parse_query_params(request),
            message="Tudo transactions retrieved successfully",
            status=HTTP_200_OK,
        )


class TudoCollectionViewset(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    def retrieve(self, request, pk=None):
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]

        tudo = Tudo.objects.filter(collection_code=pk, **field_opts)

        if not tudo:
            return format_response(error="No goals found in this collection",
                                   status=HTTP_404_NOT_FOUND)

        serializer = TudoModelSerializer(tudo, many=True)
        return format_response(data=serializer.data, status=HTTP_200_OK)


class SyncedContacts(mixins.ListModelMixin, viewsets.GenericViewSet):
    def list(self, request):
        user = request.user
        synced_contacts = retrieve_from_redis("syncedcontact-" + user.id)
        if not synced_contacts:
            return format_response(data=[], status=200)

        synced_users = User.objects.filter(
            mobile_number__in=synced_contacts["synced_contacts"])
        synced_users = [
            dict(
                id=user.id,
                name=f"{user.first_name} {user.last_name}",
                profile_image=user.profile_image,
                mobile_number=user.mobile_number,
            ) for user in synced_users
        ]
        return format_response(data=synced_users, status=200)


class SearchUsers(mixins.ListModelMixin, viewsets.GenericViewSet):
    filter_backends = (filters.DjangoFilterBackend, )
    filterset_class = UserSearchFilter

    def get_queryset(self):
        qs = User.objects.filter()
        users = UserSearchFilter(self.request.GET, queryset=qs)
        return users.qs

    def list(self, request):
        user_queryset = self.filter_queryset(self.get_queryset())
        found_users = [
            dict(
                id=user.id,
                name=f"{user.first_name} {user.last_name}",
                profile_image=user.profile_image,
                mobile_number=user.mobile_number,
            ) for user in user_queryset
        ]

        return format_response(data=found_users, status=200)


class ReferralViewset(viewsets.ViewSet):
    def list(self, request):
        """ Get Referal Stats """
        user = request.user
        invitees = User.objects.filter(invited_by=user.id, is_active=True)
        data = {
            "referral_count": invitees.count(),
            "referral_points": user.points,
            "cash_reward": user.points * NGN_PER_POINT * 100,
            "referral_code": user.invite_code,
        }
        serializer = ReferralSerializer(invitees, many=True)
        data["referrals"] = serializer.data
        return format_response(data=data, status=HTTP_200_OK)

    def create(self, request):
        """ Redeem Points """
        user = request.user
        points_redeemed = user.points
        if not user.points:
            return format_response(error="You don't have any points to redeem",
                                   status=HTTP_200_OK)
        cash_reward = user.points * NGN_PER_POINT * 100
        wallet = Wallet.objects.get(user=user)
        wallet.balance = F("balance") + cash_reward
        wallet_trans = WalletTransactions(
            amount=cash_reward,
            reference=str(uuid.uuid4()),
            transaction_type=WALLET_TRANSACTION_TYPE[1][0],
            transaction_trigger=WALLET_TRANSACTION_TRIGGER[3][0],
            wallet=wallet,
        )
        user.update(points=F("points") - user.points)
        wallet.save()
        wallet_trans.save()
        return format_response(
            data={
                "points_redeemed": points_redeemed,
                "cash_reward": cash_reward,
            },
            status=HTTP_200_OK,
        )

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

from .filters import TudoSearchFilter
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
        else:
            return format_response(error="Provide valid query params",
                                   status=HTTP_400_BAD_REQUEST)

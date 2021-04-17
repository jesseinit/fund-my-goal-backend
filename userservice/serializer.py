import itertools
import math
import random
import re
import string
import uuid
from datetime import datetime, timedelta
import requests

import phonenumbers
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db.models import F
from django.utils import timezone
from rest_framework import exceptions, serializers

from userservice.models import (BankAccount, Business, DebitCard, GroupTudo,
                                GroupTudoContribution, GroupTudoMembers,
                                GroupTudoWithdrawal, NextOfKin, Notification,
                                Tudo, TudoComments, TudoContribution,
                                TudoLikes, TudoMedia, TudoWithdrawal, User,
                                UserKYC)
from userservice.utils.helpers import (NotificationStatus, TransactionStatus,
                                       TudoContributionType, TudoStatus,
                                       create_invite_code, retrieve_from_redis,
                                       save_in_redis)
from userservice.utils.validations import (ValidateBusiness, ValidateTudo,
                                           ValidateUser,
                                           update_business_profile,
                                           update_profile, validate_address,
                                           validate_goal_name,
                                           validate_mobile_number,
                                           validate_name)
from utils.constants import (CURRENCIES, DEFAULT_AVATAR_URL,
                             GROUP_MEMBER_ROLES, GROUP_MEMBERSHIP_TYPE,
                             INVITE_STATUS, NOTIFICATION_ENTITY,
                             NOTIFICATION_INVITE_TEXT, NOTIFICATION_TYPE,
                             REQUIRED_BUSINESS_TUDO_FIELDS,
                             REQUIRED_PERSONAL_TUDO_FIELDS, SERVICE_RATE,
                             WITHDRAWAL_STATUS)
from utils.helpers import (BankingApi, GroupTudoHelper, MediaHandler,
                           delete_from_redis, generate_id, parse_user_type)

FRONTEND_URL = settings.FRONTEND_URL


class RegisterSerializer(serializers.ModelSerializer):
    access_token = serializers.CharField(required=False)
    auth_provider = serializers.ChoiceField(
        required=False, choices=["GOOGLE", "FACEBOOK"], default="LOCAL")

    class Meta:
        model = User
        fields = ["id", "mobile_number", "email", "first_name", "last_name",
                  "password", "invite_code", "is_active", "auth_provider", "access_token"]
        extra_kwargs = {
            "password": {"write_only": True},
            "social_password": {"write_only": True},
            "invite_code": {"read_only": True}
        }

    def validate_email(self, email):
        user = User.objects.filter(email=email.lower()).first() or \
            Business.objects.filter(email=email.lower()).first()
        if user:
            raise serializers.ValidationError(
                'A user has registered with this email address')
        return email

    def validate_auth_provider(self, auth_provider):
        if auth_provider in ["GOOGLE", "FACEBOOK"] and 'access_token' not in self.initial_data.keys():
            raise serializers.ValidationError(
                "Please provide an access token")
        return auth_provider

    def validate_access_token(self, access_token):
        if 'auth_provider' not in self.initial_data.keys():
            raise serializers.ValidationError(
                "Cannot pass access token without setting an Authentication Provider")

        auth_provider = self.initial_data['auth_provider']
        if auth_provider == "LOCAL":
            return False

        auth_provider_config = dict(GOOGLE={
            "url": "https://oauth2.googleapis.com/tokeninfo",
            "params": {"id_token": access_token}
        }, FACEBOOK={
            "url": "https://graph.facebook.com/me",
            "params": {"fields": "name,email",
                       "access_token": access_token}
        })

        response = requests.get(**auth_provider_config[auth_provider])
        if not response.ok:
            raise serializers.ValidationError("Cannot verify your social media account")
        user_id = response.json().get("id") or response.json().get("kid")
        setattr(self, 'social_password', user_id)
        return True

    def validate_mobile_number(self, mobile_number):
        try:
            phone_number = phonenumbers.parse(mobile_number, None)
            if phonenumbers.is_valid_number(phone_number) is False:
                raise serializers.ValidationError(
                    f"{mobile_number} is not a valid mobile number")

            mobile_number = phonenumbers.format_number(
                phone_number, phonenumbers.PhoneNumberFormat.E164)

            user = User.objects.filter(mobile_number=mobile_number).first()

            if user:
                raise serializers.ValidationError(
                    f"{mobile_number} has been used by another user")

            return mobile_number
        except phonenumbers.phonenumberutil.NumberParseException:
            raise serializers.ValidationError(
                f"{mobile_number} is not a valid mobile number.")

    def validate(self, data):
        validated_data = ValidateUser().validate_user_fields(**data)
        if isinstance(validated_data, list):
            raise serializers.ValidationError({"errors": validated_data})
        return validated_data

    def create(self, validated_data):
        if validated_data.get('access_token'):
            validated_data['social_password'] = self.social_password
            validated_data['is_active'] = True
        return User.objects.create_user(**validated_data)

    def update(self, instance, validated_data):
        instance.set_password(validated_data['password'])
        instance.save()
        return instance


class LoginSerializer(serializers.Serializer):
    ''' Serializer Class for Login ViewSet '''

    email = serializers.EmailField()
    password = serializers.CharField()
    acct_type = serializers.ChoiceField(choices=['personal', 'business'],
                                        default='personal')
    auth_type = serializers.ChoiceField(choices=['local', 'social'],
                                        default='local')
    device_id = serializers.CharField(required=False, default=None)
    device_registration_id = serializers.CharField(required=False, default=None)
    device_name = serializers.CharField(required=False, default=None)
    device_os_type = serializers.ChoiceField(choices=['android', 'ios'],
                                             default=None, required=False)


class AccountVerificationSerializer(serializers.Serializer):

    email = serializers.EmailField()
    otp = serializers.CharField(max_length=4, min_length=4)
    acct_type = serializers.ChoiceField(choices=['personal', 'business'],
                                        default='personal')

    def validate_otp(self, value):
        otp = value.strip()
        if re.match(r'^[0-9]{4}$', otp) is None:
            raise serializers.ValidationError(
                "OTP must be a 4 digit in length (ex.) 4565"
            )
        return otp


class OTPGenerateSerializer(serializers.Serializer):
    ''' Serializer Class for Login ViewSet '''
    email = serializers.EmailField()
    acct_type = serializers.ChoiceField(choices=['personal', 'business'],
                                        default='personal')


class PasswordResetLinkSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, email):
        user = User.objects.filter(email=email.lower()).first() or \
            Business.objects.filter(email=email.lower()).first()
        if not user:
            raise serializers.ValidationError(
                'This email adress was not found')
        return email.lower()


class PasswordResetSerializer(serializers.Serializer):
    new_password = serializers.CharField()

    def validate_new_password(self, new_password):
        if re.match('(?=.{8,100})', new_password) is None:
            raise serializers.ValidationError(
                "Password must have at least 8 characters")
        return new_password


class PersonalUserProfileSerializer(serializers.ModelSerializer):
    is_social_user = serializers.SerializerMethodField()
    account_type = serializers.SerializerMethodField()
    profile_image = serializers.CharField(required=False)
    gender = serializers.ChoiceField(choices=['male', 'female'], required=False)
    bvn = serializers.CharField(required=False, max_length=11, min_length=11)

    class Meta:
        model = User
        fields = ["id", "first_name", "last_name", "password", "birthday",
                  "gender", "profile_image", "email", "mobile_number", "is_social_user",
                  "color_scheme", "background_color", "is_active", "auth_provider",
                  "created_at", "updated_at", "invite_code", "bvn", "account_type"]
        extra_kwargs = {
            "password": {"write_only": True},
            'first_name': {'validators': [validate_name]},
            'last_name': {'validators': [validate_name]},
        }

    def get_is_social_user(self, obj):
        return True if obj.auth_provider in ["FACEBOOK", "GOOGLE"] else False

    def get_account_type(self, obj):
        return 'personal'

    def validate_mobile_number(self, mobile_number):
        user_instance = self.context.get('user')
        if user_instance.bvn:
            raise serializers.ValidationError(
                "You cannot update your phone number after adding your BVN")

        try:
            mobile_number = "".join(mobile_number.split())
            phone_number = phonenumbers.parse(mobile_number, None)
            if phonenumbers.is_valid_number(phone_number) is False:
                raise serializers.ValidationError(
                    f"{mobile_number} is not a valid mobile number")

            mobile_number = phonenumbers.format_number(
                phone_number, phonenumbers.PhoneNumberFormat.E164)
            user = User.objects.filter(
                mobile_number=mobile_number).exclude(id=user_instance.id).first()

            if user:
                raise serializers.ValidationError(
                    f"{mobile_number} has been used by another user")

            # Formats number to aid better comparism with BVN details
            f_mobile_number = 0
            if mobile_number:
                f_mobile_number = mobile_number[-10:]

            setattr(self, 'formated_mobile_number', f_mobile_number)
            if user_instance.bvn:
                bvn_enquiry = BankingApi.bvn_enquiry(user_instance.bvn)
                if bvn_enquiry is None:
                    raise serializers.ValidationError(
                        "BVN verification service is down at the moment. Try again later")
                # Check that the number in the BVN details is the same with what the user registered with

                if f_mobile_number not in bvn_enquiry['data']['phoneNo']:
                    raise serializers.ValidationError(
                        "The provided phone number doesnt match BVN details")

            return mobile_number

        except phonenumbers.phonenumberutil.NumberParseException:
            raise serializers.ValidationError(
                f"{mobile_number} is not a valid mobile number.")

    def validate_profile_image(self, profile_image):
        file_data = profile_image
        media_meta = file_data.split(',')[0]
        media_ext = media_meta.replace(
            "data:image/", "").replace(";base64", "")
        media_name = 'tudo-headers/' + str(uuid.uuid4().hex)
        data_formats = ('data:image/png;base64',
                        'data:image/jpeg;base64',
                        'data:image/jpg;base64')
        if not file_data.startswith(data_formats):
            raise serializers.ValidationError('Invalid image file Data')
        media_name = 'profile-images/' + str(uuid.uuid4().hex)
        file_name = f"{media_name}.{media_ext}"
        media_data = file_data.split(',')[1]
        media_meta = file_data.split(',')[0]
        str_len = len(file_data) - len(media_meta)
        img_size = (4 * math.ceil((str_len / 3)) * 0.5624896334383812) / 1000
        if img_size > 300:
            raise serializers.ValidationError(
                f"File can be upto 300kb heavy, {'{:.1f}'.format(img_size)}kb given.")
        return {"file_name": file_name, "media_data": media_data}

    def validate_birthday(self, birthday):
        user_instance = self.context.get('user')
        if user_instance.bvn:
            raise serializers.ValidationError(
                "You cannot update your Date of Birth number after adding your BVN")

        birth_date = birthday.strftime("%d-%b-%Y")

        # Compare DOB infotmation with saved BVN on update
        if not user_instance.bvn and 'bvn' in self.initial_data.keys():
            bvn_enquiry = BankingApi.bvn_enquiry(user_instance.bvn)
            if bvn_enquiry is None:
                raise serializers.ValidationError(
                    "BVN verification service is down at the moment. Try again later")
            # Todo - I don't know what I did with the back and forth on date parsing. would review later
            birth_date = datetime.strptime(birth_date, "%d-%b-%Y")
            bvn_dob = bvn_enquiry['data']['dateOfBirth']
            bvn_dob = datetime.strptime(bvn_dob, "%d-%b-%Y")
            if abs((birth_date - bvn_dob).days):
                raise serializers.ValidationError(
                    "The provided date of birth doesn't match the BVN details")

        return birthday

    def validate_bvn(self, bvn):
        user_instance = self.context.get('user')
        if user_instance.bvn:
            raise serializers.ValidationError("BVN has already been set")

        if not bvn.isdigit():
            raise serializers.ValidationError("BVN should contain only numbers.")

        bvn_enquiry = BankingApi.bvn_enquiry(bvn)
        if bvn_enquiry is None:
            raise serializers.ValidationError(
                "BVN validation failed. Validation service is down!")

        setattr(self, 'bvn_enquiry_result', bvn_enquiry)
        return bvn

    def update(self, instance, validated_data):
        if bool(validated_data) is False:
            return instance

        instance.first_name = validated_data.get("first_name", instance.first_name)
        instance.last_name = validated_data.get("last_name", instance.last_name)
        instance.birthday = validated_data.get("birthday", instance.birthday)
        instance.gender = validated_data.get("gender", instance.gender)
        instance.mobile_number = validated_data.get(
            "mobile_number", instance.mobile_number)
        if validated_data.get("profile_image"):
            media_data = validated_data.get("profile_image").get('media_data')
            file_name = validated_data.get("profile_image").get('file_name')
            instance.profile_image = MediaHandler.upload_raw(media_data, file_name)
        if validated_data.get("bvn"):
            if hasattr(self, 'formated_mobile_number'):
                mobile_number = self.formated_mobile_number
                bvn_enquiry_result = self.bvn_enquiry_result
                # Check that the number in the BVN details is the same with what the user registered with
                if mobile_number not in bvn_enquiry_result['data']['phoneNo']:
                    raise serializers.ValidationError(
                        {"errors": {"mobile_number": ["The provided phone number doesnt match BVN details"]}})

            if instance.birthday is None:
                raise serializers.ValidationError({"errors": {"birthday": [
                    "BVN validation failed. You haven't added your date of birth"]}})

            if instance.mobile_number is None:
                raise serializers.ValidationError({"errors": {"mobile_number": [
                    "BVN validation failed. You haven't added your phone number"]}})

            if validated_data.get("birthday"):
                birth_date = validated_data.get("birthday")
                birth_date = datetime(birth_date.year, birth_date.month, birth_date.day)
                bvn_dob = self.bvn_enquiry_result['data']['dateOfBirth']
                bvn_dob = datetime.strptime(bvn_dob, "%d-%b-%Y")

                # If the absolute difference between dates is truthy, then dates are different
                if abs((birth_date - bvn_dob).days):
                    raise serializers.ValidationError(
                        {"errors": {"birthday": ["The provided date of birth doesn't match the BVN details"]}})
            instance.bvn = validated_data.get("bvn")

        password = validated_data.get("password")
        if password:
            instance.set_password(password)
        instance.save()

        return instance


class PersonalProfileUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    password = serializers.CharField(required=False)
    profile_image = serializers.CharField(required=False)
    birthday = serializers.CharField(required=False)
    gender = serializers.ChoiceField(choices=['male', 'female'], required=False)
    mobile_number = serializers.CharField(required=False)

    def validate_first_name(self, first_name):
        pass

    def validate_last_name(self, last_name):
        pass

    def validate_password(self, password):
        pass

    def validate_profile_image(self, profile_image):
        pass

    def validate_birthday(self, birthday):
        pass

    def validate_gender(self, gender):
        pass

    def validate_mobile_number(self, mobile_number):
        pass


class DebitCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = DebitCard
        exclude = ['user', 'state']

    def validate(self, data):
        user = self.context['request'].user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]
        card_info = {key: value.strip() if isinstance(value, str) else value
                     for key, value in data.items()}
        validate_user = ValidateUser()
        is_valid_card = validate_user.is_valid_card(**card_info)
        if not is_valid_card:
            raise serializers.ValidationError(
                {'errors': validate_user.error_list})

        debit_card = DebitCard.objects.filter(first_six=card_info['first_six'],
                                              last_four=card_info['last_four'],
                                              card_bank=card_info['card_bank'],
                                              **field_opts)

        if debit_card:
            return debit_card[0]

        return DebitCard.objects.create(**card_info, **field_opts)


class BankDetailsSerializer(serializers.ModelSerializer):

    class Meta:
        model = BankAccount
        fields = ["id", "bank_code", "account_number",
                  "bank_name", "account_name"]
        extra_kwargs = {'bank_name': {'required': False},
                        'account_name': {'required': False}}

    def validate(self, validated_data):
        account_details = (
            re.sub('[^0-9]', '', validated_data['account_number'].strip()),
            re.sub('[^0-9]', '', validated_data['bank_code'].strip()))

        user = self.context['request'].user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]

        bank = BankAccount.objects.filter(
            account_number=account_details[0],
            bank_code=account_details[1], **field_opts)

        if bank:
            raise serializers.ValidationError(
                {"account_detail": "Already added this bank account"})

        bank_response = ValidateUser().validate_bank_details(*account_details)

        if not bank_response.get('is_resolved'):
            raise serializers.ValidationError(
                {"account_detail": "We could not resolve this account information"})

        bank_name = ValidateUser().resolve_bank_name(account_details[1])

        if not bank_name:
            raise serializers.ValidationError(
                {"bank_name": "cannot resolve bank name"})

        account_name = bank_response['account_name']

        return BankAccount.objects.create(bank_code=account_details[1],
                                          account_number=account_details[0],
                                          account_name=account_name,
                                          bank_name=bank_name,
                                          **field_opts)

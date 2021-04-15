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


class RegisterBusinessSerializer(serializers.ModelSerializer):
    mobile_number = serializers.CharField(
        required=True, error_messages={'required': "Please enter a valid phone number"})
    first_name = serializers.CharField(required=False, default=None)
    last_name = serializers.CharField(required=False, default=None)
    country = serializers.CharField(min_length=2, max_length=2)

    class Meta:
        model = Business
        fields = ["id", "first_name", "last_name", "business_name", "address",
                  "mobile_number", "description", "email", "password",
                  "invite_code", "is_active", "country",
                  "recovery_mobile_number", "recovery_email", "is_registered",
                  "currency", "sector", "services"]

        extra_kwargs = {
            "password": {"write_only": True},
            "invite_code": {"read_only": True}
        }

    def validate_email(self, email):
        business = Business.objects.filter(email=email.lower()).first() or \
            User.objects.filter(email=email.lower()).first()

        if business:
            raise serializers.ValidationError(
                'A user has registered with this email address')

        return email

    def validate_mobile_number(self, mobile_number):
        try:
            phone_number = phonenumbers.parse(mobile_number, None)
            if phonenumbers.is_valid_number(phone_number) is False:
                raise serializers.ValidationError(
                    f"{mobile_number} is not a valid mobile number")

            mobile_number = phonenumbers.format_number(
                phone_number, phonenumbers.PhoneNumberFormat.E164)

            user = Business.objects.filter(mobile_number=mobile_number).first()

            if user:
                raise serializers.ValidationError(
                    f"{mobile_number} has been used by another user")

            return mobile_number

        except phonenumbers.phonenumberutil.NumberParseException:
            raise serializers.ValidationError(
                f"{mobile_number} is not a valid mobile number.")

    def validate(self, data):
        validated_data = ValidateBusiness().validate_business_fields(**data)

        if isinstance(validated_data, list):
            raise serializers.ValidationError({"errors": validated_data})

        return validated_data

    def create(self, validated_data):
        business = Business.objects.create_business(**validated_data)
        business.invite_code = create_invite_code()
        business.set_password(validated_data['password'])
        business.save()
        return business


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


class BusinessUserProfileSerializer(serializers.ModelSerializer):
    account_type = serializers.SerializerMethodField()

    class Meta:
        model = Business
        extra_kwargs = {"password": {"write_only": True}}
        fields = "__all__"

    def get_account_type(self, obj):
        return 'business'

    def update(self, instance, validated_data):

        data = update_business_profile(validated_data, instance.bvn)
        if isinstance(data, list):
            raise serializers.ValidationError({"errors": data})
        password = data.get("password")
        instance.first_name = data.get("first_name", instance.first_name)
        instance.last_name = data.get("last_name", instance.last_name)
        instance.mobile_number = data.get(
            "mobile_number", instance.mobile_number)
        if validated_data.get("profile_image"):
            file_data = validated_data.get('profile_image')
            media_meta = file_data.split(',')[0]
            media_ext = media_meta.replace(
                "data:image/", "").replace(";base64", "")
            media_name = 'tudo-headers/' + str(uuid.uuid4().hex)
            data_formats = ('data:image/png;base64',
                            'data:image/jpeg;base64',
                            'data:image/jpg;base64')
            if not file_data.startswith(data_formats):
                raise serializers.ValidationError(
                    {"errors": {"profile_image": {'Invalid image file Data'}}})
            media_name = 'profile-images/' + str(uuid.uuid4().hex)
            file_name = f"{media_name}.{media_ext}"
            media_data = file_data.split(',')[1]
            media_meta = file_data.split(',')[0]
            str_len = len(file_data) - len(media_meta)
            img_size = (4 * math.ceil((str_len / 3)) * 0.5624896334383812) / 1000
            if img_size > 300:
                raise serializers.ValidationError(
                    {"errors": {"image_data": f"File can be upto 200kb heavy, {'{:.1f}'.format(img_size)}kb given."}})  # noqa
            url = MediaHandler.upload_raw(media_data, file_name)
            instance.profile_image = url
        instance.color_scheme = data.get("color_scheme", instance.color_scheme)
        instance.bvn = data.get("bvn", instance.bvn)
        instance.business_name = data.get(
            "business_name", instance.business_name)
        instance.address = data.get("address", instance.address)
        instance.description = data.get("description", instance.description)
        instance.country = data.get("country", instance.country)
        instance.is_registered = data.get(
            "is_registered", instance.is_registered)
        instance.currency = data.get("currency", instance.currency)
        instance.recovery_mobile_number = data.get(
            "recovery_mobile_number", instance.recovery_mobile_number)
        instance.services = data.get("services", instance.services)
        instance.recovery_email = data.get(
            "recovery_email", instance.recovery_email)
        instance.sector = data.get("sector", instance.sector)
        instance.background_color = data.get(
            "background_color", instance.background_color)
        instance.updated_at = datetime.now()
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class NextOfKinSerializer(serializers.ModelSerializer):
    """ Serializer class for Next of Kin """

    class Meta:
        model = NextOfKin
        fields = ("id", "first_name", "last_name", "email", "relationship",
                  "mobile_number", "address")
        extra_kwargs = {
            'mobile_number': {'validators': [validate_mobile_number]},
            'first_name': {'validators': [validate_name]},
            'last_name': {'validators': [validate_name]},
            'address': {'validators': [validate_address]}
        }


class UserKYCSerializer(serializers.ModelSerializer):
    """ Serializer class for user KYC """
    image_data = serializers.CharField(write_only=True)
    image_extension = serializers.ChoiceField(
        choices=['png', 'jpeg', 'jpg'], write_only=True)

    class Meta:
        model = UserKYC
        fields = ["id", "country_residence", "identity_card_url",
                    "image_data", "image_extension", "state_residence",
                    "residential_address"]
        extra_kwargs = {
            "identity_card_url": {"read_only": True}
        }

    def create(self, validated_data):
        file_data = validated_data.get('image_data')
        media_ext = validated_data.get('image_extension')
        media_name = 'user-kyc/' + str(uuid.uuid4().hex)
        file_name = f"{media_name}.{media_ext}"
        media_data = file_data.split(',')[1]
        media_meta = file_data.split(',')[0]
        str_len = len(file_data) - len(media_meta)
        img_size = (4 * math.ceil((str_len / 3)) * 0.5624896334383812) / 1000
        if img_size > 200:
            raise serializers.ValidationError(
                {"error": {"image_data": [f"File can be upto 200kb heavy, {'{:.1f}'.format(img_size)}kb given."]}})  # noqa
        url = MediaHandler.upload_raw(media_data, file_name)
        data = dict(identity_card_url=url,
                    country_residence=validated_data['country_residence'],
                    state_residence=validated_data['state_residence'],
                    residential_address=validated_data['residential_address'],
                    **self.context['user']
                    )
        return UserKYC.objects.create(**data)

    def update(self, instance, validated_data):
        file_data = validated_data.get('image_data')
        media_ext = validated_data.get('image_extension')
        if file_data and media_ext:
            media_name = 'user-kyc/' + str(uuid.uuid4().hex)
            file_name = f"{media_name}.{media_ext}"
            media_data = file_data.split(',')[1]
            media_meta = file_data.split(',')[0]
            str_len = len(file_data) - len(media_meta)
            img_size = (4 * math.ceil((str_len / 3)) * 0.5624896334383812) / 1000
            if img_size > 100:
                raise serializers.ValidationError(
                    {"error": {"image_data": [f"File can be upto 200kb heavy, {'{:.1f}'.format(img_size)}kb given."]}})  # noqa
            url = MediaHandler.upload_raw(media_data, file_name)
            instance.identity_card_url = url
        instance.country_residence = validated_data.get(
            'country_residence', instance.country_residence)
        instance.state_residence = validated_data.get(
            'state_residence', instance.state_residence)
        instance.residential_address = validated_data.get(
            'residential_address', instance.residential_address)
        instance.save()
        return instance


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


class TudoDictSerializer(serializers.DictField):
    goal_name = serializers.CharField(),
    amount = serializers.IntegerField()
    tudo_duration = serializers.ChoiceField(
        choices=(("7", "7 Days"), ("30", "30 Days"),
                 ("60", "60 Days"), ("90", "90 Days")))
    is_visible = serializers.BooleanField(read_only=True, default=True)


class TudoSerializer(serializers.Serializer):
    tudos = serializers.ListField(child=TudoDictSerializer())
    collection_code = serializers.CharField(required=False, default=None)

    def validate(self, data):
        my_tudos = []
        for tudo in data['tudos']:
            my_tudos.append({
                'id': tudo.id,
                'currency': tudo.currency,
                'goal_name': tudo.goal_name,
                'category': dict(id=tudo.category.id, name=tudo.category.category),
                'target_amount': tudo.amount,
                'generated_amount': tudo.amount_generated,
                'tudo_duration': tudo.tudo_duration,
                'completion_date': tudo.completion_date,
                'status': str(tudo.status),
                'user_id': tudo.user_id or tudo.business_id,
                'is_visible': tudo.is_visible,
                'share_code': tudo.share_code,
                'goal_description': tudo.goal_description,
                'tudo_media': tudo.tudo_media,
                'collection_code': tudo.collection_code,
            })
        return dict(tudos=my_tudos, collection_code=self.collection_code)

    def validate_tudos(self, tudos_data):
        tudo_owner = self.context['request'].user
        business_account = isinstance(tudo_owner, Business)
        validate_tudo = ValidateTudo()

        fields_check_result = validate_tudo.check_required_fields(
            tudos_data, fields=REQUIRED_PERSONAL_TUDO_FIELDS)

        if business_account:
            fields_check_result = validate_tudo.check_required_fields(
                tudos_data, fields=REQUIRED_BUSINESS_TUDO_FIELDS)

        if isinstance(fields_check_result, list):
            raise serializers.ValidationError({"errors": fields_check_result})

        for tudo in tudos_data:
            if business_account:
                validated_data = validate_tudo.validate_business_tudo_fields(
                    **tudo)
            else:
                validated_data = validate_tudo.validate_tudo_fields(**tudo)

        if isinstance(validated_data, list):
            raise serializers.ValidationError({"errors": validated_data})

        available_days = {
            '7 days': 7,
            '30 days': 30,
            '60 days': 60,
            '90 days': 90,
            validated_data['tudo_duration']: int(
                validated_data['tudo_duration'][:2])
        }

        is_multiple_tudo = len(tudos_data) > 1
        if is_multiple_tudo:
            self.collection_code = uuid.uuid4().hex[:16]
        else:
            self.collection_code = None

        created_tudos = []
        for tudo in tudos_data:
            total_days = available_days[
                validated_data['tudo_duration'].lower()]

            completion_date = timedelta(
                days=total_days) + datetime.now(tz=timezone.utc)

            # Todo: Abstract this to a Generator Method
            all_tudo_shared_codes = retrieve_from_redis(
                'all_tudo_shared_codes')

            if not all_tudo_shared_codes:
                all_tudo_shared_codes = Tudo.objects.values_list(
                    'share_code', flat=True)
                save_in_redis('all_tudo_shared_codes',
                              all_tudo_shared_codes, 60 * 5)

            generated_share_code = ''.join(random.choices(
                string.ascii_letters + string.digits, k=12)).upper()

            while generated_share_code in all_tudo_shared_codes:
                generated_share_code = ''.join(
                    random.choices(string.ascii_letters + string.digits,
                                   k=12)).upper()
                all_tudo_shared_codes.append(generated_share_code)
                save_in_redis('all_tudo_shared_codes',
                              all_tudo_shared_codes, 60 * 5)

            goal_data = {
                **tudo,
                "collection_code": self.collection_code,
                "goal_name": tudo['goal_name'],
                "amount": tudo['amount'],
                "tudo_duration": validated_data['tudo_duration'],
                "currency": tudo.get("currency", "NGN"),
                "category_id": tudo['category_id'],
                "tudo_media": validated_data['tudo_media']

            }

            if business_account:
                created_tudos.append(
                    Tudo.objects.create(**goal_data, completion_date=completion_date,
                                        business_id=tudo_owner.id, status="running",
                                        share_code=generated_share_code))
            else:
                created_tudos.append(
                    Tudo.objects.create(**goal_data, completion_date=completion_date,
                                        user_id=tudo_owner.id, status="running",
                                        share_code=generated_share_code))

        return created_tudos


class TudoModelSerializer(serializers.ModelSerializer):
    state = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    contributions = serializers.SerializerMethodField()
    contributions_percentage = serializers.SerializerMethodField()
    amount_withdrawable = serializers.SerializerMethodField()
    likes = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()
    files = serializers.SerializerMethodField()
    tudo_media = serializers.CharField()

    class Meta:
        model = Tudo
        fields = "__all__"

        extra_kwargs = {
            'goal_name': {'validators': [validate_goal_name]}
        }

    def get_state(self, obj):
        return str(obj.state)

    def get_status(self, obj):
        return str(obj.status)

    def get_user(self, obj):
        user = obj.user or obj.business
        acct_type = parse_user_type(user)
        return dict(
            id=user.id,
            first_name=user.first_name if acct_type == 'personal' else user.business_name,  # noqa
            last_name=user.last_name if acct_type == 'personal' else '',
            profile_image=user.profile_image)

    def get_category(self, obj):
        return dict(
            id=obj.category.id,
            category_name=obj.category.category)

    def get_contributions(self, obj):
        contributions = TudoContribution.objects.filter(
            tudo_code=obj,
            contribution_type=str(TudoContributionType.USERCONTRIBUTION),
            status=TransactionStatus.SUCCESS.value)

        return dict(
            contributors=[
                dict(name=contributor.contributor_name.title(),
                     amount_contributed=contributor.amount)
                for contributor in contributions.order_by('-amount')],
            contributions_count=contributions.count()
        )

    def get_contributions_percentage(self, obj):
        computed_percentage = float("{:.2f}".format(
            (obj.amount_generated / obj.amount) * 100))
        return computed_percentage

    def get_amount_withdrawable(self, obj):
        return obj.amount_generated - obj.amount_withdrawn

    def get_likes(self, obj):
        user = self.context.get('user')
        owner = obj.user or obj.business
        likes = TudoLikes.objects.filter(
            tudo=obj, like_status='LIKED').values_list('user', 'business')
        is_authenticated = self.context.get('is_authenticated', None)
        users_who_liked = list(itertools.chain.from_iterable(list(likes)))
        data = {
            "likes_count": len(likes),
            "has_owner_liked": owner.id in users_who_liked,
            "is_auth_user_liked": user.id in users_who_liked
            if is_authenticated else False
        }
        return data

    def get_comments(self, obj):
        comments = TudoComments.objects.filter(tudo=obj)
        return {
            "comments_count": comments.count(),
        }

    def get_files(self, obj):
        tudo_media = TudoMedia.objects.filter(tudo__id=obj.id).all()
        return [dict(url=media.url, id=media.id) for media in tudo_media]

    def validate(self, data):
        completion_date = data.get("completion_date")
        goal_completion_date = self.instance.completion_date
        max_allowed_date = goal_completion_date + relativedelta(months=3)
        if completion_date and (completion_date < goal_completion_date or completion_date > max_allowed_date):
            raise exceptions.ValidationError(
                {'completion_date': 'You cannot set tudo to an earlier date or by extend more than 3 months'})
        return data

    def update(self, instance, validated_data):
        validate_tudo = ValidateTudo()
        user_type = self.context['user_type']
        if user_type == 'business':
            valid_data = validate_tudo.validate_business_tudo_fields(
                partial=True, instance=instance, **validated_data)
            if isinstance(valid_data, list):
                raise serializers.ValidationError({"errors": valid_data})
        else:
            valid_data = validate_tudo.validate_tudo_fields(
                partial=True, instance=instance, **validated_data)
            if isinstance(valid_data, list):
                raise serializers.ValidationError({"errors": valid_data})
        del valid_data['tudo_category_id']
        instance.update(**valid_data)
        return instance


class TudoContributionSerializer(serializers.ModelSerializer):
    scope = serializers.ChoiceField(
        choices=['local', 'international'], required=False, default='international')

    class Meta:
        model = TudoContribution
        fields = ['contributor_email', 'scope',
                  'contributor_name', 'amount', 'tudo_code']
        extra_kwargs = {
            'contributor_name': {'required': False,
                                 'default': 'Anonymous Contributor'},
            'contributor_email': {'required': False,
                                  'default': f"{generate_id()}@mytudo.com"},
        }

    def validate(self, data):
        currency = data['tudo_code'].currency
        if currency != 'NGN':
            if data['amount'] > 100000 or data['amount'] < 100:
                raise serializers.ValidationError(
                    {'amount':
                     f"Only amounts from {currency}100 to {currency}1000 are allowed"})
        elif data['amount'] < 10000 or data['amount'] > 999999900:
            raise serializers.ValidationError(
                {'amount':
                 "Contribution should be within NGN100 and NGN9.9m"})
        return data


class TudoTransactionSerializer(serializers.ModelSerializer):
    contributed_at = serializers.SerializerMethodField('get_updated_at')

    class Meta:
        model = TudoContribution
        fields = ['contributor_name', 'amount', 'contributed_at', 'reference']

    def get_updated_at(self, obj):
        return obj.updated_at


class TudoTopUpSerializer(serializers.Serializer):
    topup_amount = serializers.IntegerField(
        min_value=10000, max_value=999999900,
        error_messages={
            'min_value': 'Ensure amount is between N100 and N9.9m',
            'max_value': 'Ensure amount is not greater than and N9.9m'}
    )
    tudo_id = serializers.CharField()
    card_id = serializers.CharField(default=None)

    def validate_card_id(self, card_id):
        user = self.context['request'].user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]
        if card_id is None:
            return None
        card = DebitCard.objects.filter(
            id=card_id, **field_opts).first()
        if not card:
            raise serializers.ValidationError(
                detail='card not found')
        return card.id

    def validate_tudo_id(self, tudo_id):
        user = self.context['request'].user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]
        tudo = Tudo.objects.filter(
            id=tudo_id, **field_opts).first()
        if not tudo:
            raise serializers.ValidationError(
                detail='tudo not found')
        if tudo.status == 'completed':
            raise serializers.ValidationError(
                detail='tudo goal has been completed')
        if tudo.status == 'paid':
            raise serializers.ValidationError(
                detail='Tudo already paid')
        return tudo_id


class TudoFeedSerializer(serializers.Serializer):
    phone_numbers = serializers.ListField(
        child=serializers.CharField(), min_length=1, error_messages={
            'min_length': 'Should contain at least 1 phone number'
        })

    def validate_phone_numbers(self, phone_numbers):
        return [numbers[-10:] for numbers in phone_numbers]


class TrendingTudoSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    contributions_percentage = serializers.SerializerMethodField()
    likes = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()

    class Meta:
        model = Tudo
        fields = ['id', 'tudo_media', 'category', 'goal_name',
                  'goal_description', 'likes', 'comments', 'currency',
                  'amount_generated', 'amount', 'contributions_percentage',
                  'share_code', 'user']

    def get_user(self, obj):
        user = obj.user or obj.business
        acct_type = parse_user_type(user)
        return dict(
            id=user.id,
            first_name=user.first_name if acct_type == 'personal' else user.business_name,
            last_name=user.last_name if acct_type == 'personal' else '',
            profile_image=user.profile_image)

    def get_category(self, obj):
        return dict(
            id=obj.category.id,
            category_name=obj.category.category)

    def get_contributions_percentage(self, obj):
        computed_percentage = float("{:.2f}".format(
            (obj.amount_generated / obj.amount) * 100))
        return computed_percentage

    def get_likes(self, obj):
        user = self.context.get('user')
        owner = obj.user or obj.business
        likes = TudoLikes.objects.filter(
            tudo=obj, like_status='LIKED').values_list('user', 'business')
        is_authenticated = self.context.get('is_authenticated', None)
        users_who_liked = list(itertools.chain.from_iterable(list(likes)))
        data = {
            "likes_count": len(likes),
            "has_owner_liked": owner.id in users_who_liked,
            "is_auth_user_liked": user.id in users_who_liked if is_authenticated else False
        }
        return data

    def get_comments(self, obj):
        comments = TudoComments.objects.filter(tudo=obj).count()
        return {
            "comments_count": comments,
        }


class TudoContactFeedSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    contributions = serializers.SerializerMethodField()
    contributions_percentage = serializers.SerializerMethodField()

    class Meta:
        model = Tudo
        fields = ("id", "goal_name", "contributions",
                  "contributions_percentage", "amount_generated",
                  "amount", "start_date", "share_code",
                  "user", "goal_description")

    def get_user(self, obj):
        user = obj.user or obj.business
        acct_type = parse_user_type(user)
        return dict(
            id=user.id,
            first_name=user.first_name if acct_type == 'personal' else user.business_name,  # noqa
            last_name=user.last_name if acct_type == 'personal' else '',
            profile_image=user.profile_image)

    def get_contributions(self, obj):
        return TudoContribution.objects.filter(tudo_code=obj,
                                                status=TransactionStatus.SUCCESS.value).count()  # noqa

    def get_contributions_percentage(self, obj):
        computed_percentage = float("{:.2f}".format(
            (obj.amount_generated / obj.amount) * 100))
        return computed_percentage


class WithdrawTudoSerializer(serializers.Serializer):
    bank_account_id = serializers.CharField()
    tudo_id = serializers.CharField()

    def validate_bank_account_id(self, bank_account_id):
        user = self.context['user']
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[self.context['user_type']]
        account = BankAccount.objects.filter(
            id=bank_account_id, **field_opts).first()
        if not account:
            raise serializers.ValidationError(
                'Bank account not found for user')
        return bank_account_id

    def validate_tudo_id(self, tudo_id):
        user = self.context['user']
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[self.context['user_type']]
        tudo = Tudo.objects.filter(id=tudo_id, **field_opts).first()
        if not tudo:
            raise serializers.ValidationError('Tudo not found for user')
        return tudo_id

    def validate(self, data):
        user = self.context['user']
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[self.context['user_type']]
        tudo = Tudo.objects.filter(id=data['tudo_id'], **field_opts).first()
        if tudo.status == TudoStatus.paid.value:
            raise serializers.ValidationError({'tudo': 'Tudo already paid'})
        # elif tudo.status == str(TudoStatus.running.value):
        #     raise serializers.ValidationError(
        #         {'tudo': "Can't withdraw running Tudo"})
        elif tudo.status == TudoStatus.processing_withdrawal.value:
            raise serializers.ValidationError({'tudo': 'Withdrawal in progress'})
        return data


class NotificationSerializer(serializers.ModelSerializer):
    meta = serializers.SerializerMethodField()
    triggered_by = serializers.SerializerMethodField()
    reaction = serializers.ChoiceField(
        choices=[('accept', 'accept'), ('decline', 'decline')], required=False)

    class Meta:
        model = Notification
        fields = ["id", "summary", "status", "notification_text", "user",
                  "triggered_by", "created_at", "updated_at", "entity_id", 'entity',
                  "notification_type", "is_reactable", 'reaction_status', 'reaction',
                  "meta"]
        extra_kwargs = {
            "status": {
                "required": False,
            }
        }

    def get_meta(self, obj):
        if obj.entity == "GROUPTUDO" and obj.notification_type == "WITHDRAWAL_REQUEST":
            withdrawal_request = GroupTudoWithdrawal.objects.filter(
                group_tudo_id=obj.entity_id).first()
            return dict(
                withdrawal_service_charge=withdrawal_request.service_charge,
                withdrawal_currency=withdrawal_request.currency,
                withdrawal_reason=withdrawal_request.withdrawal_reason,
                withdrawal_amount=withdrawal_request.withdrawal_amount) \
                    if withdrawal_request else None
        return None

    def get_triggered_by(self, obj):
        if obj.triggered_by:
            return dict(
                id=obj.triggered_by.id,
                first_name=obj.triggered_by.first_name,
                profile_image=obj.triggered_by.profile_image)
        return dict(
            first_name=obj.actor_name or "Anonymous",
            profile_image=DEFAULT_AVATAR_URL)

    def validate_reaction(self, reaction):
        reaction = reaction if reaction else None
        if reaction:
            if not self.instance.is_reactable:
                raise serializers.ValidationError(
                    'Notification is not reactable')
            return reaction
        return reaction

    def update(self, instance, validated_data):
        error_list = []
        status = validated_data.get("status").lower(
        ) if validated_data.get("status") else None
        if status:
            if status not in ["read", "unread"]:
                raise serializers.ValidationError(
                    {"errors": "Notification status can only be updated to 'read' or 'unread'"})  # noqa

            if status == "read":
                instance.status = NotificationStatus.read.value
            else:
                instance.status = NotificationStatus.unread.value
            instance.save()

        reaction = validated_data.get(
            "reaction") if validated_data.get("reaction") else None
        if reaction:
            if reaction == 'accept':
                # Invite Notifications Request ACCEPTANCE
                if instance.notification_type == NOTIFICATION_TYPE[1][0]:
                    instance.is_reactable = False
                    instance.status = NotificationStatus.read.value
                    instance.reaction_status = INVITE_STATUS[1][0]
                    GroupTudoMembers.objects.filter(
                        member=self.context['user']).update(
                            invite_status=INVITE_STATUS[1][0])
                    group_tudo = GroupTudo.objects.get(id=instance.entity_id)
                    # members_not_reacted = GroupTudoMembers.objects.filter(
                    #     group_tudo=group_tudo, invite_status=INVITE_STATUS[0][0]
                    # ).exclude(member=self.context['user']).values_list(
                    #     'member__first_name', flat=True)

                    # Invalidate invitation email accept button
                    delete_from_redis(
                        f"notification-{group_tudo.id}-{self.context['user'].email}")

                    # Todo - update acceptance email if there'd be any.
                    # details = {
                    #     'goal_name': group_tudo.name,
                    #     'members_left': list(members_not_reacted)
                    # }
                    # send_grouped_tudo_acceptance_email.delay(
                    #     invitee_first_name=self.context['user'].first_name,
                    #     user_first_name=instance.triggered_by.first_name,
                    #     user_email=instance.triggered_by.email,
                    #     details=details
                    # )

                # Process Withdrawal Request ACCEPTANCE
                if instance.notification_type == NOTIFICATION_TYPE[2][0]:
                    # TODO - Grab details from goal withdrawal request
                    w_request = GroupTudoWithdrawal.objects.filter(
                        withdrawal_status=WITHDRAWAL_STATUS[0][0],
                        approved_by=self.context['user'],
                        group_tudo_id=instance.entity_id).first()
                    # TODO - Call Bank API if the currency if NGN and make withdrawal
                    if w_request and w_request.currency == 'NGN':
                        bank_acct_id = w_request.withdrawal_entity_id
                        requester_id = w_request.requested_by_id
                        approved_id = w_request.approved_by_id
                        if w_request.withdrawal_entity_name == 'BANK':
                            requester_bank = BankAccount.objects.filter(
                                user_id=requester_id, id=bank_acct_id).first()
                            group_tudo = GroupTudo.objects.get(id=instance.entity_id)
                            if requester_bank:
                                # Todo - Remove Service Charges and Call Core Banking
                                amt_to_withdraw = w_request.withdrawal_amount
                                service_charge = w_request.service_charge
                                account_number = requester_bank.account_number
                                bank_code = requester_bank.bank_code
                                reference = w_request.reference
                                transfer_response = BankingApi.transfer_money(
                                    amount=amt_to_withdraw / 100,  # Converts to Naira
                                    account_number=account_number,
                                    bank_code=bank_code,
                                    transfer_type="inter",
                                    transaction_reference=reference,
                                    remark=f"{group_tudo.name} Group Goal Withdrawal",
                                )
                                if transfer_response.get("status") is True:
                                    # TODO - Update update goal amount withdrawn
                                    group_tudo.amount_withdrawn = F(
                                        'amount_withdrawn') + amt_to_withdraw + service_charge
                                    group_tudo = group_tudo.save()
                                    instance.is_reactable = False
                                    instance.status = NotificationStatus.read.value
                                    instance.reaction_status = INVITE_STATUS[1][0]
                                    w_request.withdrawal_status = WITHDRAWAL_STATUS[1][0]  # noqa
                                    w_request.withdrawal_date = timezone.now()
                                    w_request.save()
                                    # TODO - inform others of the approval
                                    all_members = GroupTudoMembers.objects.filter(
                                        group_tudo=group_tudo,
                                        invite_status="ACCEPTED").select_related('member')
                                    members_to_inform = all_members.exclude(
                                        member_id=approved_id)
                                    members_to_inform_instance_list = []
                                    for member in members_to_inform:
                                        members_to_inform_instance_list.append(
                                            Notification(**{
                                                "user": member.member,
                                                "triggered_by_id": approved_id,
                                                "notification_type": NOTIFICATION_TYPE[2][0],
                                                "entity_id": group_tudo.id,
                                                "entity": NOTIFICATION_ENTITY[2][0],
                                                "summary": "Group Goal Withdrawal Approval",
                                                "notification_text": f"{instance.user.first_name} has APPROVED the withdrawal request on the {group_tudo.name} goal",  # noqa
                                                "actor_name": None,
                                                "is_reactable": False,
                                                "reaction_status": INVITE_STATUS[0][0]
                                            })
                                        )
                                    Notification.objects.bulk_create(
                                        members_to_inform_instance_list)
                                    # Todo - Set Group Status to PAID(determin the terms first)
                                else:
                                    error_list.append("Payment Gateway Error")
                            else:
                                # TODO - User withdrwal account not found
                                error_list.append(
                                    "Could not resolve requester's bank details")
                        elif w_request.withdrwal_entity_name == 'WALLET':
                            raise NotImplementedError()
                            # TODO - Find users wallet and move the funds there
                    else:
                        # TODO - withdrwal request wasnt found or currency isnt NGN
                        error_list.append(
                            "Withdrawal request was not found or isn't a Naira request")

            if reaction == 'decline':
                if instance.notification_type == NOTIFICATION_TYPE[1][0]:
                    instance.is_reactable = False
                    instance.status = NotificationStatus.read.value
                    instance.reaction_status = INVITE_STATUS[2][0]
                    group_tudo = GroupTudo.objects.get(id=instance.entity_id)
                    group_tudo.member_count = F('member_count') - 1
                    group_tudo.save()
                    GroupTudoMembers.objects.filter(
                        member=self.context['user'],
                        group_tudo=group_tudo).delete()
                    # Deteting this to invalidate the invite details in cache
                    delete_from_redis(
                        f"notification-{group_tudo.id}-{self.context['user'].email}")

                # Process Withdrawal Request DECLINE
                if instance.notification_type == NOTIFICATION_TYPE[2][0]:
                    w_request = GroupTudoWithdrawal.objects.filter(
                        withdrawal_status=WITHDRAWAL_STATUS[0][0],
                        approved_by=self.context['user'],
                        group_tudo_id=instance.entity_id).first()
                    group_tudo = w_request.group_tudo
                    instance.is_reactable = False
                    instance.status = NotificationStatus.read.value
                    instance.reaction_status = INVITE_STATUS[2][0]
                    w_request.withdrawal_status = WITHDRAWAL_STATUS[2][0]
                    w_request.save()
                    approved_id = w_request.approved_by_id
                    # Todo - When a request is declined it
                    all_members = GroupTudoMembers.objects.filter(
                        group_tudo_id=instance.entity_id,
                        invite_status="ACCEPTED").select_related('member')
                    members_to_inform = all_members.exclude(member_id=approved_id)
                    members_to_inform_instance_list = []
                    for member in members_to_inform:
                        members_to_inform_instance_list.append(
                            Notification(**{
                                "user": member.member,
                                "triggered_by_id": approved_id,
                                "notification_type": NOTIFICATION_TYPE[2][0],
                                "entity_id": group_tudo.id,
                                "entity": NOTIFICATION_ENTITY[2][0],
                                "summary": "Group Goal Withdrawal Rejected",
                                "notification_text": f"{instance.user.first_name} has REJECTED the withdrawal request on the {group_tudo.name} goal",  # noqa
                                "actor_name": None,
                                "is_reactable": False,
                                "reaction_status": INVITE_STATUS[0][0]
                            })
                        )
                    Notification.objects.bulk_create(members_to_inform_instance_list)
                    # TODO - should send a mail to the user requester of the action
            instance.save()
        if error_list:
            raise serializers.ValidationError(dict(error=error_list))
        return instance


class TudoWithdrawTransactionSerializer(serializers.ModelSerializer):
    state = serializers.SerializerMethodField()

    class Meta:
        model = TudoWithdrawal
        fields = "__all__"

    def get_state(self, obj):
        return str(obj.state)


class ApplicationSupportSerializer(serializers.Serializer):
    full_name = serializers.CharField(min_length=3, max_length=30, error_messages={
        'min_length': 'Fullname should have at least 3 characters',
        'max_length': 'Fullname should have at most 30 characters'})
    mobile_number = serializers.CharField(required=False, default=None)
    email = serializers.EmailField()
    subject = serializers.CharField(min_length=3, max_length=20, error_messages={
        'min_length': 'Subject should have at least 3 characters',
        'max_length': 'Subject should have at most 20 characters'})
    message = serializers.CharField(min_length=2, error_messages={
        'min_length': 'Message should have at least 2 characters'})

    def validate_mobile_number(self, mobile_number):
        user = self.context['user']
        is_authenticated = self.context['is_authenticated']
        if is_authenticated:
            return user.mobile_number or None
        if mobile_number:
            validate_mobile_number(mobile_number)
        return mobile_number

    def validate_email(self, email):
        user = self.context['user']
        is_authenticated = self.context['is_authenticated']
        if is_authenticated:
            return user.email
        return email

    def validate_full_name(self, full_name):
        user = self.context['user']
        is_authenticated = self.context['is_authenticated']
        if is_authenticated:
            return f"{user.first_name} {user.last_name}"
        return full_name


class TudoCommentSerializer(serializers.ModelSerializer):
    tudo_id = serializers.CharField(
        write_only=True, required=False, default=None)
    parent_id = serializers.CharField(
        write_only=True, required=False, default=None)
    user = serializers.SerializerMethodField()

    class Meta:
        model = TudoComments
        fields = ["id", "tudo_id", "parent_id", "user", "created_at",
                  "updated_at", "comment_text"]

    def validate(self, data):
        errors = []

        if data['tudo_id'] and data['parent_id']:
            raise serializers.ValidationError(
                dict(error="You can only reply to a tudo or a reply at once not both"))

        if data['tudo_id'] is not None:
            tudo = Tudo.objects.filter(pk=data['tudo_id']).first()
            if not tudo:
                errors.append({'tudo_id': ['This tudo goal does not exist']})

        if data['parent_id'] is not None:
            tudo_comment = TudoComments.objects.filter(
                pk=data['parent_id'], parent_id__isnull=True).first()
            if not tudo_comment:
                errors.append(
                    {'parent_id': ["This parent comment does not exist"]})

        if errors:
            raise serializers.ValidationError(dict(error=errors))

        return data

    def create(self, validated_data):
        return TudoComments.objects.create(
            comment_text=validated_data['comment_text'],
            tudo_id=validated_data['tudo_id'],
            parent_id=validated_data.get('parent_id', None), **self.context['user'])

    def get_user(self, obj):
        user = obj.user or obj.business
        acct_type = parse_user_type(user)
        return dict(
            id=user.id,
            first_name=user.first_name if acct_type == 'personal' else user.business_name,  # noqa
            last_name=user.last_name if acct_type == 'personal' else '',
            profile_image=user.profile_image)


class TudoLikesSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model = TudoLikes
        fields = ["id", "user"]

    def get_user(self, obj):
        user = obj.user or obj.business
        acct_type = parse_user_type(user)
        return dict(
            id=user.id,
            first_name=user.first_name if acct_type == 'personal' else user.business_name,  # noqa
            last_name=user.last_name if acct_type == 'personal' else '',
            profile_image=user.profile_image)


class TudoCommentListSerializer(serializers.ModelSerializer):
    replies = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()

    class Meta:
        model = TudoComments
        fields = ["id", "comment_text", "user",
                  "created_at", "updated_at", "replies"]

    def get_replies(self, comment):
        replies = self.Meta.model.objects.filter(parent_id=comment.id)

        def format_replies(instance):
            return {
                "id": instance.id,
                "comment_text": instance.comment_text,
                "user": dict(
                    id=instance.user.id if instance.user else instance.business.id,
                    first_name=instance.user.first_name if instance.user else instance.business.first_name,  # noqa
                    last_name=instance.user.last_name if instance.user else instance.business.last_name,  # noqa
                    profile_image=instance.user.profile_image if instance.user else instance.business.profile_image),  # noqa
                "created_at": instance.created_at,
                "updated_at": instance.updated_at,
            }

        return [format_replies(reply) for reply in replies]

    def get_user(self, obj):
        user = obj.user or obj.business
        acct_type = parse_user_type(user)
        return dict(
            id=user.id,
            first_name=user.first_name if acct_type == 'personal' else user.business_name,  # noqa
            last_name=user.last_name if acct_type == 'personal' else '',
            profile_image=user.profile_image)


class TudoMediaDictSerializer(serializers.Serializer):
    file_data = serializers.CharField(required=True)
    extension = serializers.ChoiceField(
        choices=['doc', 'docx', 'pdf', 'jpg', 'png', 'jpeg'])

    def validate(self, data):
        file_data = data.get('file_data')
        media_ext = data.get('extension')
        media_name = 'tudo-media/' + str(uuid.uuid4().hex)
        file_name = f"{media_name}.{media_ext}"
        media_data = file_data.split(',')[1]
        media_meta = file_data.split(',')[0]
        str_len = len(file_data) - len(media_meta)
        img_size = (4 * math.ceil((str_len / 3)) * 0.5624896334383812) / 1000
        return {"media_data": media_data, "file_name": file_name, "size": img_size}


class TudoMediaSerializer(serializers.Serializer):
    tudo_id = serializers.CharField(required=True)
    media = serializers.ListField(child=TudoMediaDictSerializer())

    def validate_tudo_id(self, tudo_id):
        tudo = Tudo.objects.filter(id=tudo_id, **self.context['user']).first()
        if tudo is None:
            raise serializers.ValidationError('Goal does not exist')
        return tudo_id

    def validate_media(self, media_list):
        errors = []
        for index, media_data in enumerate(media_list):
            if media_data['size'] > 1000:
                errors.append({index: "Media size cannot be greater then 1mb"})
        if errors:
            raise serializers.ValidationError(errors)
        return media_list

    def create(self, validated_data):
        media = validated_data.get('media')
        tudo_id = self.context.get('tudo_id')
        tudo = Tudo.objects.filter(id=tudo_id).first()
        media_details = []
        for data in media:
            url = f"https://{settings.SPACE_STORAGE_BUCKET_NAME}.{settings.SPACE_REGION}.digitaloceanspaces.com/{data['file_name']}"  # noqa
            tudo_media = TudoMedia(url=url, tudo=tudo)
            tudo_media.save()
            upload_tudo_media_to_bucket.delay(
                data['media_data'], data['file_name'], tudo_media.id)
            media_details.append({
                'created_at': tudo_media.created_at,
                'media_id': tudo_media.id,
                'media_url': tudo_media.url
            })
        return media_details


class TudoMediaModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = TudoMedia
        fields = "__all__"


class ReferralSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['first_name', 'email', 'profile_image']


class TudoTransactionsSerializer(serializers.Serializer):
    transaction_type = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()
    id = serializers.CharField()
    amount = serializers.IntegerField()

    def get_transaction_type(self, obj):
        if obj._meta.object_name == TudoWithdrawal._meta.object_name:
            return "Withdrawal"

        elif obj._meta.object_name == TudoContribution._meta.object_name:
            if obj.contribution_type == str(TudoContributionType.USERCONTRIBUTION):
                return "Contribution"
            elif obj.contribution_type == str(TudoContributionType.TOPUP):
                return "Top up"


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

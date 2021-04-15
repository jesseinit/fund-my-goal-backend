import re
import uuid
from datetime import datetime, timedelta
import math

import phonenumbers
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from rest_framework import exceptions
from rest_framework.serializers import ValidationError

from adminservice.models import TudoCategory
from savingservice.models import Plan
from userservice.models import DebitCard
from utils.constants import (BUSINESS_SECTORS, BUSINESS_SERVICES,
                             BUSINESS_SUPPORTED_COUNTRY,
                             BUSINESS_SUPPORTED_CURRENCIES, CURRENCIES)
from utils.helpers import BankingApi, MediaHandler, parse_user_type


class ValidateUser:
    def __init__(self):
        self.error_list = []

    def validate_user_fields(self, **kwargs):
        password = self.validate_password(kwargs.get('password'))
        first_name = self.validate_name(kwargs.get("first_name"), 'first_name')
        last_name = self.validate_name(kwargs.get('last_name'), 'last_name')

        if len(self.error_list):
            return self.error_list

        return {
            "password": password,
            "first_name": first_name,
            "last_name": last_name,
            **kwargs
        }

    def validate_email(self, email):
        email = email.strip().lower() if email is not None else None
        if email:
            if re.match(r'^[A-Za-z0-9\.\+_-]+@[A-Za-z0-9\._-]+\.[a-zA-Z]{2,5}$',
                        email) is None:
                self.error_list.append(
                    {f"{email}": "Please input a valid email"})
        return email

    def validate_mobile_number(self, mobile_number, field_name='mobile_number'):
        mobile_number = mobile_number.strip() if mobile_number is not None else None
        if mobile_number:
            if re.match(r'^\+[0-9]+$', mobile_number) is None:
                self.error_list.append(
                    {f"{field_name}": "Mobile Number must contain a valid country code" +
                     " and your mobile number, e.g +121449599806"})
                return None
        try:
            phone_number = phonenumbers.parse(mobile_number, None)
            if phonenumbers.is_valid_number(phone_number) is False:
                self.error_list.append(
                    {f"{field_name}": f"{phone_number} is not a valid mobile number"})
            mobile_number = phonenumbers.format_number(
                phone_number, phonenumbers.PhoneNumberFormat.E164)
            return mobile_number
        except phonenumbers.phonenumberutil.NumberParseException as e:
            self.error_list.append(
                {f"{field_name}":
                    f"{mobile_number} is not a valid\
                         mobile number. Valid number looks like +2348012345678"})

    def validate_password(self, password):
        password = password.strip()
        if re.match('(?=.{8,100})', password) is None:
            self.error_list.append(
                {"password": "password must have at least 8 characters"})
        return password

    def validate_name(self, name, field_name):
        if name is not None:
            if len(name.strip()) < 2:
                self.error_list.append({f"{field_name}": "{} \
                    must be two (2) and above characters".format(name)})
        name_regex = re.search(r'[^a-zA-Z\-]+', name)
        if name_regex is not None:
            self.error_list.append(
                {f"{field_name}": f"{name} can only contain alphabets and hyphens."})
        return name

    def validate_bank_details(self, account_number, bank_code):
        response = BankingApi.get_transfer_beneficiary(
            account_number=account_number, bank_code=bank_code)
        return response

    def resolve_bank_name(self, bank_code):
        bank_list = BankingApi.retrieve_bank_list()
        if not bank_list:
            return None
        bank_name = [bank_data['name']
                     for bank_data in bank_list
                     if int(bank_code) == int(bank_data['code'])]
        return bank_name[0] if bank_name else None

    def is_valid_card(self, **kwargs):
        """ Method to validate user card information """

        months_number_list = [int("{:02d}".format(i)) for i in range(1, 13)]
        card_first_six_numbers = kwargs.get('first_six')
        card_expiry_year = kwargs.get('exp_year')
        card_expiry_month = kwargs.get('exp_month')

        if not len(str(card_first_six_numbers)) in [6]:
            self.error_list.append(
                {'first_six':
                 'Kindly provide only the first six numbers on your card'})

        if not len(str(kwargs.get('last_four'))) in [4]:
            self.error_list.append(
                {'last_four':
                 'Kindly provide the last four numbers on your card'})

        if card_expiry_month not in months_number_list:
            self.error_list.append(
                {'exp_month': 'Kindly provide a valid card expiry month'})

        if (card_expiry_year < datetime.now().year) or \
                (card_expiry_month < datetime.now().month
                 and card_expiry_year == datetime.now().year):
            self.error_list.append(
                {'exp_year': 'Kindly provide a non-expired card'})

        if self.error_list:
            return False

        return True

    def validate_kin(self, mobile_number):
        mobile_number = self.validate_mobile_number(mobile_number)
        if self.error_list:
            return self.error_list

        return {
            "mobile_number": mobile_number
        }


class ValidateBusiness(ValidateUser):
    def __init__(self):
        self.error_list = []

    def validate_business_fields(self, **kwargs):
        email = self.validate_email(kwargs.get('email'))
        recovery_email = self.validate_email(kwargs.get(
            'recovery_email')) if kwargs.get('recovery_email') else None
        recovery_mobile_number = self.validate_mobile_number(kwargs.get(
            'recovery_mobile_number'), field_name='recovery_mobile_number') \
                 if kwargs.get('recovery_mobile_number') else None
        mobile_number = self.validate_mobile_number(
            kwargs.get('mobile_number')) if kwargs.get('mobile_number') else None
        password = self.validate_password(kwargs.get('password'))
        address = kwargs.get('address')
        description = kwargs.get('description')
        sector = ','.join([sector.title()
                           for sector in kwargs.get('sector', '').split(',')])
        country = kwargs.get('country')
        currency = self.validate_currency(kwargs.get('currency', "NGN"))
        is_registered = self.validate_is_registered(
            kwargs.get('is_registered'))
        # first_name = self.validate_name(kwargs.get("first_name"), 'first_name')
        # last_name = self.validate_name(kwargs.get('last_name'), 'last_name')
        first_name = kwargs.get("first_name")
        last_name = kwargs.get('last_name')
        business_name = self.validate_business_name(
            kwargs.get('business_name'))
        services = self.validate_services(kwargs.get('services'))

        if all([recovery_mobile_number, mobile_number]) and recovery_mobile_number == mobile_number:
            self.error_list.append(
                {'recovery_mobile_number': "Recovery phone number must be different from mobile phone number"})

        if len(self.error_list):
            return self.error_list

        return {
            "password": password,
            "first_name": first_name,
            "last_name": last_name,
            "address": address,
            "business_name": business_name,
            "services": services,
            "is_registered": is_registered,
            "address": address,
            "country": country,
            "currency": currency,
            "sector": sector,
            "description": description,
            **kwargs
        }

    def validate_business_name(self, business_name):
        if re.match(r'^[A-Za-z0-9\-]',
                    business_name) is None:
            self.error_list.append(
                {"business_name": "Business name can only contain alphabets, numbers and hyphens."})
        return business_name

    def validate_services(self, services):
        return ','.join([service.title() for service in services.split(',')])

    def validate_currency(self, currency):
        if (currency, currency) not in BUSINESS_SUPPORTED_CURRENCIES:
            self.error_list.append(
                {"currency": f"{currency} is not currently supported"})
        return currency

    def validate_is_registered(self, is_registered):
        if is_registered is not None:
            return is_registered
        else:
            self.error_list.append(
                {"is_registered": "is_registered must not be empty"})


def validate_password(password):
    """
    Description: validates a password

    Args:
    password: The password to validate

    Returns:
    password: If the value is valid.
    error: of type dict.
    """
    password = password.strip()
    if re.match('(?=.{8,100})', password) is None:
        return {"error": "password must have at least 8 characters"}
    return password


def validate_email(email):
    """
        Description: validates an email

        Args:
        email: The emailto validate

        Returns:
        email: If the value is valid.
        error: of type dict.
    """
    email = email.strip()
    if re.match(r'^[A-Za-z0-9\.\+_-]+@[A-Za-z0-9\._-]+\.[a-zA-Z]{2,5}$',
                email) is None:
        raise ValidationError({"error": "Please input a valid email"})
    return email


def update_profile(validate_data, user_bvn, **kwargs):
    """ Validate update fields.

    Args:
        validated_data: a dictionary of user data

    Returns:
        validated_data: if datas are valid.
        error: a list of errors.
    """

    error_list = []
    if validate_data.get('gender') is not None:
        gender = validate_data.get('gender')
        gender = gender.strip()
        if gender not in ['male', 'female']:
            error_list.append({"gender": "Gender must be female or male"})

    if validate_data.get('background_color') is not None:
        color = validate_data.get('background_color').strip()
        bg_colors = ['white', 'dark']
        if color.lower() not in bg_colors:
            error_list.append(
                {"background_color": "Please select 'white' or 'dark'"})

    if validate_data.get('color_scheme') is not None:
        color = validate_data.get('color_scheme').strip()
        if re.match(r'^#(?:[0-9a-fA-F]{1,2}){3}$', color) is None:
            error_list.append(
                {"color_scheme": "Scheme color must be in hexadecimal color notation"})

    if validate_data.get('password') is not None:
        password = validate_data.get('password')
        if re.match('(?=.{8,100})', password) is None:
            error_list.append({"password": "password must have at least\
                8 characters"})

    if validate_data.get('first_name') is not None:
        first_name = validate_data.get('first_name')
        if len(first_name.strip()) < 2:
            error_list.append({"first_name": "Length of first_name \
                must two (2) and above"})
        first_name_regex = re.search(r'[^a-zA-Z\-]+', first_name)
        if " " in first_name:
            error_list.append({"first_name": "first_name should contain\
                only aphabet and hypen"})
        if first_name_regex is not None:
            error_list.append({"first_name": "first_name should contain\
                only aphabet and hypen"})

    if validate_data.get('last_name') is not None:
        last_name = validate_data.get('last_name')
        if len(last_name.strip()) < 2:
            error_list.append({"last_name": "Length of last_name \
                must two (2) and above"})
        last_name_regex = re.search(r'[^a-zA-Z\-]+', last_name)
        if " " in last_name:
            error_list.append({"last_name": "last_name should contain\
                only aphabet and hypen"})
        if last_name_regex is not None:
            error_list.append({"last_name": "last_name should contain\
                only aphabet and hypen"})

    if validate_data.get('birthday') is not None:
        birthday = validate_data.get('birthday')
        if user_bvn:
            birth_date = birthday.strftime("%d-%b-%Y")
            bvn_error = bvn_check_profile(
                user_bvn, ('dateOfBirth', birth_date))
            if bvn_error:
                error_list.append({"bvn": bvn_error})

    if validate_data.get("mobile_number") is not None:
        mobile_number = validate_data.get('mobile_number')
        try:
            phone_number = phonenumbers.parse(mobile_number, None)
            if phonenumbers.is_valid_number(phone_number) is False:
                error_list.append(
                    {"mobile_number": f"{mobile_number} is not a valid mobile number"})
                return None
            mobile_number = phonenumbers.format_number(
                phone_number, phonenumbers.PhoneNumberFormat.E164)
        except phonenumbers.phonenumberutil.NumberParseException:
            error_list.append(
                {"mobile_number": f"{mobile_number} is not a valid mobile number."})

    if validate_data.get('bvn') is not None:
        # Todo - if it flies...basically prevent the user from updating BVN information
        # if user_bvn:
        #     error_list.append(
        #         {"bvn": "Opps...cannot update your bvn information"})
        bvn = validate_data.get('bvn').strip()
        user_instance = kwargs.get('instance')
        if len(bvn) != 11 or not bvn.isdigit():
            error_list.append({"bvn": "This is an invalid bvn number"})
        bvn_enquiry = BankingApi.bvn_enquiry(bvn)
        if bvn_enquiry is None:
            error_list.append(
                {"bvn": "BVN validation failed. Validation service is down!"})

        if bvn_enquiry and 'data' in bvn_enquiry and user_instance:
            mobile_number = validate_data.get("mobile_number")

            if mobile_number:
                mobile_number = "".join(mobile_number.split()
                                        ) or user_instance.mobile_number
            if not mobile_number:
                error_list.append(
                    {"bvn": "BVN validation failed. Please add a phone number to your account"})
                return error_list
            if mobile_number.startswith('+234'):
                mobile_number = mobile_number.replace('+234', "0")
            if mobile_number.startswith('+2340'):
                mobile_number = mobile_number.replace('+234', "")
            if mobile_number != bvn_enquiry['data']['phoneNo']:
                error_list.append(
                    {"bvn": "BVN validation failed. Could not match BVN with phone number"})

    if error_list:
        return error_list

    return validate_data


def update_business_profile(validate_data, user_bvn):

    error_list = []

    if validate_data.get('background_color') is not None:
        color = validate_data.get('background_color').strip()
        bg_colors = ['white', 'dark']
        if color.lower() not in bg_colors:
            error_list.append(
                {"background_color": "Please select 'white' or 'dark'"})

    if validate_data.get('color_scheme') is not None:
        color = validate_data.get('color_scheme').strip()
        if re.match(r'^#(?:[0-9a-fA-F]{1,2}){3}$', color) is None:
            error_list.append(
                {"color_scheme": "Scheme color must be in hexadecimal color notation"})

    if validate_data.get('password') is not None:
        password = validate_data.get('password')
        password = password.strip()
        if re.match('(?=.{8,100})', password) is None:
            error_list.append({"password": "password must have at least\
                8 characters"})

    if validate_data.get('first_name') is not None:
        first_name = validate_data.get('first_name')
        if user_bvn:
            bvn_error = bvn_check_profile(user_bvn, ('firstName', first_name))
            if bvn_error:
                error_list.append({"first_name": bvn_error})

        if len(first_name.strip()) < 2:
            error_list.append(
                {"first_name": "Length of first_name must two (2) and above"})
        first_name_regex = re.search(r'[^a-zA-Z\-]+', first_name)
        if " " in first_name:
            error_list.append(
                {"first_name": "first_name should contain only aphabet and hypen"})
        if first_name_regex is not None:
            error_list.append(
                {"first_name": "first_name should contain only aphabet and hypen"})

    if validate_data.get('last_name') is not None:
        last_name = validate_data.get('last_name')
        if user_bvn:
            bvn_error = bvn_check_profile(user_bvn, ('lastName', last_name))
            if bvn_error:
                error_list.append({"last_name": bvn_error})

        if len(last_name.strip()) < 2:
            error_list.append(
                {"last_name": "Length of last_name must two (2) and above"})
        last_name_regex = re.search(r'[^a-zA-Z\-]+', last_name)
        if " " in last_name:
            error_list.append(
                {"last_name": "last_name should contain only aphabet and hypen"})
        if last_name_regex is not None:
            error_list.append(
                {"last_name": "last_name should contain only aphabet and hypen"})

    if validate_data.get('business_name') is not None:
        business_name = validate_data.get('business_name')

        if len(business_name.strip()) < 2:
            error_list.append(
                {"business_name": "Length of business name must two (2) and above"})
        business_name_regex = re.search(r'[^a-zA-Z0-9\-]+', business_name)
        if " " in business_name:
            error_list.append(
                {"business_name": "business_name should contain only aphabet, numbers and hypen"})
        if business_name_regex is not None:
            error_list.append(
                {"business_name": "business_name should contain only aphabet and hypen"})

    if validate_data.get('address') is not None:
        address = validate_data.get('address')

        if len(address.strip()) < 2:
            error_list.append(
                {"address": "Length of address must two (2) and above"})
        address_regex = re.search(r'[^a-zA-Z0-9\-]+', address)
        if " " in address:
            error_list.append(
                {"address": "address should contain only aphabet, numbers and hypen"})
        if address_regex is not None:
            error_list.append(
                {"address": "address should contain only aphabet and hypen"})

    if validate_data.get('description') is not None:
        description = validate_data.get('description')

        if len(description.strip()) < 2:
            error_list.append(
                {"description": "Length of description must two (2) and above"})
        description_regex = re.search(r'[^a-zA-Z0-9\-]+', description)
        if " " in description:
            error_list.append(
                {"description": "description should contain only aphabet, numbers and hypen"})
        if description_regex is not None:
            error_list.append(
                {"description": "description should contain only aphabet and hypen"})

    if validate_data.get('country') is not None:
        country = validate_data.get('country')
        country = country.upper()
        if country in BUSINESS_SUPPORTED_COUNTRY:
            if len(country.strip()) < 2:
                error_list.append(
                    {"country": "Length of country must two (2) and above"})
            country_regex = re.search(r'[^a-zA-Z0-9\-]+', country)
            if " " in address:
                error_list.append(
                    {"country": "country should contain only aphabet, numbers and hypen"})
            if country_regex is not None:
                error_list.append(
                    {"country": "country should contain only aphabet and hypen"})
        else:
            error_list.append({"country": "Country not supported"})

    if validate_data.get('currency') is not None:
        currency = validate_data.get('currency')
        currency = currency.upper()
        if (currency, currency) not in BUSINESS_SUPPORTED_CURRENCIES:
            error_list.append(
                {"currency": f"{currency} is not currently supported"})

    if validate_data.get('sector') is not None:
        sector = validate_data.get('sector')
        sector = sector.upper()
        if (sector, sector) not in BUSINESS_SECTORS:
            error_list.append({"sector": "invalid sector"})

    if validate_data.get('services') is not None:
        services = validate_data.get('services').upper()
        for eachservice in services.upper().split(','):
            if (eachservice, eachservice) not in BUSINESS_SERVICES:
                error_list.append({"services": "Service not available."})

    if validate_data.get("recovery_mobile_number") is not None:
        recovery_mobile_number = validate_data.get('recovery_mobile_number')
        if re.match(r'^\+[0-9]+$', recovery_mobile_number.strip()) is not None:
            phone_number = phonenumbers.parse(recovery_mobile_number, None)
            if phonenumbers.is_valid_number(phone_number) == False:
                error_list.append(
                    {"recovery_mobile_number": "recovery_mobile_number is not valid"})
        else:
            error_list.append({"recovery_mobile_number": "recovery_mobile_number number must contain country code" +
                                                         " and your recovery_mobile_number, e.g +121449599806"})

    if validate_data.get("mobile_number") is not None:
        mobile_number = validate_data.get('mobile_number')
        if re.match(r'^\+[0-9]+$', mobile_number.strip()) is not None:
            phone_number = phonenumbers.parse(mobile_number, None)
            if phonenumbers.is_valid_number(phone_number) == False:
                error_list.append(
                    {"mobile_number": "Mobile number is not valid"})
        else:
            error_list.append({"mobile_number": "Mobile number must contain country code" +
                                                " and your mobile number, e.g +121449599806"})

    if validate_data.get('bvn') is not None:
        bvn = validate_data.get('bvn').strip()
        if len(bvn) != 11 or not bvn.isdigit():
            error_list.append({"bvn": "This is an invalid bvn number"})
        bvn_enquiry = BankingApi.bvn_enquiry(bvn)
        if not bvn_enquiry:
            error_list.append(
                {"bvn": "BVN validation failed. Check number and try again"})

    if error_list:
        return error_list
    return validate_data


def bvn_check_profile(bvn, field):
    bvn_enquiry = BankingApi.bvn_enquiry(bvn)
    if bvn_enquiry and 'data' in bvn_enquiry:
        bvn_field_value = bvn_enquiry['data'][field[0]]
        if bvn_field_value != field[1]:
            return f"{field[0]} does not correspond with bvn"
    else:
        return None


def validate_mobile_number(mobile_number):
    """
        Check that the mobile number is in right format.
    """
    try:
        phone_number = phonenumbers.parse(mobile_number, None)
        if phonenumbers.is_valid_number(phone_number) is False:
            raise ValidationError(
                f"{mobile_number} is not a valid mobile number")
        mobile_number = phonenumbers.format_number(
            phone_number, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.phonenumberutil.NumberParseException as e:
        raise ValidationError(
            f"{mobile_number} is not a valid mobile number. Valid number looks like +2348012345678")


def validate_name(name):
    if name is not None:
        if len(name.strip()) < 2:
            raise ValidationError("Length of name must two (2) and above")
    name_regex = re.search(r'[^a-zA-Z\s]+', name)
    if name_regex is not None:
        raise ValidationError("Name should contain only aphabet and space")


def validate_address(address):
    address = re.search(r'[^a-zA-Z0-9\s\,\.\-]', address)
    if address is not None:
        raise ValidationError(
            "Address should contain only alphabet and number")


def validate_goal_name(goal_name):
    if len(goal_name.strip()) < 3 or len(goal_name.strip()) > 50:
        raise ValidationError(
            "Goal name should not be less than 3 and not more than 50")


def validate_kyc(user):
    user_type = parse_user_type(user)
    # field_opts = dict(personal=dict(user=user),
    #                   business=dict(business=user))[user_type]
    bvn = user.bvn
    # Todo - Enable KYC and Next of Kin check when business gives a go-ahead
    # user_kyc = UserKYC.objects.filter(**field_opts).first()
    # next_of_kin = NextOfKin.objects.filter(**field_opts).first()

    if bvn:
        return True
    else:
        return False


class ValidateTudo:
    def __init__(self):
        self.error_list = []

    def validate_tudo_fields(self, **kwargs):

        goal_name = kwargs.get("goal_name")
        amount = kwargs.get("amount")
        tudo_duration = kwargs.get("tudo_duration")
        currency = kwargs.get("currency")
        category_id = kwargs.get("category_id")
        tudo_media = kwargs.get("tudo_media")
        goal_description = kwargs.get("goal_description")
        is_visible = kwargs.get("is_visible")

        instance = kwargs.get('instance')
        is_update_action = bool(kwargs.get('partial'))

        if is_update_action:
            goal_name = self.validate_goal_name(
                goal_name) if goal_name else instance.goal_name
            amount = self.validate_amount(
                amount) if amount else instance.amount
            currency = self.validate_currency(
                currency) if currency else instance.currency
            tudo_duration = self.validate_tudo_duration(
                tudo_duration) if tudo_duration else instance.tudo_duration
            tudo_category_id = self.validate_tudo_category(
                category_id) if category_id else instance.category_id
            tudo_media = self.validate_tudo_media(
                tudo_media) if tudo_media else instance.tudo_media
            goal_description = kwargs.get("goal_description", instance.goal_description)
            is_visible = kwargs.get("is_visible", instance.is_visible)
        else:
            goal_name = self.validate_goal_name(goal_name)
            amount = self.validate_amount(amount)
            currency = self.validate_currency(currency)
            tudo_duration = self.validate_tudo_duration(tudo_duration)
            tudo_category_id = self.validate_tudo_category(category_id)
            tudo_media = self.validate_tudo_media(
                tudo_media) if tudo_media else None

        if len(self.error_list):
            return self.error_list

        return {
            "goal_name": goal_name,
            "amount": amount,
            "currency": currency,
            "tudo_duration": tudo_duration,
            "tudo_category_id": tudo_category_id,
            "tudo_media": tudo_media,
            "goal_description": goal_description,
            "is_visible": is_visible
        }

    def validate_business_tudo_fields(self, **kwargs):

        goal_name = kwargs.get("goal_name")
        amount = kwargs.get("amount")
        tudo_duration = kwargs.get("tudo_duration")
        currency = kwargs.get("currency")
        category_id = kwargs.get("category_id")
        tudo_media = kwargs.get("tudo_media")
        goal_description = kwargs.get("goal_description")
        is_visible = kwargs.get("is_visible")

        instance = kwargs.get('instance')
        is_update_action = bool(kwargs.get('partial'))

        if is_update_action:
            goal_name = self.validate_goal_name(
                goal_name) if goal_name else instance.goal_name
            amount = self.validate_amount(
                amount) if amount else instance.amount
            currency = self.validate_currency(
                currency) if currency else instance.currency
            tudo_duration = self.validate_tudo_duration(
                tudo_duration) if tudo_duration else instance.tudo_duration
            tudo_category_id = self.validate_business_tudo_category(
                category_id) if category_id else instance.category_id
            tudo_media = self.validate_tudo_media(
                tudo_media) if tudo_media else instance.tudo_media
            goal_description = kwargs.get("goal_description", instance.goal_description)
            is_visible = kwargs.get("is_visible", instance.is_visible)
        else:
            goal_name = self.validate_goal_name(goal_name)
            amount = self.validate_amount(amount)
            currency = self.validate_currency(currency)
            tudo_duration = self.validate_tudo_duration(tudo_duration)
            tudo_category_id = self.validate_business_tudo_category(
                category_id)
            tudo_media = self.validate_tudo_media(tudo_media)

        if len(self.error_list):
            return self.error_list

        return {
            "goal_name": goal_name,
            "amount": amount,
            "currency": currency,
            "tudo_duration": tudo_duration,
            "tudo_category_id": tudo_category_id,
            "tudo_media": tudo_media,
            "goal_description": goal_description,
            "is_visible": is_visible
        }

    def validate_date(self, date):
        try:
            return datetime.strptime(date, '%Y-%m-%d')
        except Exception as err:
            return err

    def validate_tudo_duration(self, tudo_duration):
        if isinstance(tudo_duration, dict):
            custom_duration = tudo_duration.get('custom')
            if not custom_duration:
                self.error_list.append(
                    {"tudo_duration": "Please select '7 days', '30 Days', '60 Days', '90 Days' or a custom date"})
                return

            parsed_date_string = self.validate_date(custom_duration)
            if isinstance(parsed_date_string, Exception):
                self.error_list.append(
                    {"tudo_duration": "Incorrect! date format should be YYYY-MM-DD"}
                )
                return

            custom_duration = parsed_date_string
            days_7 = datetime.now() + timedelta(days=7)
            days_90 = datetime.now() + timedelta(days=90)

            if custom_duration <= datetime.now() or \
                    custom_duration < days_7 or custom_duration > days_90:
                self.error_list.append(
                    {"tudo_duration": "Duration must be between 7 to 90 days"}
                )

            tudo_duration = str(custom_duration - datetime.now())[:7]
        else:
            durations = ['7 days', '30 days', '60 days', '90 days']
            if tudo_duration.lower() not in durations:
                self.error_list.append(
                    {"tudo_duration": "Please select '7 days','30 Days', '60 Days', '90 Days' or a Custom date"})

        return tudo_duration

    def validate_amount(self, amounts):
        if not isinstance(amounts, int):
            self.error_list.append(
                {"amount": "amount should be an integer"})
            return
        if amounts < 100000 or amounts > 50000000000:
            self.error_list.append(
                {"amount": "Amount should be  between 1000 and 500million"})
        return amounts

    def validate_currency(self, currency):
        if (currency, currency) not in CURRENCIES:
            self.error_list.append(
                {"currency": f"{currency} is not currently supported"})
        return currency

    def validate_goal_name(self, goal_name):
        if goal_name is not None:
            if len(goal_name.strip()) < 3 or len(goal_name.strip()) > 50:
                self.error_list.append(
                    {"goal_name": "Goal name should not be less than 3 and not more than 50"})
        return goal_name

    def validate_tudo_media(self, tudo_media):
        media_name = 'tudo-headers/' + str(uuid.uuid4().hex)
        data_formats = ('data:video/mp4;base64,',
                        'data:image/png;base64',
                        'data:image/jpeg;base64',
                        'data:image/jpg;base64')
        if tudo_media and tudo_media.startswith(data_formats):
            media_meta = tudo_media.split(',')[0]
            str_len = len(tudo_media) - len(media_meta)

            media_size = (4 * math.ceil((str_len / 3)) * 0.5624896334383812) / 1000
            if media_size > 1000 and media_meta.startswith('data:image/'):
                self.error_list.append(
                    {"tudo_media": "Image size cannot be greater then 1mb"})
                return None
            if media_size > 10000 and media_meta.startswith('data:video/'):
                self.error_list.append(
                    {"tudo_media": "Image size cannot be greater then 10mb"})
                return None
            media_ext = media_meta.replace("data:image/", "").replace(";base64", "") if media_meta.startswith(
                'data:image/') else media_meta.replace("data:video/", "").replace(";base64", "")
            media_data = tudo_media.split(',')[1]
            file_name = f"{media_name}.{media_ext}"
            img_url = MediaHandler.upload_raw(media_data, file_name)
            if not img_url:
                self.error_list.append(
                    {"tudo_media": "Error occurred uploading your media file"})
            return img_url or None

        self.error_list.append(
            {"tudo_media": "Invalid media or extension not supported"})

    def validate_tudo_category(self, category_id):
        if category_id in ['6bd19cgjc37k', 'h473ci8axtfx']:
            self.error_list.append(
                {"category_id": "You cannot create this goal under group or business category"})
            return None

        tudo_category = TudoCategory.objects.filter(id=category_id).first()
        if not tudo_category:
            self.error_list.append(
                {"category_id": "This category does not exist"})

        return category_id

    def validate_business_tudo_category(self, category_id):
        if category_id in TudoCategory.objects.exclude(
                id__in=['6bd19cgjc37k', 'ce9e61r06vob']).values_list('id', flat=True):
            return category_id
        else:
            self.error_list.append(
                {"category_id": "This goal cannot be created under personal or group category"})
            return None

    def check_required_fields(self, data, fields=[]):
        error = []
        required_fields = [*fields]
        for tudo in data:
            for field in required_fields:
                if field not in tudo.keys():
                    error.append({f"{field}": f"This field is required"})
        if error:
            return error
        return True


def validate_periodic_savings_data(**data):
    """
    This method validates periodic savings payload
    Args:
        data: key-worded parameter that holds required data
              for creating a savings plan
    """

    user = data.pop('user')
    card = data.pop('card', None)
    transaction_ref = uuid.uuid4()
    error_list = []
    now = timezone.now()
    debit_card = data.get("card_id")

    if debit_card is not None:
        card = DebitCard.objects.filter(id=data['card_id'], user=user).first()
        if card is None:
            error_list.append(
                {'card_id': 'The card with this details cannot be found'})

    plan = Plan.objects.filter(type='Periodic').first()

    if plan is None:
        error_list.append(
            {'plan_id': 'The selected plan does not exist'})

    if data['start_amount'] != data['frequency_amount']:
        error_list.append(
            {'start_amount': 'Your starting amount must be same as your Frequency amount'})

    if data["start_date"] < now:
        error_list.append(
            {'start_date': "You can't start your savings earlier than now"})

    if data["start_date"] > now + relativedelta(months=3):
        error_list.append(
            {'start_date': 'You cannot start your savings in more than 3 months from now'})

    if error_list:
        raise exceptions.ValidationError({'error': error_list})

    return {'plan_type': plan, 'user': user, 'card': card,
            'start_amount': data["start_amount"],
            'frequency': data["frequency"],
            'frequency_amount': data["frequency_amount"],
            'transaction_ref': transaction_ref, **data}


def validate_update_savings(validated_data, instance):
    error_list = []

    if validated_data.get('is_paused') and not instance.saving_status == 'RUNNING':
        error_list.append(
            {'saving_status': "You can only pause running plans"})

    if validated_data.get("target_amount") is not None:
        target_amount = validated_data.get("target_amount")
        if instance.saved_amount > target_amount:
            error_list.append(
                {'target_amount': "amount already saved can't be greater than your target amount"})

    if validated_data.get("card_id") is not None:
        card_id = validated_data.get("card_id")
        card = DebitCard.objects.filter(
            id=card_id, user=instance.user_id).first()
        if card is None:
            error_list.append(
                {'card_id': 'The card with this details cannot be found'})

    if error_list:
        return error_list
    return validated_data

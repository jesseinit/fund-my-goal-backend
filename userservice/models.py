from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from django.contrib.auth.hashers import make_password

from adminservice.models import TudoCategory
from userservice.utils.generate_id import LENGTH_OF_ID
from userservice.utils.helpers import (NotificationStatus, StateType,
                                       TransactionStatus, TudoContributionType,
                                       TudoDuration, TudoStatus,
                                       create_invite_code,
                                       default_tudo_description)
from utils.constants import (BUSINESS_SUPPORTED_COUNTRY, CURRENCIES,
                             DEFAULT_AVATAR_URL, FOLLOWING_STATUS,
                             GROUP_ACCESS_TYPE, GROUP_MEMBER_ROLES,
                             GROUP_MEMBERSHIP_TYPE, GROUP_TUDO_STATUS,
                             GROUPTUDO_TRANSACTION_TYPE, INVITE_STATUS,
                             LIKE_STATUS, NOTIFICATION_ENTITY,
                             NOTIFICATION_TYPE, REWARDTYPES, WITHDRAWAL_STATUS,
                             WITHDRAWAL_DESTINATION)
from utils.helpers import BaseAbstractModel


class UserManager(BaseUserManager):
    def create_user(self, **kwargs):
        """
        Creates and saves a User with email, password, mobile_number credentials.
        """
        email = kwargs.get("email")
        password = kwargs.get("password")
        mobile_number = kwargs.get("mobile_number")
        first_name = kwargs.get("first_name")
        last_name = kwargs.get("last_name")
        invite_code = create_invite_code()
        is_active = kwargs.get("is_active") or False
        auth_provider = kwargs.get("auth_provider")
        social_password = make_password(kwargs.get(
            "social_password")) if kwargs.get("social_password") else None
        user = self.model(
            mobile_number=mobile_number, email=self.normalize_email(
                email).lower(),
            first_name=first_name, last_name=last_name, invite_code=invite_code,
            auth_provider=auth_provider, social_password=social_password, is_active=is_active
        )
        user.set_password(password)
        user.save()
        return user

    def get_queryset(self):
        return super().get_queryset().filter(state=StateType.active.value)


class User(BaseAbstractModel, AbstractBaseUser):
    """
        Personal User Model
    """
    AUTH_PROVIDER = [
        ('LOCAL', 'LOCAL'),
        ("GOOGLE", 'GOOGLE'),
        ("FACEBOOK", 'FACEBOOK'),
    ]

    first_name = models.CharField(max_length=100, null=False, blank=False)
    last_name = models.CharField(max_length=100, null=False, blank=False)
    email = models.EmailField(max_length=100, null=False, unique=True)
    mobile_number = models.CharField(max_length=100, null=True, unique=True)
    password = models.CharField(max_length=100, null=False)
    social_password = models.CharField(max_length=100, null=True, default=None)
    profile_image = models.URLField(default=DEFAULT_AVATAR_URL)
    bvn = models.CharField(max_length=11, null=True, unique=True, default=None)
    gender = models.CharField(max_length=50, null=True)
    birthday = models.DateField(auto_now=False, null=True, blank=True)
    invited_by = models.CharField(null=True, max_length=60)
    invite_code = models.CharField(max_length=10, unique=True, null=True)
    points = models.IntegerField(default=0)
    color_scheme = models.CharField(max_length=7, default='#7594FB')
    background_color = models.CharField(max_length=10, default='white')
    is_active = models.BooleanField(default=False)
    auth_provider = models.CharField(
        max_length=10, default='LOCAL', choices=AUTH_PROVIDER)
    USERNAME_FIELD = "email"

    objects = UserManager()

    def __str__(self):
        return f"<Tudo User - {self.email}>"


class BankAccountManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(state=StateType.active.value)


class BankAccount(BaseAbstractModel):

    user = models.ForeignKey(
        User, null=True, default=None, on_delete=models.CASCADE)
    business = models.ForeignKey(
        Business, null=True, default=None, on_delete=models.CASCADE)
    bank_code = models.CharField(max_length=50)
    account_name = models.CharField(max_length=200)
    account_number = models.CharField(max_length=50)
    bank_name = models.CharField(max_length=200)

    objects = BankAccountManager()


class DebitCardManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(state=StateType.active.value)


class DebitCard(BaseAbstractModel):
    """ Debit card model """
    user = models.ForeignKey(
        User, null=True, default=None,
        on_delete=models.CASCADE
    )
    business = models.ForeignKey(
        Business, null=True, default=None,
        on_delete=models.CASCADE
    )
    authorization_code = models.CharField(unique=True, max_length=200)
    card_type = models.CharField(max_length=200)
    first_six = models.IntegerField()
    last_four = models.IntegerField()
    exp_month = models.IntegerField()
    exp_year = models.IntegerField()
    card_bank = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = DebitCardManager()

    def __str__(self):
        return f'<DebitCard ****{self.last_four}>'

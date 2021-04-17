from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from django.contrib.auth.hashers import make_password

from userservice.utils.helpers import (StateType)
from utils.constants import (,
                             DEFAULT_AVATAR_URL, )
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
        is_active = kwargs.get("is_active") or False
        user = self.model(
            mobile_number=mobile_number, email=self.normalize_email(
                email).lower(),
            first_name=first_name, last_name=last_name, is_active=is_active
        )
        user.set_password(password)
        user.save()
        return user

    def get_queryset(self):
        return super().get_queryset().filter(state=StateType.active.value)


class User(BaseAbstractModel, AbstractBaseUser):
    """
        User Model
    """
    first_name = models.CharField(max_length=100, null=False, blank=False)
    last_name = models.CharField(max_length=100, null=False, blank=False)
    email = models.EmailField(max_length=100, null=False, unique=True)
    mobile_number = models.CharField(max_length=100, null=True, unique=True)
    password = models.CharField(max_length=100, null=False)
    profile_image_url = models.URLField(default=DEFAULT_AVATAR_URL)
    bvn = models.CharField(max_length=11, null=True, unique=True, default=None)
    gender = models.CharField(max_length=50, null=True)
    dob = models.DateField(auto_now=False, null=True, blank=True)
    is_active = models.BooleanField(default=False)
    USERNAME_FIELD = "email"

    objects = UserManager()

    def __str__(self):
        return f"<User - {self.email}>"


# class BankAccountManager(models.Manager):
#     def get_queryset(self):
#         return super().get_queryset().filter(state=StateType.active.value)


# class BankAccount(BaseAbstractModel):

#     user = models.ForeignKey(
#         User, null=True, default=None, on_delete=models.CASCADE)
#     business = models.ForeignKey(
#         Business, null=True, default=None, on_delete=models.CASCADE)
#     bank_code = models.CharField(max_length=50)
#     account_name = models.CharField(max_length=200)
#     account_number = models.CharField(max_length=50)
#     bank_name = models.CharField(max_length=200)

#     objects = BankAccountManager()


# class DebitCardManager(models.Manager):
#     def get_queryset(self):
#         return super().get_queryset().filter(state=StateType.active.value)


# class DebitCard(BaseAbstractModel):
#     """ Debit card model """
#     user = models.ForeignKey(
#         User, null=True, default=None,
#         on_delete=models.CASCADE
#     )
#     business = models.ForeignKey(
#         Business, null=True, default=None,
#         on_delete=models.CASCADE
#     )
#     authorization_code = models.CharField(unique=True, max_length=200)
#     card_type = models.CharField(max_length=200)
#     first_six = models.IntegerField()
#     last_four = models.IntegerField()
#     exp_month = models.IntegerField()
#     exp_year = models.IntegerField()
#     card_bank = models.CharField(max_length=200)
#     created_at = models.DateTimeField(auto_now_add=True)

#     objects = DebitCardManager()

#     def __str__(self):
#         return f'<DebitCard ****{self.last_four}>'

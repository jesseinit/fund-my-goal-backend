
from datetime import timedelta

import pytest
from django.utils import timezone
from mixer.backend.django import mixer

from adminservice.models import Admin, AdminPermission, AdminRole, TudoCategory
from savingservice.models import (Plan, Savings, SavingsTransaction,
                                  SavingsWithdrawal)
from userservice.models import (BankAccount, DebitCard, GroupTudo, NextOfKin,
                                Notification, Tudo, TudoContribution,
                                TudoMedia, User, UserKYC)
from userservice.utils.helpers import (TransactionStatus, TudoContributionType,
                                       UserActionStatus)
from utils.helpers import delete_from_redis
from random import randint


pytest_plugins = [
    "userservice.tests.fixtures.user_fixtures",
]


@pytest.fixture()
def new_unverified_user():
    new_user = {
        "first_name": "john",
        "last_name": "doe",
        "email": "johndoe@gmail.com",
        "mobile_number": "+12124959980",
        "password": "Password123"
    }
    user = mixer.blend(User, **new_user)

    return new_user


@pytest.fixture()
def new_valid_user():
    new_user = {
        "first_name": "john",
        "last_name": "doe",
        "email": "johndoe@gmail.com",
        "mobile_number": "+491771789427",
        "password": "Password123",
        "bvn": None
    }
    new_user['is_active'] = True
    user = mixer.blend(User, **new_user)
    new_user['id'] = user.id
    return new_user


@pytest.fixture()
def inviter_user(new_valid_user):
    new_valid_user['created_at'] = timezone.now()
    new_valid_user['invite_code'] = 'testinvit1'
    user = User(**new_valid_user)
    user.save()
    return user


@pytest.fixture()
def new_valid_user_2():
    new_user = {
        "first_name": "Mary ",
        "last_name": "Jones",
        "email": "maryjones@gmail.com",
        "mobile_number": "+2347012706429",
        "password": "Password345"
    }
    new_user['is_active'] = True
    user = mixer.blend(User, **new_user)
    new_user['id'] = user.id
    return new_user


@pytest.fixture()
def invited_user(new_valid_user, new_valid_user_2):
    user = {'created_at': timezone.now(),
            'invite_code': 'testinvit2',
            'invited_by': new_valid_user['id'],
            'email': "peterjones@gmail.com",
            'id': 'user_id',
            'is_active': True}
    user = mixer.blend(User, **user)
    user.set_password('Password345')
    user.save()
    return user


@pytest.fixture()
def auth_header_invited_user(client, invited_user):
    response = client.post('/api/v1/login',
                           data={
                               'email': invited_user.email,
                               'password': 'Password345'
                           })
    token = str(response.data["token"], 'utf-8')
    header = {"HTTP_AUTHORIZATION": 'Bearer ' + token}
    return header


@mixer.middleware(User)
def encrypt_password(user):
    user.set_password('Password123')
    return user


@pytest.fixture()
def auth_header(client, new_valid_user,):
    response = client.post('/api/v1/login',
                           data={
                               'email': new_valid_user['email'],
                               'password': new_valid_user['password']
                           })
    token = str(response.data["token"], 'utf-8')
    header = {"HTTP_AUTHORIZATION": 'Bearer ' + token,
              "content_type": 'application/json'}
    yield header
    delete_from_redis('blacklisted_tokens')


@pytest.fixture(scope='function')
def new_user():
    return {
        "first_name": "john",
        "last_name": "doe",
        "email": "johndoe@gmail.com",
        "mobile_number": "+2348153353131",
        "password": "Password123"
    }


@pytest.fixture(scope='function')
def new_user2():
    return {
        "first_name": "john",
        "last_name": "doe",
        "email": "johndoe1@gmail.com",
        "mobile_number": "+13472336099",
        "password": "Password123"
    }


@pytest.fixture()
def new_user_to_verify():
    new_user = {
        "first_name": "john",
        "last_name": "doe",
        "email": "joe.doe1@gmail.com",
        "mobile_number": "+13472336099",
        "password": "Password123"
    }

    return new_user


@pytest.fixture()
def invalid_otp():
    return {
        "otp": "1111",
        "email": "joe.doe1@gmail.com"
    }


@pytest.fixture()
def valid_bank_details():
    return {
        "is_resolved": True,
        "account_name": "John Smith",
        "data": {
            "account_number": "0000000000",
            "account_name": "John Smith",
            "bank_id": 9
        }
    }


@pytest.fixture()
def added_bank_details_user_1(new_valid_user):
    bank_details = {
        "account_number": "0000000000",
        "account_name": "John Smith",
        "bank_code": "059",
        "user_id": new_valid_user['id']
    }
    added_details = mixer.blend(BankAccount, **bank_details)
    return added_details


@pytest.fixture()
def added_bank_details_user_2(new_valid_user_2):
    bank_details = {
        "account_number": "55555555555",
        "account_name": "mary_jones",
        "bank_code": "059",
        "user_id": new_valid_user_2['id']
    }
    return BankAccount.objects.create(**bank_details)


@pytest.fixture()
def invalid_bank_details():
    return {
        "status": False,
        "message": "Could not resolve account name. \
                 Check parameters or try again."
    }


@pytest.fixture()
def update_user(new_valid_user):
    return {
        "id": new_valid_user["id"],
        "gender": "female",
        "first_name": "Mariam",
        "last_name": "Audu",
        "birthday": "1958-08-07",
        "profile_image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEBLAEsAAD",
        "old_password": "Password123",
        "password": "88888888",
        "mobile_number": "+2348130462902",
        "bvn": "22222222234",
    }


@pytest.fixture()
def new_next_of_kin(new_valid_user):
    return {
        "first_name": "Mr",
        "last_name": "Bingo",
        "email": "john.doe@gmail.com",
        "relationship": "brother",
        "mobile_number": "+2348064557366",
        "address": "Aderibigbe street, OKOKOKo",
        "password": new_valid_user['password'],
        "user_id": new_valid_user['id']
    }


@pytest.fixture()
def new_kyc(new_valid_user):
    return {
        "image_data": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEBLAEsAAD",
        "image_extension": "jpeg",
        "country_residence": "Germany3",
        "state_residence": "Berlin",
        "password": new_valid_user['password'],
        "residential_address": "yoyo",
        "user_id": new_valid_user['id']
    }


@pytest.fixture()
def new_random_kyc(new_valid_user):
    return {
        "identity_card_url": "http://www.card.png",
        "country_residence": "Germany3",
        "state_residence": "Berlin",
        "password": new_valid_user['password'],
        "residential_address": "yoyo",
    }


@pytest.fixture()
def new_create_kyc(new_kyc):
    kyc = mixer.blend(UserKYC, **new_kyc)
    return kyc


@pytest.fixture()
def new_create_kin(new_next_of_kin):
    kin = mixer.blend(NextOfKin, **new_next_of_kin)
    return kin


@pytest.fixture()
def new_create_random_kyc(new_random_kyc):
    kyc = mixer.blend(UserKYC, **new_random_kyc)
    return kyc


@pytest.fixture()
def valid_debit_card(new_valid_user):
    """ A valid debit card fixture """
    card_details = {
        "authorization_code": "AUTH_8tjjdt",
        "card_type": "visa",
        "last_four": "1381",
        "exp_month": "08",
        "exp_year": "2020",
        "first_six": "412345",
        "card_bank": "TEST BANK",
        "user_id": new_valid_user['id']
    }
    debit_card = DebitCard.objects.create(**card_details)
    return (card_details, debit_card.id)


@pytest.fixture()
def invalid_debit_card():
    """ An invalid debit card fixture """
    return {
        "authorization_code": "AUT",
        "card_type": "visa",
        "last_four": "11",
        "exp_month": "08",
        "exp_year": "2008",
        "first_six": "412345",
        "card_bank": "TEST BANK"
    }


@pytest.fixture()
def add_tudo_category(new_valid_user):
    category = TudoCategory.objects.create(category="Public")
    return category


@pytest.fixture()
def add_tudo_category(new_valid_user):
    category = TudoCategory.objects.create(category="Public")
    return category


@pytest.fixture()
def create_tudo_data(add_tudo_category):
    category = add_tudo_category
    return {
        "tudos": [{
            "goal_name": "Wedding",
            "amount": 200400,
            "tudo_duration": "90 Days",
            "is_visible": True,
            "currency": "NGN",
            "tudo_media": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEBLAE",
            "category_id": category.id
        }]
    }


@pytest.fixture()
def tudo_update_details():
    return {
        "goal_name": "Party",
        "is_visible": False}


@pytest.fixture()
def created_tudo(new_valid_user, create_tudo_data):
    """ Create a tudo record """
    from datetime import datetime, timedelta, timezone
    completion_date = timedelta(days=30) + datetime.now(tz=timezone.utc)
    return Tudo.objects.create(**create_tudo_data['tudos'][0],
                               user_id=new_valid_user['id'],
                               status='running',
                               completion_date=completion_date,
                               share_code='BU9232FBY0'
                               )


@pytest.fixture()
def created_completed_tudo(new_valid_user, create_tudo_data):
    """ Create a completed tudo record """
    completion_date = timedelta(days=30) + timezone.now()
    creation_date = timezone.now() - timedelta(days=30)
    tudo = Tudo(**create_tudo_data['tudos'][0],
                user_id=new_valid_user['id'],
                status='completed',
                completion_date=completion_date,
                share_code='AU9232FBK0',
                amount_generated=2000000)
    tudo.save()
    tudo.start_date = creation_date
    tudo.save()
    return tudo


@pytest.fixture()
def created_completed_24_hours_tudo(new_valid_user, create_tudo_data):
    """ Create a completed tudo which was created less than 24 hours ago """
    from datetime import timedelta
    from django.utils import timezone
    completion_date = timedelta(hours=5) + timezone.now()
    return Tudo.objects.create(**create_tudo_data['tudos'][0],
                               user_id=new_valid_user['id'],
                               status='completed',
                               completion_date=completion_date,
                               share_code='AU9232FBK0',
                               amount_generated=2000000,
                               )


@pytest.fixture()
def created_running_tudo(new_valid_user, create_tudo_data):
    """ Create a completed tudo record """
    from datetime import datetime, timedelta, timezone
    completion_date = timedelta(days=30) + datetime.now(tz=timezone.utc)
    return Tudo.objects.create(**create_tudo_data['tudos'][0],
                               user_id=new_valid_user['id'],
                               completion_date=completion_date,
                               share_code='NH8732MKK0',
                               amount_generated=20000,
                               )


@pytest.fixture()
def created_paid_tudo(new_valid_user, create_tudo_data):
    """ Create a paid tudo record """
    from datetime import datetime, timedelta, timezone
    completion_date = timedelta(days=30) + datetime.now(tz=timezone.utc)
    return Tudo.objects.create(**create_tudo_data['tudos'][0],
                               user_id=new_valid_user['id'],
                               status='paid',
                               completion_date=completion_date,
                               share_code='AU9232FBK0'
                               )


@pytest.fixture()
def created_tudo_with_amount_generated(new_valid_user, create_tudo_data):
    """ Create a tudo record """
    from datetime import datetime, timedelta, timezone
    completion_date = timedelta(days=30) + datetime.now(tz=timezone.utc)
    return Tudo.objects.create(**create_tudo_data['tudos'][0],
                               user_id=new_valid_user['id'],
                               completion_date=completion_date,
                               amount_generated=2000,
                               share_code='BU9232FBUM'
                               )


@pytest.fixture()
def completed_tudo_contribution(created_tudo):
    contribution_details = {
        'contributor_name': 'Mobolaji',
        'contributor_email': 'mobolajijohnson@gmail.com',
        'tudo_code': created_tudo,
        'amount': 500000,
        'reference': 'reference-code',
        'status': TransactionStatus.SUCCESS.value
    }
    return TudoContribution.objects.create(**contribution_details)


# @pytest.fixture()
# def grouped_tudo_data(created_tudo, created_tudo_with_amount_generated, new_valid_user):
#     tudo_ids = sorted([created_tudo.id, created_tudo_with_amount_generated.id])
#     group_hash = hashlib.md5(json.dumps(tudo_ids).encode('utf-8')).hexdigest()

#     return GroupTudo.objects.bulk_create([
#         GroupTudo(group_code='4MDJL0QLJE', tudo_id=tudo_id,
#                     group_name='My wedding plan',
#                     user_id=new_valid_user['id'],
#                     group_hash=group_hash
#                     ) for tudo_id in tudo_ids
#     ])


@pytest.fixture()
def tudo_topup_data(created_tudo, valid_debit_card):
    return {
        "topup_amount": 1500000,
        "tudo_id": created_tudo.id,
        "card_id": valid_debit_card[1]
    }


@pytest.fixture()
def tudo_topup_paid_data(created_paid_tudo, valid_debit_card):
    return {
        "topup_amount": 1500000,
        "tudo_id": created_paid_tudo.id,
        "card_id": valid_debit_card[1]
    }


@pytest.fixture()
def valid_plan():
    """ Create a sample plan """
    plan_type = mixer.blend(Plan)
    return plan_type


@pytest.fixture()
def locked_plan():
    """ Create a sample plan """
    plan_type = Plan.objects.create(**{
        "pk": "3",
        "state": "StateType.active",
        "created_at": "2019-11-24T23:09:34.713380Z",
        "updated_at": "2019-11-24T23:09:34.713380Z",
        "name": "Some Custom Savings Type Name - Locked",
        "type": "Locked",
        "description": "Some plan description",
        "image": "some-plan-image.jpeg",
        "interest_rate": "16.00"
    })
    return plan_type


@pytest.fixture()
def cardless_locked_savings_data(locked_plan):
    savings_plan_data = {
        "purpose": "Detty December",
        "target_amount": "2500000",
        "start_amount": "32000",
        "allow_interest": False,
        "start_date": (timezone.now() + timedelta(seconds=40)).strftime('%Y-%m-%d %H:%M:%S'),
        "maturity_date": (timezone.now() + timedelta(days=100)).strftime('%Y-%m-%d %H:%M:%S')
    }
    return savings_plan_data


@pytest.fixture()
def card_locked_savings_data(locked_plan, valid_debit_card):
    savings_plan_data = {
        "card_id": valid_debit_card[1],
        "purpose": "Detty December",
        "frequency": "daily",
        "target_amount": "2500000",
        "start_amount": "32000",
        "allow_interest": False,
        "start_date": (timezone.now() + timedelta(seconds=40)).strftime('%Y-%m-%d %H:%M:%S'),
        "maturity_date": (timezone.now() + timedelta(days=100)).strftime('%Y-%m-%d %H:%M:%S')
    }
    return savings_plan_data


@pytest.fixture()
def created_notification(new_valid_user):
    """ Create a notification record """
    return Notification.objects.create(
        user_id=new_valid_user['id'],
        summary="Test Notification",
        notification_text='Notifying the user about something important'
    )


@pytest.fixture()
def targeted_plan():
    """ Create a sample plan """
    plan_type = Plan.objects.create(**{
        "pk": 1,
        "state": "StateType.active",
        "created_at": "2019-11-24T23:09:34.713380Z",
        "updated_at": "2019-11-24T23:09:34.713380Z",
        "name": "Some Custom Savings Type Name - Targeted",
        "type": "Targeted",
        "description": "Some plan description",
        "image": "some-plan-image.jpeg",
        "interest_rate": "11.00"
    })
    return plan_type


@pytest.fixture()
def cardless_targeted_savings_data(targeted_plan):
    savings_plan_data = {
        "purpose": "Detty December",
        "target_amount": "25000000",
        "start_amount": "32000",
        "allow_interest": False,
        "frequency": "DAILY",
        "start_date": (timezone.now() + timedelta(seconds=40)).strftime('%Y-%m-%d %H:%M:%S')
    }
    return savings_plan_data


@pytest.fixture()
def card_targeted_savings_data(targeted_plan, valid_debit_card):
    savings_plan_data = {
        "card_id": valid_debit_card[1],
        "purpose": "Detty December",
        "target_amount": "25000000",
        "start_amount": "3200000",
        "frequency": "DAILY",
        "allow_interest": False,
        "start_date": (timezone.now() + timedelta(seconds=40)).strftime('%Y-%m-%d %H:%M:%S')
    }
    return savings_plan_data


@pytest.fixture()
def periodic_plan():
    """ Create a sample periodic plan  """
    plan_type = Plan.objects.create(**{
        "pk": 2,
        "state": "StateType.active",
        "created_at": "2019-11-24T23:09:34.713380Z",
        "updated_at": "2019-11-24T23:09:34.713380Z",
        "name": "Some Custom Savings Type Name - Periodic ",
        "type": "Periodic",
        "description": "Some plan description",
        "image": "some-plan-image.jpeg",
        "interest_rate": "11.00"
    })
    return plan_type


@pytest.fixture()
def card_periodic_savings_data(periodic_plan, valid_debit_card):
    savings_plan_data = {
        "card_id": valid_debit_card[1],
        "purpose": "Detty December",
        "frequency": "DAILY",
        "frequency_amount": "2500000",
        "start_amount": "2500000",
        "start_date": (timezone.now() + timedelta(seconds=40)).strftime('%Y-%m-%d %H:%M:%S'),
    }
    return savings_plan_data


@pytest.fixture()
def cardless_periodic_savings_data(periodic_plan):
    savings_plan_data = {
        "purpose": "Detty December",
        "frequency": "DAILY",
        "frequency_amount": "32000",
        "start_amount": "32000",
        "start_date": (timezone.now() + timedelta(seconds=40)).strftime('%Y-%m-%d %H:%M:%S'),
    }
    return savings_plan_data


@pytest.fixture()
def locked_savings_data(new_valid_user, cardless_locked_savings_data, locked_plan):
    del cardless_locked_savings_data['start_amount']
    del cardless_locked_savings_data['maturity_date']
    del cardless_locked_savings_data['start_date']
    return dict(**cardless_locked_savings_data,
                user_id=new_valid_user['id'],
                plan_type_id=locked_plan.id,
                interest_rate=7.0,
                transaction_status='SUCCESS',
                # allow_interest=False,
                saved_amount=50000,
                start_date='2020-08-12 00:13:59+01',
                maturity_date='2020-08-12 00:13:59+01')


@pytest.fixture()
def completed_locked_savings(locked_savings_data):
    '''Create a completed locked savings'''
    locked_savings_data['saving_status'] = 'COMPLETED'
    return Savings.objects.create(
        **locked_savings_data
    )


@pytest.fixture()
def running_locked_savings(locked_savings_data):
    '''Create a running locked savings'''
    locked_savings_data['saving_status'] = 'RUNNING'
    locked_savings_data['allow_interest'] = True
    return Savings.objects.create(
        **locked_savings_data
    )


@pytest.fixture()
def paid_locked_savings(locked_savings_data):
    '''Create a paid locked savings'''
    locked_savings_data['saving_status'] = 'PAID'
    return Savings.objects.create(
        **locked_savings_data
    )


@pytest.fixture()
def targeted_savings_data(new_valid_user, cardless_targeted_savings_data, targeted_plan):
    del cardless_targeted_savings_data['start_amount']
    del cardless_targeted_savings_data['start_date']
    return dict(**cardless_targeted_savings_data,
                user_id=new_valid_user['id'],
                plan_type_id=targeted_plan.id,
                interest_rate=7.0,
                transaction_status='SUCCESS',
                # allow_interest=False,
                saved_amount=50000,
                start_date='2020-08-12 00:13:59+01',
                maturity_date='2020-08-12 00:13:59+01')


@pytest.fixture()
def completed_targeted_savings(targeted_savings_data):
    '''Create a completed targeted savings'''
    targeted_savings_data['saving_status'] = 'COMPLETED'
    return Savings.objects.create(
        **targeted_savings_data
    )


@pytest.fixture()
def running_targeted_savings(targeted_savings_data):
    '''Create a running targeted savings'''
    targeted_savings_data['saving_status'] = 'RUNNING'
    return Savings.objects.create(
        **targeted_savings_data
    )


@pytest.fixture()
def paid_targeted_savings(targeted_savings_data):
    '''Create a paid targeted savings'''
    targeted_savings_data['saving_status'] = 'PAID'
    return Savings.objects.create(
        **targeted_savings_data
    )


@pytest.fixture()
def periodic_savings_data(new_valid_user, cardless_periodic_savings_data, periodic_plan):
    del cardless_periodic_savings_data['start_amount']
    del cardless_periodic_savings_data['start_date']
    return dict(**cardless_periodic_savings_data,
                user_id=new_valid_user['id'],
                plan_type_id=periodic_plan.id,
                interest_rate=7.0,
                transaction_status='SUCCESS',
                target_amount=70000,
                allow_interest=False,
                saved_amount=50000,
                start_date='2020-08-12 00:13:59+01',
                maturity_date='2020-08-12 00:13:59+01')


@pytest.fixture()
def running_periodic_savings(periodic_savings_data):
    '''Create a running periodic savings'''
    periodic_savings_data['saving_status'] = 'RUNNING'
    return Savings.objects.create(
        **periodic_savings_data
    )


@pytest.fixture()
def paid_periodic_savings(periodic_savings_data):
    '''Create a paid periodic savings'''
    periodic_savings_data['saving_status'] = 'PAID'
    return Savings.objects.create(
        **periodic_savings_data
    )


@pytest.fixture()
def create_savings(periodic_plan, valid_debit_card, new_valid_user):
    """ Create a savings """
    savings = Savings.objects.create(**{
        "user_id": new_valid_user['id'],
        "purpose": "Detty December",
        "target_amount": 0,
        "plan_type_id": periodic_plan.id,
        "transaction_ref": "a9bf3d28-0c37-4dfb-bd94-2a54aabe0e31",
        "transaction_status": "SUCCESS",
        "saving_status": "RUNNING",
        "interest_rate": "11.0",
        "card_id": valid_debit_card[1],
        "frequency": "DAILY",
        "frequency_amount": "2500000",
        "maturity_date": None,
        "allow_interest": False,
        "start_date": timezone.now() + timedelta(seconds=40),
        "saved_amount": "2500000"
    })
    return savings


@pytest.fixture()
def savings_update_details():
    return {
        "purpose": "Too much money",
        "frequency": "WEEKLY",
        "frequency_amount": "200000000"}


@pytest.fixture()
def admin_role_permission():
    permission_data = {
        "name": "Super Admin Permission",
        "allow_make_superadmin": True,
        "allow_ban_user": True,
        "allow_create_profile": True
    }
    return mixer.blend(AdminPermission, **permission_data)


@pytest.fixture()
def admin_role(admin_role_permission):
    role_data = {
        "name": "Super Admin",
        "role_permission": admin_role_permission,
    }
    return mixer.blend(AdminRole, **role_data)


@pytest.fixture()
def admin_user(admin_role):
    admin_data = {
        "username": "superadmin",
        'password': 'some_admin_password',
        "role": admin_role
    }
    admin = mixer.blend(Admin, **admin_data)
    admin_data['id'] = admin.id
    admin_data['first_name'] = admin.first_name
    admin_data['last_name'] = admin.last_name
    return admin_data


@mixer.middleware(Admin)
def encrypt_password(admin):
    admin.set_password('some_admin_password')
    return admin


@pytest.fixture()
def auth_header_admin(client, admin_user):
    response = client.post('/api/v1/admin/login',
                           data={
                               'username': admin_user['username'],
                               'password': admin_user['password']
                           })
    token = str(response.data["token"], 'utf-8')
    header = {"HTTP_AUTHORIZATION": 'Bearer ' + token}
    return header


@pytest.fixture()
def new_user_activity(admin_user):
    data = {
        'actor_id': admin_user['id'],
        'resource_url': '/api/v1/login',
        'payload': {'testing': 'testing'},
        'status': UserActionStatus.success,
        'actor_name': f"{admin_user['first_name']} {admin_user['last_name']}",
        'admin_viewable': True,
        'message': 'successfully logged in',
        'response': {"message": "Your login was successful", "status": 200},
        'action': "POST"
    }
    # UserActionsAudit.objects.create(**data)


@pytest.fixture()
def topup_savings_data(create_savings, valid_debit_card):
    return {
        "topup_amount": 1500000,
        "savings_id": create_savings.id,
        "card_id": valid_debit_card[1]
    }


@pytest.fixture()
def tudo_media(created_tudo):
    data = {"url": "http://testing1.com/image.png", "tudo": created_tudo}
    media = TudoMedia(**data)
    media.save()
    return media


@pytest.fixture()
def deleted_tudo_media(tudo_media):
    tudo_media.state = 'deleted'
    tudo_media.save()
    return tudo_media


@pytest.fixture()
def topup_savings(create_savings, new_valid_user):

    data = {
        'amount': 170000,
        'savings': create_savings,
        'reference': "p9nf3d28-0c37-4dfl-bd24-2a54aabe0e31",
        'status': 'Success',
        'user_id': new_valid_user['id']
    }

    topup = SavingsTransaction(**data)
    topup.save()
    return topup


@pytest.fixture()
def withdraw_savings(create_savings, new_valid_user,
                     added_bank_details_user_1):
    data = dict()
    data['amount'] = 10000
    data['savings'] = create_savings
    data['transaction_ref'] = "p9nf3d28-0c37-4dfl-bd24-2a54aabe0e31"
    data['bank'] = added_bank_details_user_1
    data['user_id'] = new_valid_user['id']

    withdrawal = SavingsWithdrawal(**data)
    withdrawal.save()
    return withdrawal


@pytest.fixture()
def topup_tudo(created_tudo):

    data = {
        'tudo_code': created_tudo,
        'contributor_name': 'Thanos',
        'contributor_email': 'Thanos@drstrange.com',
        'amount': 15000,
        'reference': "p9ng5h88-0c37-4dfl-bd24-2a54aabe0e31",
        'contribution_type': TudoContributionType.TOPUP,
        'status': 'Success'
    }

    topup = TudoContribution(**data)
    topup.save()
    return topup


@pytest.fixture()
def contribute_tudo(created_tudo):

    data = {
        'tudo_code': created_tudo,
        'contributor_name': 'Thanos',
        'contributor_email': 'Thanos@drstrange.com',
        'amount': 15000,
        'reference': "p9ng6970h88-0c37-4dfl-bd24-2a54aabe0e31",
        'contribution_type': TudoContributionType.USERCONTRIBUTION,
        'status': 'Success',
    }

    contribution = TudoContribution(**data)
    contribution.save()
    return contribution

from datetime import timedelta
from decimal import Decimal as D

import africastalking
from celery import shared_task
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from num2words import num2words

from userservice.models import Tudo, TudoMedia, User
from userservice.utils.helpers import (EmailSubjects, TudoStatus, send_email)
from userservice.utils.send_emails import SendEmail
from utils.constants import SUPPORT_EMAIL
from utils.enums import RewardPoints
from utils.helpers import MediaHandler, retrieve_from_redis, save_in_redis

FRONTEND_URL = settings.FRONTEND_URL

MIN_INACTIVE_DAYS = 7 * 2

MAX_INACTIVE_DAYS = 7 * 52

SKIPPED_DAYS = 7 * 2


def fetch_inactive_users():
    past_dates = []
    for day in range(MIN_INACTIVE_DAYS, MAX_INACTIVE_DAYS + 1, SKIPPED_DAYS):
        past_date = timezone.now().date() - timedelta(days=day)
        past_dates.append(past_date)
    user_contacts = User.objects.filter(last_login__date__in=past_dates).values_list(
        'id', 'first_name', 'email', 'last_login')
    return user_contacts


@shared_task(name='complete_expired_tudos')
def complete_expired_tudos():
    current_date = timezone.now()
    tudos = Tudo.objects.filter(status=TudoStatus.running.value,
                                completion_date__lte=current_date)
    for tudo in tudos:
        tudo.status = TudoStatus.completed.value
        tudo.save()
        goal_owner = tudo.user or tudo.business
        details = {
            'user_first_name': goal_owner.first_name or goal_owner.business_name,
            'tudo_goal_name': tudo.goal_name
        }
        send_tudo_expired_email.delay(user_email=goal_owner.email, details=details)


@shared_task(name='send_inactivity_reminder')
def send_inactivity_reminder():
    inactive_user_contacts = fetch_inactive_users()
    for contact in inactive_user_contacts:
        user_first_name = contact[1]
        user_email = contact[2]
        user_last_login = contact[3]

        number_of_days = (timezone.now() - user_last_login).days
        number_of_weeks = number_of_days // 7

        to_email = [user_email]
        inactivity_template = \
            'email_alerts/inactivity.html'
        subject = 'It’s been {} weeks! We miss you ☹️'.format(
            num2words(number_of_weeks)) if number_of_weeks > 1 else \
                 'It’s been {} week! We miss you ☹️'.format(
            num2words(number_of_weeks))
        context = {
            'user_first_name': user_first_name,
            'number_of_weeks': num2words(number_of_weeks),
            'domain': FRONTEND_URL,
        }
        send_mail = SendEmail(inactivity_template, context, subject, to_email)
        send_mail.send()


@shared_task(name='send_successful_user_invite_email')
def send_successful_user_invite_email(invitee_first_name, user_first_name, user_email,
                                      **kwargs):
    template = 'email_alerts/successful_invite.html'
    subject = EmailSubjects.successful_invite.value
    details = {
        'user_first_name': user_first_name,
        'invitee_first_name': invitee_first_name,
        'reward_points': RewardPoints.signup.value
    }

    send_custom_email(template, subject, user_email, details)


@shared_task(name='send_unsupported_country_email')
def send_unsupported_country_email(user_first_name, user_email, **kwargs):
    template = 'email_alerts/unsupported_country.html'
    subject = EmailSubjects.signup.value
    details = {'user_first_name': user_first_name}
    send_custom_email(template, subject, user_email, details)


@shared_task(name='send_successful_tudo_contribution_email')
def send_successful_tudo_contribution_email(contributor_name, contributor_email,
                                            user_first_name, user_email, **kwargs):
    receiver_template = 'email_alerts/successful_contribution_receiver.html'
    details = {
        'user_first_name': user_first_name,
        'contributor_name': contributor_name,
        'tudo_current_amount': D(kwargs['details']['tudo_current_amount']) / D(100),
        'tudo_target_amount': D(kwargs['details']['tudo_target_amount']) / D(100)
    }
    details.update(kwargs['details'])
    contributed_amount_in_naira = D(details['contributed_amount']) / D(100)
    subject = EmailSubjects.contribution_receiver.value.format(
        contributed_amount_in_naira)
    send_custom_email(receiver_template, subject, user_email, details)

    if contributor_email != 'xerde@xerdetech.com':
        sender_template = 'email_alerts/successful_contribution_sender.html'
        subject = EmailSubjects.contribution_sender.value
        send_custom_email(sender_template, subject, contributor_email, details)


@shared_task(name='send_successful_signup_email')
def send_successful_signup_email(user_first_name, user_email, **kwargs):
    template = 'email_alerts/successful_signup.html'
    details = {'user_first_name': user_first_name}
    subject = EmailSubjects.signup.value
    send_custom_email(template, subject, user_email, details)


@shared_task(name='send_tudo_goal_reached_email')
def send_tudo_goal_reached_email(user_first_name, user_email, **kwargs):
    template = 'email_alerts/tudo_goal_reached.html'
    details = {'user_first_name': user_first_name}
    subject = EmailSubjects.tudo_goal_reached.value
    send_custom_email(template, subject, user_email, details)


@shared_task(name='send_tudo_withdrawal_email')
def send_tudo_withdrawal_email(user_first_name, user_email, **kwargs):
    template = 'email_alerts/tudo_withdrawal.html'
    details = {'user_first_name': user_first_name}
    details.update(kwargs['details'])
    subject = EmailSubjects.withdrawal.value
    send_custom_email(template, subject, user_email, details)


@shared_task(name='send_new_tudo_list_email')
def send_new_tudo_list_email(user_first_name, user_email, **kwargs):
    template = 'email_alerts/new_tudo_list.html'
    details = {'user_first_name': user_first_name}
    details.update(kwargs['details'])
    subject = EmailSubjects.new_tudo_list.value
    send_custom_email(template, subject, user_email, details)


@shared_task(name='send_password_reset_email')
def send_password_reset_email(user_email, user_first_name, **kwargs):
    template = 'email_alerts/password_reset.html'
    details = {'user_first_name': user_first_name}
    details.update(kwargs['details'])
    subject = EmailSubjects.password_reset.value
    send_custom_email(template, subject, user_email, details)


@shared_task(name='send_tudo_expired_email')
def send_tudo_expired_email(user_email, **kwargs):
    template = 'email_alerts/tudo_expired.html'
    subject = EmailSubjects.tudo_expired.value
    details = kwargs['details']
    send_custom_email(template, subject, user_email, details)


@shared_task(name='send_email_async')
def send_email_async(*args, **kwargs):
    return send_email(*args, **kwargs)


@shared_task(name='send_sms_async')
def send_sms_async(*args, **kwargs):
    africastalking.initialize(settings.SMS_GATEWAY_USERNAME, settings.SMS_GATEWAY_TOKEN)
    sms = africastalking.SMS
    response = sms.send("<#> Your Tudo verification code is: " + args[1] +
                        f'\n{settings.MOBILE_APP_ID}', [args[0]],
                        sender_id=settings.SMS_GATEWAY_SENDER_ID)
    return [
        dict(number=rep['number'], status=rep['status'])
        for rep in response['SMSMessageData']['Recipients']
    ]


@shared_task(name='send_custom_email')
def send_custom_email(template, subject, recipient_email, details):
    to_email = [recipient_email]
    context = {
        'domain': FRONTEND_URL,
    }
    context.update(details)
    send_mail = SendEmail(template, context, subject, to_email)
    return send_mail.send()


@shared_task(name='log_interest_compute')
def log_interest_compute(data):
    task_id = log_interest_compute.request.id
    data.update({'task_id': task_id})
    background_actions = retrieve_from_redis('background_actions')
    if background_actions is None:
        background_actions = [].append(data)
        return save_in_redis('background_actions', background_actions)
    save_in_redis('background_actions', background_actions.update(data))


@shared_task(name='scheduled_saving_success_email')
def send_scheduled_saving_success_email(user_email, user_first_name, **kwargs):
    template = 'email_alerts/successful_scheduled_savings_charge.html'
    details = {'user_first_name': user_first_name}
    details.update(kwargs['details'])
    subject = EmailSubjects.scheduled_saving_success.value
    send_custom_email(template, subject, user_email, details)


@shared_task(name='scheduled_saving_failure_email')
def send_scheduled_saving_failure_email(user_email, user_first_name, **kwargs):
    template = 'email_alerts/failed_scheduled_savings_charge.html'
    details = {'user_first_name': user_first_name}
    details.update(kwargs['details'])
    subject = EmailSubjects.scheduled_saving_failure.value
    send_custom_email(template, subject, user_email, details)


@shared_task(name='send_application_support_email')
def send_application_support_email(**kwargs):
    return send_mail(f"#Support - {kwargs.get('subject')}",
                     kwargs.get('message'),
                     f"{kwargs.get('full_name')} <{kwargs.get('email')}>",
                     [SUPPORT_EMAIL],
                     fail_silently=False)


@shared_task(name='send_grouped_tudo_invite_email_for_unregistered_users')
def send_grouped_tudo_invite_email_for_unregistered_users(**kwargs):
    """ Sends an email to a registered user to notify about a group Tudo invite.
    """
    template = 'email_alerts/group_tudo_templates/invite_unregistered_users.html'
    subject = EmailSubjects.grouped_tudo_invite.value
    goal_id = kwargs.get('goal_id')
    notification_data = kwargs.get('notification_data')
    details = {
        'inviter': kwargs.get('inviter'),
        'goal_id': goal_id,
        'goal_name': kwargs.get('goal_name'),
        "email_list": kwargs.get('email_list'),
        'goal_target': kwargs.get("goal_target"),
        'goal_currency': kwargs.get('goal_currency'),
        'goal_duration': kwargs.get('goal_duration'),
        'accept_link': f"{FRONTEND_URL}/signup/personal",
    }

    for to_email in kwargs.get('email_list'):
        ttl = ((timezone.now() + relativedelta(days=7)) - timezone.now()).seconds
        save_in_redis(f"pending-group-invite-{to_email}",
                      dict(goal_id=goal_id, notification_data=notification_data),
                      timeout=ttl)
        send_custom_email(template, subject, to_email, details)


@shared_task(name='send_grouped_tudo_invite_email_for_registered_users')
def send_grouped_tudo_invite_email_for_registered_users(**kwargs):
    """ Sends an email to a registered user to notify about a group Tudo invite.
    """
    template = 'email_alerts/group_tudo_templates/invite_registered_users.html'
    subject = EmailSubjects.grouped_tudo_invite.value
    inviter = kwargs.get('inviter')
    member_list = kwargs.get('member_list')
    member_count = kwargs.get('member_count') - 1
    goal_name = kwargs.get('goal_name')
    goal_target = kwargs.get('goal_target')
    goal_currency = kwargs.get('goal_currency')
    goal_duration = kwargs.get('goal_duration')
    goal_id = kwargs.get('goal_id')

    for invitee in member_list:
        ttl = ((timezone.now() + relativedelta(days=7)) - timezone.now()).seconds
        save_in_redis(f"notification-{goal_id}-{invitee['email']}",
                      dict(is_registered=True,
                           creator_name=inviter,
                           group_name=goal_name),
                      timeout=ttl)
        details = {
            'inviter': inviter,
            'goal_name': goal_name,
            'member_count': member_count,
            'member_list': member_list,
            'goal_target': goal_target,
            'goal_currency': goal_currency,
            'goal_duration': goal_duration,
            'accept_link':
            f"{FRONTEND_URL}/dashboard?entity=notification&id={goal_id}&resp=accept",
            'reject_link':
            f"{FRONTEND_URL}/dashboard?entity=notification&id={goal_id}&resp=reject"
        }
        details.update(invitee)
        send_custom_email(template, subject, invitee['email'], details)


@shared_task(name='send_grouped_tudo_acceptance_email')
def send_grouped_tudo_acceptance_email(invitee_first_name, user_first_name, user_email,
                                       **kwargs):
    """ Sends an email to the creator of a grouped Tudo to notify
    about an invite acceptance.
    """
    template = 'email_alerts/grouped_tudo_invite_acceptance.html'
    subject = EmailSubjects.grouped_tudo_invite_acceptance.value
    details = {
        'user_first_name': user_first_name,
        'invitee_first_name': invitee_first_name
    }
    details.update(kwargs['details'])
    send_custom_email(template, subject, user_email, details)


@shared_task(name='upload_tudo_media_to_bucket')
def upload_tudo_media_to_bucket(image_data, filename, id, **kwarg):
    img_url = MediaHandler.upload_raw(image_data, filename)
    instance = TudoMedia.objects.filter(id=id).first()
    if instance:
        instance.update(url=img_url)
        return f"Uploaded {img_url} successfully and updated {instance}"
    return None


@shared_task(name='send_verification_email')
def send_verification_email(**kwargs):
    """ Send verification code email to users """
    template = 'email_alerts/verification_code.html'
    subject = EmailSubjects.verfication_code.value
    user_email = kwargs.get('user_email')
    full_name = kwargs.get('full_name')
    otp = kwargs.get('otp')
    details = {
        'full_name': full_name,
        'otp': otp
    }
    send_custom_email(template, subject, user_email, details)

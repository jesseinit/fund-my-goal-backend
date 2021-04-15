from django.db import transaction
from django.db.models import F
from fcm_django.models import FCMDevice
from userservice.models import (
    Notification, Rewards, Tudo, TudoContribution, User)
from userservice.tasks import (send_successful_tudo_contribution_email,
                               send_tudo_goal_reached_email)
from userservice.utils.helpers import (
    TransactionStatus, TudoContributionType, TudoStatus)

from utils.constants import (REWARDTYPES, GOAL_CONTRIB_NOTIF_TEXT,
                             GOAL_COMPLETION_NOTIF_TEXT, REWARD_GOAL_CONTRIB_TEXT, REWARD_GOAL_TOPUP_TEXT)
from utils.enums import RewardPoints
from utils.helpers import parse_user_type


class TransactionHandler:

    @classmethod
    def process_tudo_contribution(cls, data):
        tudo = Tudo.objects.filter(
            share_code=data['metadata']['tudo_code']).first()

        if tudo and tudo.status == str(TudoStatus.processing_withdrawal):
            return False
        try:
            with transaction.atomic():
                Tudo.objects.filter(
                    share_code=data['metadata']['tudo_code']).update(
                        amount_generated=F('amount_generated') + data['amount'])

                tudo = Tudo.objects.get(
                    share_code=data['metadata']['tudo_code'])

                contribution = TudoContribution.objects.create(
                    contributor_email=data['metadata']['contributor_email'],
                    contributor_name=data['metadata']['contributor_name'],
                    amount=data['amount'],
                    status=TransactionStatus.SUCCESS.value,
                    reference=data['reference'],
                    tudo_code=tudo,
                    currency=tudo.currency)

                details = {
                    "contributed_amount": contribution.amount,
                    "tudo_current_amount": tudo.amount_generated,
                    "tudo_target_amount": tudo.amount,
                    "currency": tudo.currency
                }

                is_tudo_completed = tudo.amount_generated >= tudo.amount
                user = tudo.user or tudo.business
                account_type = parse_user_type(user)
                field_opts = dict(personal=dict(user=user),
                                  business=dict(business=user))[account_type]
                if is_tudo_completed:
                    tudo.status = TudoStatus.completed.value
                    Notification.objects.create(
                        summary="Tudo goal reached notification",
                        notification_text=GOAL_COMPLETION_NOTIF_TEXT.substitute(
                            first_name=user.first_name, goal_name=tudo.goal_name),
                        actor_name=user.first_name,
                        **field_opts)

                    send_tudo_goal_reached_email.delay(
                        user_first_name=user.first_name,
                        user_email=user.email
                    )
                    if account_type == 'personal':
                        device = FCMDevice.objects.filter(user=user).first()
                        if device:
                            device.send_message(
                                title="Goal Smashed",
                                body=GOAL_COMPLETION_NOTIF_TEXT.substitute(
                                    first_name=user.first_name, goal_name=tudo.goal_name))
                    tudo.save()
                else:
                    # Dispatch an email to the user
                    send_successful_tudo_contribution_email.delay(
                        contributor_name=contribution.contributor_name,
                        contributor_email=contribution.contributor_email,
                        user_first_name=user.first_name,
                        user_email=user.email,
                        details=details
                    )

                    # Create a new notification message
                    Notification.objects.create(
                        **field_opts,
                        summary="Tudo contribution notification",
                        triggered_by=None,
                        notification_text=f"Hello {user.first_name}, \
                            N{contribution.amount / 100} was contributed by \
                            {contribution.contributor_name} to your tudo \
                            account for '{tudo.goal_name}', cheers!🎉",
                        actor_name=contribution.contributor_name)

                    # The rest of the logic below belongs to personal accounts only
                    if account_type == 'personal':
                        device = FCMDevice.objects.filter(
                            user=user).order_by('-date_created').first()
                        if device:
                            device.send_message(
                                data=dict(goal_id=tudo.id, goal_type="personal"),
                                title="Goal Contribution Recieved",
                                body=GOAL_CONTRIB_NOTIF_TEXT.substitute(
                                    first_name=user.first_name,
                                    amount=contribution.amount / 100,
                                    contributor_name=contribution.contributor_name,
                                    goal_name=tudo.goal_name))

                        count_successful_contributions = TudoContribution.objects.filter(
                            tudo_code__user=user,
                            status__iexact=TransactionStatus.SUCCESS.value
                        ).count()

                        if count_successful_contributions == 1:
                            inviter = User.objects.filter(
                                id=user.invited_by).first()
                            if inviter:
                                inviter.points = (
                                    F("points") + RewardPoints.goal_creation.value)
                                inviter.save()
                                rewards_data = {
                                    'inviter': inviter,
                                    'invitee': user,
                                    'type': REWARDTYPES[2][0],
                                    'points': RewardPoints.savings_topup.value
                                }
                                Rewards(**rewards_data).save()
                                # Todo - Send notification to inviter
                                inviter_device = FCMDevice.objects.filter(
                                    user=inviter).order_by('-date_created').first()
                                if inviter_device:
                                    inviter_device.send_message(
                                        title=f"{RewardPoints.goal_creation.value} Reward Point(s) Received",
                                        body=REWARD_GOAL_CONTRIB_TEXT.substitute(
                                            points=RewardPoints.goal_creation.value,
                                            invitee_name=user.first_name))
            return True
        except (TudoContribution.DoesNotExist, Tudo.DoesNotExist):
            return False

    @ classmethod
    def process_tudo_topup(cls, data):
        """ Method to process personal or business goal top-ups """
        tudo = Tudo.objects.get(
            id=data['metadata']['tudo_id'])
        if tudo.status == str(TudoStatus.processing_withdrawal):
            return False
        with transaction.atomic():
            Tudo.objects.filter(id=data['metadata']['tudo_id']).update(
                amount_generated=F('amount_generated') + data['amount'])
            tudo = Tudo.objects.filter(id=data['metadata']['tudo_id']).first()
            user = tudo.user or tudo.business_account
            account_type = parse_user_type(user)
            contribution = TudoContribution.objects.create(
                contributor_name='Self TopUp',
                contributor_email=data['metadata']['contributor_name'],
                amount=data['amount'],
                status=TransactionStatus.SUCCESS.value,
                contribution_type=TudoContributionType.TOPUP,
                tudo_code=tudo,
                reference=data['reference'])

            if tudo.amount_generated >= tudo.amount:
                Notification.objects.create(
                    user_id=user.id,
                    summary="Tudo goal reached notification",
                    notification_text=f"Congratulations!🎉 {user.first_name}, your goal '{tudo.goal_name}' has been achieved, cheers!🎉",
                    actor_name=user.first_name)
                tudo.update(status=TudoStatus.completed.value)

            # Check to accertain if this is the first contribution on the goal
            count_successful_contributions = TudoContribution.objects.filter(
                tudo_code__user=user,
                status__iexact=TransactionStatus.SUCCESS.value
            ).count()

            device = None
            if account_type == 'personal':
                device = FCMDevice.objects.filter(
                    user=user).order_by('-date_created').first()
                if device:
                    device.send_message(
                        data=dict(goal_id=tudo.id, goal_type="personal"),
                        title="Goal Top-Up was Successful",
                        body=GOAL_CONTRIB_NOTIF_TEXT.substitute(
                            first_name=user.first_name,
                            amount=contribution.amount / 100,
                            contributor_name=contribution.contributor_name,
                            goal_name=tudo.goal_name))

                if count_successful_contributions == 1:
                    inviter = User.objects.filter(id=user.invited_by).first()
                    # Reward inviter with some redeemable reward points
                    if inviter:
                        inviter.update(
                            points=F("points") + RewardPoints.savings_topup.value)
                        Rewards(**{
                            'inviter': inviter,
                            'invitee': user,
                            'type': REWARDTYPES[1][0],
                            'points': RewardPoints.savings_topup.value
                        }).save()
                        inviter_device = FCMDevice.objects.filter(
                            user=inviter).order_by('-date_created').first()
                        if inviter_device:
                            inviter_device.send_message(
                                title=f"{RewardPoints.savings_topup.value} Reward Point(s) Received",
                                body=REWARD_GOAL_TOPUP_TEXT.substitute(
                                    points=RewardPoints.goal_creation.value,
                                    invitee_name=user.first_name))
        return True

from django.shortcuts import render

# Create your views here.
from rest_framework import mixins, viewsets


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

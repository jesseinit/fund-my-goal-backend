from django.shortcuts import render

# Create your views here.


class GoalViewset(viewsets.ViewSet):

    serializer_class = GoalSerializer

    def create(self, request):
        serializer = self.serializer_class(data=request.data,
                                           context={"request": request})
        if not serializer.is_valid():
            return format_response(
                error=serializer.errors.get("tudos").get("errors", serializer.errors),
                status=HTTP_400_BAD_REQUEST,
            )

        user = request.user
        user_first_name = user.first_name
        user_email = user.email
        send_new_tudo_list_email.delay(
            user_first_name=user_first_name,
            user_email=user_email,
            details={"tudo_list": serializer.data["tudos"]},
        )
        actor_name = f"{user.first_name} {user.last_name}"
        return format_response(
            data=serializer.data,
            message="You've successfully created a Goal list",
            log="successfully created a Goal list",
            actor_name=actor_name,
            status=HTTP_201_CREATED,
        )

    def partial_update(self, request, pk):
        if not request.data:
            return format_response(error="Provide fields to be updated",
                                   status=HTTP_400_BAD_REQUEST)
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]
        tudo = Goal.tudo_status.running().filter(pk=pk, **field_opts).first()
        if not tudo:
            return format_response(error="Goal does not exist",
                                   status=HTTP_404_NOT_FOUND)

        serializer = GoalModelSerializer(
            tudo,
            data=request.data,
            partial=True,
            context={
                "user_type": user_type,
                "user": {
                    **field_opts
                }
            },
        )

        if not serializer.is_valid():
            return format_response(error=serializer.errors, status=HTTP_400_BAD_REQUEST)
        serializer.save()
        actor_name = f"{user.first_name} {user.last_name}"

        return format_response(
            data=serializer.data,
            status=HTTP_200_OK,
        )

    def list(self, request):
        tudos_type = request.query_params.get("type")
        user = request.user
        category = request.query_params.get("category", ".+")

        if tudos_type and tudos_type in ["running", "completed", "paid"]:
            if tudos_type == "running":
                tudos = Goal.tudo_status.running
            elif tudos_type == "completed":
                tudos = Goal.tudo_status.completed
            elif tudos_type == "paid":
                tudos = Goal.tudo_status.paid
            tudos_by_category = tudos().filter(
                category__category__iregex=r"^{}$".format(category))
            tudos = get_tudos(request, tudos_by_category, tudos_type)
            return tudos

        query = request.query_params.get("query")
        if query:
            return search_tudos(request, query, parse_query_params(request))

        paginator = CustomPaginator(url_suffix="api/v1/tudo")
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]

        user_tudos = Goal.objects.filter(**field_opts)

        tudos = paginator.paginate_queryset(
            user_tudos.filter(category__category__iregex=r"^{}$".format(category)),
            request,
        )

        serializer = GoalModelSerializer(tudos, many=True)
        actor_name = f"{user.first_name} {user.last_name}"
        return paginator.get_paginated_response(
            data=serializer.data,
            message="Goals retrieved successfully",
            log="successfully retrieved all Goals",
            actor_name=actor_name,
            status=HTTP_200_OK,
        )

    def retrieve(self, request, pk=None):
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]
        tudo = Goal.objects.filter(pk=pk, **field_opts).first()
        if tudo is None:
            return format_response(error="This goal was not found",
                                   status=HTTP_404_NOT_FOUND)

        serializer = GoalModelSerializer(tudo)
        approved_tudo_contributions = GoalContribution.objects.filter(
            tudo_code=tudo.share_code, status=TransactionStatus.SUCCESS.value)

        transactions = GoalTransactionSerializer(approved_tudo_contributions, many=True)
        data = serializer.data
        data["transactions"] = transactions.data

        actor_name = f"{user.first_name} {user.last_name}"
        return format_response(
            data=data,
            message="Goal retrieved successfully",
            log=f"successfully retrieved {tudo.goal_name} Goal",
            actor_name=actor_name,
            status=HTTP_200_OK,
        )

    def destroy(self, request, pk=None):
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]

        tudo = Goal.objects.filter(pk=pk, **field_opts).first()
        if not tudo:
            return format_response(error="This Goal does not exist",
                                   status=HTTP_404_NOT_FOUND)

        if tudo.amount_generated == 0:
            tudo.state = StateType.deleted.value
            tudo.save()
            actor_name = f"{user.first_name} {user.last_name}"
            return format_response(
                message="Successfully deleted Goal",
                log=f"successfully deleted {tudo.goal_name} Goal",
                actor_name=actor_name,
                status=HTTP_200_OK,
            )
        else:
            return format_response(
                error="You cannot delete a tudo that has been funded",
                status=HTTP_400_BAD_REQUEST,
            )


class TrendingGoalsViewset(mixins.ListModelMixin, viewsets.GenericViewSet):
    """View to add bank details for a user"""

    authentication_classes = [AllowAnyUser]
    permission_classes = [AllowAny]

    def list(self, request):
        paginator = CustomPaginator(url_suffix="api/v1/tudo/trending")
        trending_tudos = paginator.paginate_queryset(
            Goal.objects.get_all(),
            request,
        )

        serialized_trending_tudos = TrendingGoalSerializer(
            trending_tudos,
            many=True,
            context={
                "user": request.user,
                "is_authenticated":
                True if request.user.is_authenticated is True else False,
            },
        )
        return paginator.get_paginated_response(
            data=serialized_trending_tudos.data,
            query_params=parse_query_params(request),
            status=HTTP_200_OK,
        )


class LikeGoalViewset(viewsets.ViewSet):
    """ Viewset that handles liking and un-liking a tudo """

    lookup_field = "tudo_id"
    authentication_classes = [
        AllowAnyUser,
    ]
    permission_classes = [
        AllowListRetrieveOnly,
    ]

    def create(self, request):
        if "tudo_id" not in request.data.keys():
            return format_response(error=dict(tudo_id=["Please enter a tudo id"]),
                                   status=400)
        tudo_id = request.data["tudo_id"]
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]

        tudo = Goal.objects.filter(id=tudo_id).first()

        if not tudo:
            return format_response(error=dict(tudo_id=["Goal goal not found"]),
                                   status=HTTP_404_NOT_FOUND)

        liked_tudo = GoalLikes.objects.filter(tudo=tudo, **field_opts).first()

        if liked_tudo and liked_tudo.like_status == LIKE_STATUS[0][0]:
            liked_tudo.like_status = LIKE_STATUS[1][0]
            liked_tudo.save()
            likes_count = GoalLikes.objects.filter(
                tudo=tudo, like_status=LIKE_STATUS[0][0]).count()
            return format_response(
                data=dict(tudo_id=tudo.id, likes_count=likes_count, action="unliked"),
                status=HTTP_200_OK,
            )
        elif liked_tudo and liked_tudo.like_status == LIKE_STATUS[1][0]:
            liked_tudo.like_status = LIKE_STATUS[0][0]
            liked_tudo.save()
            likes_count = GoalLikes.objects.filter(
                tudo=tudo, like_status=LIKE_STATUS[0][0]).count()
            return format_response(
                data=dict(tudo_id=tudo.id, likes_count=likes_count, action="liked"),
                status=HTTP_200_OK,
            )

        GoalLikes.objects.create(tudo=tudo, like_status=LIKE_STATUS[0][0], **field_opts)

        likes_count = GoalLikes.objects.filter(tudo=tudo,
                                               like_status=LIKE_STATUS[0][0]).count()

        return format_response(
            data=dict(tudo_id=tudo.id, likes_count=likes_count, action="liked"),
            status=HTTP_201_CREATED,
        )

    def retrieve(self, request, tudo_id):

        tudo_likes = GoalLikes.objects.filter(tudo_id=tudo_id,
                                              like_status=LIKE_STATUS[0][0])
        paginator = CustomPaginator(url_suffix="api/v1/tudo/likes", page_size=10)
        likes = paginator.paginate_queryset(tudo_likes, request)
        likes = GoalLikesSerializer(likes, many=True)
        return paginator.get_paginated_response(data=likes.data, status=HTTP_200_OK)


class FollowGoalViewset(viewsets.ViewSet):
    """ Viewset that handles following and un-following a tudo """

    def create(self, request):
        if "tudo_id" not in request.data.keys():
            return format_response(error=dict(tudo_id=["Please enter a tudo id"]),
                                   status=400)
        tudo_id = request.data["tudo_id"]
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]

        tudo = Goal.objects.filter(id=tudo_id).first()
        if not tudo:
            return format_response(error=dict(tudo_id=["Goal goal not found"]),
                                   status=HTTP_404_NOT_FOUND)

        followed_tudo = GoalFollowers.objects.filter(tudo=tudo, **field_opts).first()

        if followed_tudo and followed_tudo.follow_status == FOLLOWING_STATUS[0][0]:
            followed_tudo.follow_status = FOLLOWING_STATUS[1][0]
            followed_tudo.save()
            follower_count = GoalFollowers.objects.filter(
                tudo=tudo, follow_status=FOLLOWING_STATUS[0][0]).count()
            return format_response(
                data=dict(tudo_id=tudo.id,
                          follower_count=follower_count,
                          action="unfollowed"),
                status=HTTP_200_OK,
            )

        elif followed_tudo and followed_tudo.follow_status == FOLLOWING_STATUS[1][0]:
            followed_tudo.follow_status = FOLLOWING_STATUS[0][0]
            followed_tudo.save()
            follower_count = GoalFollowers.objects.filter(
                tudo=tudo, follow_status=FOLLOWING_STATUS[0][0]).count()
            return format_response(
                data=dict(tudo_id=tudo.id,
                          follower_count=follower_count,
                          action="followed"),
                status=HTTP_200_OK,
            )

        GoalFollowers.objects.create(tudo=tudo,
                                     follow_status=FOLLOWING_STATUS[0][0],
                                     **field_opts)
        follower_count = GoalFollowers.objects.filter(
            tudo=tudo, follow_status=FOLLOWING_STATUS[0][0]).count()

        return format_response(
            data=dict(tudo_id=tudo.id, follower_count=follower_count, action="followed"),
            status=HTTP_201_CREATED,
        )


class CommentGoalViewset(viewsets.ViewSet):
    """ Viewset to manage coments """

    authentication_classes = [
        AllowAnyUser,
    ]
    permission_classes = [
        AllowListRetrieveOnly,
    ]
    serializer_class = GoalCommentSerializer
    lookup_field = "tudo_id"

    def create(self, request):
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]
        serializer = self.serializer_class(data=request.data,
                                           context={"user": {
                                               **field_opts
                                           }})
        if not serializer.is_valid():
            return format_response(
                error=serializer.errors.get("error", serializer.errors),
                status=HTTP_400_BAD_REQUEST,
            )
        serializer.save()
        return format_response(data=serializer.data, status=HTTP_201_CREATED)

    def retrieve(self, request, tudo_id):
        """ Retrieve Goal Comments """
        comments_queryset = GoalComments.objects.filter(tudo_id=tudo_id)
        paginator = CustomPaginator(url_suffix="api/v1/tudo/comment", page_size=10)
        comment_paginated_qs = paginator.paginate_queryset(comments_queryset, request)
        comments = GoalCommentListSerializer(comment_paginated_qs, many=True)
        return paginator.get_paginated_response(data=comments.data, status=HTTP_200_OK)


class SearchGoalViewset(mixins.ListModelMixin, viewsets.GenericViewSet):
    filter_backends = (filters.DjangoFilterBackend, )
    filterset_class = GoalSearchFilter
    serializer_class = GoalModelSerializer
    authentication_classes = [AllowAnyUser]
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = Goal.objects.filter(is_visible=True)
        tudos = GoalSearchFilter(self.request.GET, queryset=qs)
        return tudos.qs

    def list(self, request):
        qs = self.filter_queryset(self.get_queryset())
        paginator = CustomPaginator(url_suffix="api/v1/tudo/search")
        tudos = paginator.paginate_queryset(qs, request)
        serialized_tudos = self.serializer_class(tudos, many=True, context={
            "user": request.user,
            "is_authenticated": True if request.user.is_authenticated is True else False,
        })
        return paginator.get_paginated_response(data=serialized_tudos.data,
                                                query_params=parse_query_params(request))


class GoalMediaViewset(viewsets.ViewSet):
    def create(self, request):
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]
        data = request.data
        media = data.get("media")

        if not media or not isinstance(media, list):
            return format_response(error="media key missing or media list is empty")

        serializer = GoalMediaSerializer(data=data,
                                         context={
                                             "tudo_id": data.get("tudo_id"),
                                             "user": {
                                                 **field_opts
                                             }
                                         })

        if not serializer.is_valid():
            return format_response(
                error=serializer.errors.get("errors", serializer.errors),
                status=HTTP_400_BAD_REQUEST,
            )

        media_data = serializer.save()
        return format_response(data=media_data, status=HTTP_201_CREATED)

    def retrieve(self, request, pk):
        tudo_media = GoalMedia.objects.filter(id=pk).first()

        if not tudo_media:
            return format_response(error="Media file not found",
                                   status=HTTP_404_NOT_FOUND)

        serializer = GoalMediaModelSerializer(tudo_media)

        return format_response(data=serializer.data, status=HTTP_200_OK)

    def list(self, request):
        tudo_id = request.query_params.get("tudo_id", None)
        if not tudo_id:
            return format_response(error="tudo_id parameter not specified",
                                   status=HTTP_400_BAD_REQUEST)

        tudo_media = GoalMedia.objects.filter(tudo__id=tudo_id)

        serializer = GoalMediaModelSerializer(tudo_media, many=True)

        return format_response(data=serializer.data, status=HTTP_200_OK)

    def destroy(self, request, pk):
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(tudo__user=user),
                          business=dict(tudo__business=user))[user_type]

        tudo_media = GoalMedia.objects.filter(id=pk, **field_opts).first()

        if not tudo_media:
            return format_response(error="Media file not found",
                                   status=HTTP_404_NOT_FOUND)

        tudo_media.state = StateType.deleted.value
        tudo_media.save()

        return format_response(message="Media file deleted", status=HTTP_200_OK)


class GoalTransactionsViewset(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    def retrieve(self, request, pk):
        user = request.user
        transaction_type = request.query_params.get("type", "all").lower()
        if transaction_type == "contributions":
            contributions = GoalContribution.objects.filter(
                tudo_code__id=pk,
                tudo_code__user=user,
                contribution_type=GoalContributionType.USERCONTRIBUTION,
            )
            withdrawals = GoalWithdrawal.objects.none()
        elif transaction_type == "topups":
            contributions = GoalContribution.objects.filter(
                tudo_code__id=pk,
                tudo_code__user=user,
                contribution_type=GoalContributionType.TOPUP,
            )
            withdrawals = GoalWithdrawal.objects.none()
        elif transaction_type == "withdrawals":
            contributions = GoalContribution.objects.none()
            withdrawals = GoalWithdrawal.objects.filter(tudo__id=pk, user=user)
        elif transaction_type == "all":
            contributions = GoalContribution.objects.filter(tudo_code__id=pk,
                                                            tudo_code__user=user)
            withdrawals = GoalWithdrawal.objects.filter(tudo__id=pk, user=user)
        else:
            contributions = GoalContribution.objects.none()
            withdrawals = GoalWithdrawal.objects.none()

        if request.query_params.get("sort", None) == "-date":
            descending_date = True
        else:
            descending_date = False

        all_transactions = sorted(
            chain(contributions, withdrawals),
            key=lambda x: x.created_at,
            reverse=descending_date,
        )

        paginator = CustomPaginator(url_suffix=f"api/v1/tudo/transactions/{pk}")
        paginated_transactions = paginator.paginate_queryset(all_transactions, request)
        serializer = GoalTransactionsSerializer(paginated_transactions, many=True)

        return paginator.get_paginated_response(
            data=serializer.data,
            query_params=parse_query_params(request),
            message="Goal transactions retrieved successfully",
            status=HTTP_200_OK,
        )


class WithdrawGoalViewset(viewsets.ViewSet):

    serializer_class = WithdrawGoalSerializer

    @classmethod
    def set_tudo_status(cls, tudo, transaction_status):
        if (timezone.now().date() < tudo.completion_date.date()
                and tudo.amount_generated < tudo.amount):
            tudo.status = GoalStatus.running.value
        elif transaction_status == TransactionStatus.SUCCESS:
            tudo.status = GoalStatus.paid.value
        elif transaction_status == TransactionStatus.FAILED:
            tudo.status = GoalStatus.completed.value
        return tudo

    @classmethod
    def reverse_transaction(cls, tudo_id, user, transaction_status):
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]
        tudo = Goal.objects.filter(id=tudo_id,
                                   status=GoalStatus.processing_withdrawal.value,
                                   **field_opts).first()
        WithdrawGoalViewset.set_tudo_status(tudo, transaction_status).save()

    def create(self, request):
        withdraw_details = request.data
        serializer = self.serializer_class(
            data=withdraw_details,
            context={
                "user_type": parse_user_type(request.user),
                "user": request.user
            },
        )
        if not serializer.is_valid():
            return format_response(error=serializer.errors, status=HTTP_400_BAD_REQUEST)
        user = request.user
        user_type = parse_user_type(user)
        field_opts = dict(personal=dict(user=user),
                          business=dict(business=user))[user_type]

        tudo_id = serializer.data["tudo_id"]
        bank_account_id = serializer.data["bank_account_id"]

        tudo_locked = Goal.objects.filter(
            id=tudo_id, **field_opts, status=GoalStatus.completed.value).update(
                status=GoalStatus.processing_withdrawal.value)
        if not tudo_locked:
            return format_response(error="Withdrawal in progress",
                                   status=HTTP_400_BAD_REQUEST)

        tudo_to_withdraw = Goal.objects.filter(
            id=tudo_id, status=GoalStatus.processing_withdrawal.value,
            **field_opts).first()

        amount_withdrawable_kobo = (tudo_to_withdraw.amount_generated -
                                    tudo_to_withdraw.amount_withdrawn)

        if amount_withdrawable_kobo < 10000:
            self.reverse_transaction(tudo_id, request.user, TransactionStatus.FAILED)
            return format_response(
                error="Cannot withdraw amount less than NGN100",
                status=HTTP_400_BAD_REQUEST,
            )

        service_charge_kobo = amount_withdrawable_kobo * SERVICE_RATE
        amount_to_withdraw_kobo = amount_withdrawable_kobo - service_charge_kobo

        bank_account = BankAccount.objects.filter(
            id=bank_account_id, **field_opts).first()

        account_number = bank_account.account_number
        bank_code = bank_account.bank_code
        reference = "xerde-" + str(uuid.uuid4())[:14] + str(int(time.time()))
        transfer_response = BankingApi.transfer_money(
            amount=amount_to_withdraw_kobo / 100,
            account_number=account_number,
            bank_code=bank_code,
            transfer_type="inter",
            transaction_reference=reference,
            remark="{} Goal Withdrawal".format(tudo_to_withdraw.goal_name),
        )

        if transfer_response.get("status") is True:
            tudo = Goal.objects.filter(id=tudo_id, **field_opts).first()
            tudo.amount_withdrawn = F("amount_withdrawn") + amount_withdrawable_kobo

            WithdrawGoalViewset.set_tudo_status(tudo, TransactionStatus.SUCCESS).save()
            GoalWithdrawal.objects.create(
                reference=reference,
                tudo=tudo_to_withdraw,
                bank_id=bank_account_id,
                amount=amount_to_withdraw_kobo,
                service_charge=service_charge_kobo,
                currency=tudo_to_withdraw.currency,
                **field_opts,
            )

            details = {
                "goal_name": tudo_to_withdraw.goal_name,
                "currency": tudo_to_withdraw.currency,
                "amount_generated": tudo_to_withdraw.amount_generated,
                "net_amt_withdrawn": amount_to_withdraw_kobo,
                "withdrawn_amount": amount_withdrawable_kobo,
                "service_charge": service_charge_kobo,
                "destination_bank_name": bank_account.bank_name,
                "charge_rate": round(SERVICE_RATE * 100),
                "destination_account_number": bank_account.account_number,
            }

            if tudo_to_withdraw.user:
                send_tudo_withdrawal_email.delay(
                    user_first_name=tudo_to_withdraw.user.first_name,
                    user_email=tudo_to_withdraw.user.email,
                    details=details,
                )
                actor_name = f"{user.first_name} {user.last_name}"

            elif tudo_to_withdraw.business:
                send_tudo_withdrawal_email.delay(
                    user_first_name=tudo_to_withdraw.business.business_name,
                    user_email=tudo_to_withdraw.business.email,
                    details=details,
                )
                actor_name = f"{tudo_to_withdraw.business.business_name}"

            return format_response(
                data={
                    "target_amount": tudo_to_withdraw.amount,
                    "amount_generated": tudo_to_withdraw.amount_generated,
                    "amount_withdrawable": amount_withdrawable_kobo,  # GROSS
                    "net_amt_withdrawn": amount_to_withdraw_kobo,  # NET
                    "service_charge": service_charge_kobo,
                },
                message="Withdrawal successful",
                log=f"Successfully withdraws from {tudo_to_withdraw.goal_name} Goal",
                actor_name=actor_name,
                status=HTTP_200_OK,
            )

        self.reverse_transaction(tudo_id, request.user, TransactionStatus.FAILED)

        return format_response(error="Unable to complete transaction",
                               status=HTTP_503_SERVICE_UNAVAILABLE)


class GoalContributionViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    permission_classes = ()
    authentication_classes = ()
    serializer_class = GoalContributionSerializer

    def create(self, request):
        contribution = request.data
        if contribution.get("tudo_code"):
            tudo_instance = Goal.objects.filter(
                share_code=contribution["tudo_code"]).first()
            if not tudo_instance:
                return format_response(error={"tudo_code": ["Goal not found"]},
                                       status=HTTP_404_NOT_FOUND)
            if tudo_instance.status == "GoalStatus.completed":
                return format_response(
                    error={"tudo_code": ["Goal already completed"]},
                    status=HTTP_400_BAD_REQUEST,
                )
            if tudo_instance.status == "GoalStatus.paid":
                return format_response(
                    error={"tudo_code": ["Goal already paid"]},
                    status=HTTP_400_BAD_REQUEST,
                )

        serializer = self.serializer_class(data=contribution,
                                           context={"request": request})

        if not serializer.is_valid():
            return format_response(error=serializer.errors, status=HTTP_400_BAD_REQUEST)

        validated_data = serializer.data
        transaction_reference = str(uuid.uuid4())
        user = tudo_instance.user or tudo_instance.business
        shortend_goal_title = shorten(tudo_instance.goal_name.title(),
                                      20,
                                      placeholder='...')
        payload = dict(txref=transaction_reference,
                       amount=validated_data["amount"] / 100,
                       currency=tudo_instance.currency,
                       customer_email=validated_data["contributor_email"],
                       redirect_url=settings.FRONTEND_URL + "/paymentSuccess",
                       custom_title=CUSTOM_GOAL_TEXT.format(user.first_name,
                                                            shortend_goal_title))

        if validated_data["scope"] == "international":
            save_in_redis(
                f"ref-meta-{transaction_reference}",
                dict(
                    transaction_type=TransactionType.TUDO_CONTRIBUTION,
                    contributor_email=validated_data["contributor_email"],
                    contributor_name=validated_data["contributor_name"],
                    tudo_code=validated_data["tudo_code"],
                ),
                timeout=86400,  # 24hrs validity
            )
            response = FlutterWaveAPI.initialize(**payload)

            if response is None:
                delete_from_redis(f"ref-meta-{transaction_reference}")
                return format_response(error="Payment Processor Error",
                                       status=HTTP_503_SERVICE_UNAVAILABLE)
        else:
            response = Transaction.initialize(
                reference=transaction_reference,
                amount=validated_data["amount"],
                currency=tudo_instance.currency,
                email=validated_data["contributor_email"],
                metadata={
                    **validated_data,
                    "transaction_type": TransactionType.TUDO_CONTRIBUTION,
                },
                callback_url=settings.FRONTEND_URL + "/paymentSuccess",
            )

        if response["status"] == "success" or response["status"] is True:
            return format_response(
                data={
                    "authorization_url":
                    response["data"].get("link")
                    or response["data"].get("authorization_url")
                },
                message="Authorization URL created",
                status=HTTP_201_CREATED,
            )

        return format_response(
            error="Payment Processor Error - Error Reported",
            status=HTTP_500_INTERNAL_SERVER_ERROR,
        )

    def retrieve(self, request, pk=None):
        tudo_contribution_reference = pk
        user = request.user
        if tudo_contribution_reference:
            tudo_contribution = GoalContribution.objects.filter(
                reference=tudo_contribution_reference).first()

            if not tudo_contribution:
                return format_response(error="Goal contribution not found",
                                       status=HTTP_404_NOT_FOUND)

            serializer = GoalContributionSerializer(tudo_contribution)
            contributed_amount = serializer.data.pop("amount")
            contribution_current = tudo_contribution.tudo_code.amount_generated
            contribution_target = tudo_contribution.tudo_code.amount
            contribution_percentage_current = round(
                (D(contribution_current) / D(contribution_target)) * 100, 2)
            data = {
                "status": tudo_contribution.status,
                "contributed_at": tudo_contribution.updated_at,
                "contributed_amount": contributed_amount,
                "contribution_current": contribution_current,
                "contribution_current_percentage": contribution_percentage_current,
                "contribution_target": contribution_target,
                "tudo_media": tudo_contribution.tudo_code.tudo_media,
                "beneficiary_name": tudo_contribution.tudo_code.user.first_name,
            }
            data.update(serializer.data)
            del data["amount"]
            del data["contributor_email"]
            log = f"successfully retrieved Goal contribution"
            return format_response(
                data=data,
                status=HTTP_200_OK,
            )

        return format_response(status=HTTP_404_NOT_FOUND)

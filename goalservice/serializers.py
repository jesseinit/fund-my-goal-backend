
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


class TudoWithdrawTransactionSerializer(serializers.ModelSerializer):
    state = serializers.SerializerMethodField()

    class Meta:
        model = TudoWithdrawal
        fields = "__all__"

    def get_state(self, obj):
        return str(obj.state)


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

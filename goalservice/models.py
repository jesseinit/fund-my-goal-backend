from django.db import models
from utils.helpers import BaseAbstractModel
# Create your models here.


class GoalManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(state=StateType.active.value)

    def get_all(self, **filters):
        return super().get_queryset().filter(**filters)


class GoalQuerySet(models.QuerySet):
    """ Custom query set to filter Goal states """

    def running(self):
        return self.filter(status=GoalStatus.running.value,
                            state=StateType.active.value)

    def completed(self):
        return self.filter(
            status__in=[GoalStatus.completed.value, GoalStatus.paid.value],
            state=StateType.active.value)

    def paid(self):
        return self.filter(status=GoalStatus.paid.value, state=StateType.active.value)


class Goal(BaseAbstractModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             default=None, null=True, related_name='personal_todo')
    created_at = models.DateTimeField(auto_now_add=True)
    goal_name = models.CharField(max_length=100, null=False)
    category = models.ForeignKey(GoalCategory, on_delete=models.CASCADE)
    amount = models.BigIntegerField()
    amount_generated = models.BigIntegerField(default=0)
    amount_withdrawn = models.BigIntegerField(default=0)
    currency = models.CharField(
        max_length=10, choices=CURRENCIES, default='NGN')
    status = models.CharField(
        max_length=50,
        choices=[(Goal, Goal.value) for Goal in GoalStatus],
        default=GoalStatus.running
    )
    share_code = models.CharField(
        null=True, max_length=LENGTH_OF_ID, unique=True)
    collection_code = models.CharField(null=True, max_length=16)
    start_date = models.DateField(auto_now_add=True)
    is_visible = models.BooleanField(default=False)
    goal_description = models.TextField(
        null=True, default=default_Goal_description)
    updated_at = models.DateTimeField(auto_now=True)
    Goal_duration = models.CharField(
        max_length=50,
        choices=[(Goal, Goal.value) for Goal in GoalDuration])
    Goal_media = models.URLField(null=True)
    completion_date = models.DateTimeField()
    objects = GoalManager()
    Goal_status = GoalQuerySet().as_manager()


class GoalContribution(BaseAbstractModel):
    Goal_code = models.ForeignKey(
        Goal, to_field='share_code', db_column='Goal_code', on_delete=models.CASCADE)
    contributor_name = models.CharField(max_length=100)
    contributor_email = models.EmailField(max_length=100)
    amount = models.BigIntegerField()
    currency = models.CharField(
        max_length=10, choices=CURRENCIES, default='NGN')
    reference = models.CharField(max_length=100, unique=True)
    contribution_type = models.CharField(
        choices=[(contrib_type, contrib_type.value)
                 for contrib_type in GoalContributionType],
        default=GoalContributionType.USERCONTRIBUTION, max_length=65)
    contribution_status = models.CharField(choices=[(status, status.value)
                                                    for status in TransactionStatus],
                                           default='Pending', max_length=65)


class GoalWithdrawalManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(state=StateType.active.value)


class GoalWithdrawal(BaseAbstractModel):
    user = models.ForeignKey(
        User, null=True, default=None, on_delete=models.CASCADE)
    Goal = models.ForeignKey(Goal, on_delete=models.CASCADE)
    amount = models.BigIntegerField()
    currency = models.CharField(
        max_length=10, choices=CURRENCIES, default='NGN')
    service_charge = models.BigIntegerField(default=0)
    reference = models.CharField(max_length=100, unique=True)
    bank = models.ForeignKey(BankAccount, on_delete=models.CASCADE)
    objects = GoalWithdrawalManager()


class GoalLikes(BaseAbstractModel):
    user = models.ForeignKey(
        User, null=True, default=None, on_delete=models.CASCADE)
    Goal = models.ForeignKey(Goal, on_delete=models.CASCADE)
    like_status = models.CharField(max_length=50, choices=LIKE_STATUS)


class GoalFollowers(BaseAbstractModel):
    user = models.ForeignKey(
        User, null=True, default=None, on_delete=models.CASCADE)
    Goal = models.ForeignKey(Goal, on_delete=models.CASCADE)
    follow_status = models.CharField(max_length=50, choices=FOLLOWING_STATUS)


class GoalComments(BaseAbstractModel):
    user = models.ForeignKey(
        User, null=True, default=None, on_delete=models.CASCADE)
    Goal = models.ForeignKey(Goal, on_delete=models.CASCADE, null=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True)
    comment_text = models.TextField()


class GoalMediaManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(state=StateType.active.value)


class GoalMedia(BaseAbstractModel):

    Goal = models.ForeignKey(Goal, on_delete=models.CASCADE, null=True,
                             default=None)
    url = models.URLField(null=False)
    objects = GoalMediaManager()

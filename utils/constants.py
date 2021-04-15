import os
from string import Template

PLANTYPES = [('TARGET', 'TARGET'), ('PERIODIC', 'PERIODIC'), ('LOCKED', 'LOCKED')]

TRANSACTIONSTATUS = [
    ('PENDING', 'PENDING'),
    ('SUCCESS', 'SUCCESS'),
    ('FAILED', 'FAILED'),
]

SAVINGSFREQUENCY = [('DAILY', 'DAILY'), ('WEEKLY', 'WEEKLY'), ('MONTHLY', 'MONTHLY')]

SAVINGSTATUS = [
    ('COMPLETED', 'COMPLETED'),
    ('RUNNING', 'RUNNING'),
    ('PAID', 'PAID'),
    ('PAUSED', 'PAUSED'),
    ('PENDING', 'PENDING'),
    ('PROCESSING_WITHDRAWAL', 'PROCESSING_WITHDRAWAL'),
    ('SCHEDULED', 'SCHEDULED'),
]

GROUP_TUDO_STATUS = [
    ('RUNNING', 'RUNNING'),
    ('COMPLETED', 'COMPLETED'),
    ('PROCESSING_WITHDRAWAL', 'PROCESSING_WITHDRAWAL'),
    ('PAID', 'PAID'),
]

CURRENCIES = [
    ('NGN', 'NGN'),
    ('USD', 'USD'),
]

BUSINESS_SUPPORTED_CURRENCIES = [
    ('NGN', 'NGN'),
    ('USD', 'USD'),
]

LIKE_STATUS = [
    ('LIKED', 'LIKED'),
    ('UN-LIKED', 'UN-LIKED'),
]

TUDO_CONTRIBUTION_TYPES = [('TOP_UP', 'TOP_UP'),
                           ('USER_CONTRIBUTION', 'USER_CONTRIBUTION')]

FOLLOWING_STATUS = [
    ('FOLLOWED', 'FOLLOWED'),
    ('UNFOLLOWED', 'UNFOLLOWED'),
]

TUDO_DEFAULT_DESCRIPTION = ("Hey! I'm trying to reach this goal as soon as possible, "
                            "and I'd be glad to have your support on this journey. "
                            "Your contribution would go a long way. Thank you!")
ID_LENGTH = 12

INSUFFICIENT_BALANCE = 'Pool account balance not enough to complete transfer'

FUNDS_TRANFER_SUCCESS = 'Funds tranfer was successfully completed'

FUNDS_TRANFER_FAILURE = 'Funds transfer could not be completed'

SUPPORT_EMAIL = os.getenv('SUPPORT_EMAIL', 'Tudo Support <support@mytudo.com>')

GROUP_MEMBER_ROLES = [('REGULAR', 'REGULAR'), ('ADMIN', 'ADMIN'),
                      ('SUPERADMIN', 'SUPERADMIN')]

NOTIFICATION_TYPE = [('ALERT', 'ALERT'), ('INVITE', 'INVITE'),
                      ('WITHDRAWAL_REQUEST', 'WITHDRAWAL_REQUEST')]

NOTIFICATION_ENTITY = [('TUDO', 'TUDO'), ('SAVINGS', 'SAVINGS'),
                       ('GROUPTUDO', 'GROUPTUDO')]

GROUPTUDO_TRANSACTION_TYPE = [('CONTRIBUTION', 'CONTRIBUTION'),
                              ('WITHDRAWAL', 'WITHDRAWAL')]

INVITE_STATUS = [('PENDING', 'PENDING'), ('ACCEPTED', 'ACCEPTED'),
                 ('DECLINED', 'DECLINED')]

REWARDTYPES = [('SIGNUP', 'SIGNUP'), ('GOAL_CREATION', 'GOAL_CREATION'),
               ('GOAL_CONTRIBUTION', 'GOAL_CONTRIBUTION')]

WALLET_TRANSACTION_TYPE = [('DEBIT', 'DEBIT'), ('CREDIT', 'CREDIT')]

WALLET_TRANSACTION_TRIGGER = [('TOP_UP', 'TOP_UP'),
                              ('TUDO_WITHDRAWAL', 'TUDO_WITHDRAWAL'),
                              ('SAVINGS_WITHDRAWAL', 'SAVINGS_WITHDRAWAL'),
                              ('REWARD_COLLECTION', 'REWARD_COLLECTION'),
                              ('WALLET_TRANSFER', 'WALLET_TRANSFER'),
                              ('BANK_WITHDRAWAL', 'BANK_WITHDRAWAL')]

NGN_PER_POINT = 50  # Naira not Kobo

BUSINESS_SECTORS = [
    ('AEROSPACE', 'AEROSPACE'),
    ('TRANSPORT', 'TRANSPORT'),
    ('COMPUTER', 'COMPUTER'),
    ('TELECOMMUNICATION', 'TELECOMMUNICATION'),
    ('AGRICULTURE', 'AGRICULTURE'),
    ('CONSTRUCTION', 'CONSTRUCTION'),
    ('EDUCATION', 'EDUCATION'),
    ('PHARMECEUTICAL', 'PHARMECEUTICAL'),
    ('FOOD', 'FOOD'),
    ('HEALTHCARE', 'HEALTHCARE'),
    ('HOSPITALITY', 'HOSPITALITY'),
    ('ENTERTAINMENT', 'ENTERTAINMENT'),
    ('NEWSMEDIA', 'NEWSMEDIA'),
    ('ENERGY', 'ENERGY'),
    ('MANUFACTURING', 'MANUFACTURING'),
    ('MUSIC', 'MUSIC'),
    ('MINING', 'MINING'),
    ('ELECTRONICS', 'ELECTRONICS'),
]

BUSINESS_SERVICES = [('ACCOUNT OPENING', 'ACCOUNT OPENING'),
                     ('WALLETSYSTEMS', 'WALLETSYSTEMS'), ('FUNDRAISING', 'FUNDRAISING'),
                     ('SAVINGS', 'SAVINGS'), ('INVESTMENTS', 'INVESTMENTS'),
                     ('MARKETPLACE', 'MARKETPLACE'),
                     ('PAYMENTCOLLATIONS', 'PAYMENTCOLLATIONS'),
                     ('GROUPFINANCINGGOALS', 'GROUPFINANCINGGOALS')]

BUSINESS_SUPPORTED_COUNTRY = [
    ('NG', 'NIGERIA'), ('US', 'UNITED STATES'),
    ('SA', 'SOUTH AFRICA'), ('KY', 'KENYA'), ('BE', 'BELGIUM')]

DEFAULT_AVATAR_URL = \
    'https://tudo-media.ams3.digitaloceanspaces.com/profile-images/USER_IMAGE_tko5rq.png'  # noqa

USER_TYPES = ['PERSONAL', 'BUSINESS']

REQUIRED_BUSINESS_TUDO_FIELDS = [
    "goal_name", "amount", "currency", "tudo_duration", "category_id", "tudo_media"
]

REQUIRED_PERSONAL_TUDO_FIELDS = [
    "goal_name", "amount", "currency", "tudo_duration", "category_id",
]

GROUP_MEMBERSHIP_TYPE = [('FIXED', 'FIXED'), ('FLEXIBLE', 'FLEXIBLE')]

MAX_GROUP_MEMBERSHIP_COUNT = 25

GROUP_ACCESS_TYPE = [('PUBLIC', 'PUBLIC'), ('PRIVATE', 'PRIVATE')]

NOTIFICATION_INVITE_TEXT = "You have been invited to join {} group goal by {}"

CUSTOM_GOAL_TEXT = "Contribute to {}'s {} Goal"

WITHDRAWAL_DESTINATION = [("BANK", "BANK"), ("WALLET", "WALLET")]

WITHDRAWAL_STATUS = [
    ("PENDING", "PENDING"), ("APPROVED", "APPROVED"), ("DECLINED", "DECLINED")]

# 2% off all withdrawals
SERVICE_RATE = 0.00

GOAL_CONTRIB_NOTIF_TEXT = Template(
    "Hello $first_name, $amount was contributed by $contributor_name to your $goal_name goal, yaaay!🎉")

GOAL_COMPLETION_NOTIF_TEXT = Template(
    "Congratulations!🎉 $first_name, your goal $goal_name has been achieved, cheers!🎉")

REWARD_GOAL_TOPUP_TEXT = Template(
    "You've just received $points point(s) after $invitee_name perfomed their first goal topup")

REWARD_GOAL_CONTRIB_TEXT = Template(
    "You've just received $points point(s) after $invitee_name got their first goal contribution")

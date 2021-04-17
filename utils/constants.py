import os
from string import Template


TRANSACTIONSTATUS = [
    ('PENDING', 'PENDING'),
    ('SUCCESS', 'SUCCESS'),
    ('FAILED', 'FAILED'),
]


CURRENCIES = [
    ('NGN', 'NGN'),
    ('USD', 'USD'),
]

GOAL_DEFAULT_DESCRIPTION = ("Hey! I'm trying to reach this goal as soon as possible, "
                            "and I'd be glad to have your support on this journey. "
                            "Your contribution would go a long way. Thank you!")

INSUFFICIENT_BALANCE = 'Pool account balance not enough to complete transfer'

FUNDS_TRANFER_SUCCESS = 'Funds tranfer was successfully completed'

FUNDS_TRANFER_FAILURE = 'Funds transfer could not be completed'

SUPPORT_EMAIL = os.getenv(
    'SUPPORT_EMAIL', 'FundMyGoal Support <support@fundmygoal.com>')


WALLET_TRANSACTION_TYPE = [('DEBIT', 'DEBIT'), ('CREDIT', 'CREDIT')]

WALLET_TRANSACTION_TRIGGER = [('TOP_UP', 'TOP_UP'),
                              ('WALLET_TRANSFER', 'WALLET_TRANSFER'),
                              ('BANK_WITHDRAWAL', 'BANK_WITHDRAWAL')]


DEFAULT_AVATAR_URL = \
    'https://res.cloudinary.com/jesseinit/image/upload/v1552302764/store/file_xowg1x.jpg'  # noqa

USER_TYPES = ['PERSONAL', 'BUSINESS']

NOTIFICATION_INVITE_TEXT = "You have been invited to join {} group goal by {}"

CUSTOM_GOAL_TEXT = "Contribute to {}'s {} Goal"

WITHDRAWAL_DESTINATION = [("BANK", "BANK"), ("WALLET", "WALLET")]

WITHDRAWAL_STATUS = [
    ("PENDING", "PENDING"), ("APPROVED", "APPROVED"), ("DECLINED", "DECLINED")]

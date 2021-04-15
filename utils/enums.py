from enum import Enum


class StateType(Enum):
    active = "active"
    archived = "archived"
    deleted = "deleted"


class TudoStatus(Enum):
    """ Different status of tudo """
    RUNNING = 'RUNNING'
    COMPLETED = 'COMPLETED'
    PAID = 'PAID'
    PROCESSING_WITHDRAWAL = 'PROCESSING_WITHDRAWAL'


class TudoDuration(Enum):
    """ Different duration of tudo """
    ONEMONTH = '30'
    TWOMONTHS = '60'
    THREEMONTHS = '90'


class TransactionStatus(Enum):
    PENDING = 'PENDING'
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'


class TudoContributionType(Enum):
    TOPUP = 'TOPUP'
    USERCONTRIBUTION = 'USERCONTRIBUTION'


class NotificationStatus(Enum):
    READ = "READ"
    UNREAD = "UNREAD"


class EmailSubjects(Enum):
    contribution_receiver = 'Yaay! You just got N{}! 🎉🎈🍾'
    contribution_sender = 'Thank you! 😁'
    tudo_goal_reached = 'Goal Smashed! 🎯💪🏽🍾'
    tudo_expired = 'Yikes! You didn’t reach this goal. ☹️'
    withdrawal = 'Your withdrawal was successful! 🎉'
    savings_topup = 'Tudo Top Up Successful!'
    new_tudo_list = 'New Tudo List Created!'
    signup = 'Welcome to Tudo! 🎉🎉'
    new_savings = 'New Savings Plan Created!'
    successful_invite = '5 points earned, Good job!🎉'
    inactivity = 'It’s been {} weeks! We miss you ☹️'
    password_reset = 'Password Reset'


class PlanType(Enum):
    """ Refers to the various plans type a savings plan can be created with """
    TARGET = 'TARGET'
    PERIODIC = 'PERIODIC'
    LOCKED = 'LOCKED'


class UserRole(Enum):
    default_user = 'default_user'
    admin = 'admin'


class RewardPoints(Enum):
    signup = 1
    goal_creation = 2
    savings_topup = 2


class UserActionStatus():
    SUCCESSFUL = 'SUCCESSFUL'
    FAILED = 'FAILED'


class TransactionType():
    """Determines the transaction being processed by webhook"""
    TUDO_CONTRIBUTION = "TUDO_CONTRIBUTION"
    TUDO_TOPUP = "TTUDO_TOPUP"
    LOCKED_SAVINGS = "LOCKED_SAVINGS"
    TARGETED_SAVINGS = "TARGETED_SAVINGS"
    PERIODIC_SAVINGS = "PERIODIC_SAVINGS"
    SAVINGS_TOPUP = "SAVINGS_TOPUP"
    ADDED_CARD = "ADDED_CARD"
    GROUP_TUDO_CONTRIBUTION = "GROUP_TUDO_CONTRIBUTION"
    FUND_WALLET = "FUND_WALLET"

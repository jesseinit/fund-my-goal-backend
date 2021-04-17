from enum import Enum


class RecordStateType(Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"


class GoalStatus(Enum):
    """ The status of a goal """
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


class GoalContributionType(Enum):
    TOPUP = 'TOPUP'
    USERCONTRIBUTION = 'USERCONTRIBUTION'


class EmailSubjects(Enum):
    GOAL_SMASHED = 'Goal Smashed! 🎯💪🏽🍾'
    GOAL_EXPIRED = 'Yikes! You didn’t reach this goal. ☹️'
    COMPLETED_WITHDRAWAL = 'Your withdrawal was successful! 🎉'
    NEW_GOAL_ADDED = 'New Tudo List Created!'
    SIGNUP = 'Welcome to Tudo! 🎉🎉'
    INITIATED_PASSWORD_RESET = 'Password Reset'

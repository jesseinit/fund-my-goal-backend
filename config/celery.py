from __future__ import absolute_import, unicode_literals

import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

max_timeout_in_seconds = 3 * 31 * 24 * 60 * 60
app.conf.broker_transport_options = {
    "visibility_timeout": max_timeout_in_seconds}

app.conf.beat_schedule = {
    'send-notification-two-weeks-inactive-users-daily': {
        'task': 'send_inactivity_reminder',
        'schedule': crontab(minute=0, hour=13),
    },
    'complete-expired_tudos': {
        'task': 'complete_expired_tudos',
        'schedule': crontab(minute=59, hour=23)
    },
}

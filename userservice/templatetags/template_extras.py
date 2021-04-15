from decimal import Decimal
from datetime import datetime

from django import template
from dateutil import parser

register = template.Library()


@register.filter
def convert_kobo_to_naira(value):
    return "{:,.2f}".format(Decimal(value) / Decimal(100))


@register.filter
def format_date(date):
    if not isinstance(date, datetime):
        date = parser.parse(date)
    return date.strftime("%d %B, %Y")

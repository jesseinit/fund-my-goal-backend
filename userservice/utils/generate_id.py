import uuid
from django.utils.http import int_to_base36


LENGTH_OF_ID = 12


def generate_id() -> str:
    """Generates random string whose length is of `ID_LENGTH`"""
    return int_to_base36(uuid.uuid4().int)[:LENGTH_OF_ID]

from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode
from userservice.utils.password_reset.activation_token import (
    account_activation_token)
from userservice.models import User, Business


def decode_token(uidb64, token):
    """
    Description: It decodes the encoded token

    Args:
        uidb64: Your userid that was converted to base64
        token: Token.

    Returns:
        user: if it was correctly decoded else user will be None.
        chek_token: returns a boolean .
    """
    uid = force_bytes(urlsafe_base64_decode(uidb64)).decode('utf-8')
    user = User.objects.filter(id=uid).first(
    ) or Business.objects.filter(id=uid).first()
    check_token = account_activation_token.check_token(user, token)
    return check_token, user

import jwt

from django.conf import settings
from django.dispatch import receiver
from django.db.models.signals import post_save

# from userservice.models import BlackListedToken


# @receiver(post_save, sender=BlackListedToken)
# def delete_expired_token(sender, instance, **kwargs):
#     """
#     This receiver is executed whenever a token is blacklisted.

#     Args:
#         sender: the model sending the signal
#         instance: The instance of the just blacklisted token

#     """
# model_instance = BlackListedToken.objects.filter(user_id=instance.user_id)
# if model_instance.exists:
#     for model in model_instance:
#         try:
#             jwt.decode(model.token, settings.SECRET_KEY,
#                        algorithms=['HS256'])
#         except jwt.ExpiredSignatureError:
#             model.delete()
# pass

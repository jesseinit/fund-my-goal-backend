from userservice.models import User
from walletservice.models import Wallet
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, update_fields, **kwargs):
    if created:
        Wallet.objects.create(user=instance)

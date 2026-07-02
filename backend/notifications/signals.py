from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .preferences import ensure_default_preferences


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_default_notification_preferences(sender, instance, created, **kwargs):
    if created:
        ensure_default_preferences(instance)

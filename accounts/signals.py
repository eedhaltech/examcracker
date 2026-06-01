from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from allauth.socialaccount.signals import social_account_added
from .models import UserProfile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.profile.save()
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=instance)


@receiver(social_account_added)
def populate_google_profile(request, sociallogin, **kwargs):
    user = sociallogin.user
    profile, _ = UserProfile.objects.get_or_create(user=user)
    extra = sociallogin.account.extra_data
    if not profile.google_id:
        profile.google_id = extra.get('sub', '')
    if not profile.avatar_url:
        profile.avatar_url = extra.get('picture', '')
    profile.save()

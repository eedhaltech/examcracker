from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

from .models import MonetizationSettings


CACHE_KEY = "monetization_settings_singleton"


def get_monetization_settings() -> MonetizationSettings:
    """
    Returns singleton MonetizationSettings row (creates default if missing).
    Cached for 60 seconds.
    """
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    obj, _ = MonetizationSettings.objects.get_or_create(id=1)
    cache.set(CACHE_KEY, obj, 60)
    return obj


def monetization_active() -> bool:
    return get_monetization_settings().is_active_now


def monetization_active_for_user(user) -> bool:
    """
    Per-user monetization gate:
    - global monetization must be active (ms.is_active_now)
    - if ms.monetize_after_days > 0 and user is authenticated,
      paywalls become active only after that many days since signup.
    """
    ms = get_monetization_settings()
    if not ms.is_active_now:
        return False

    try:
        if not user or not getattr(user, "is_authenticated", False):
            return True
        delay_days = int(ms.monetize_after_days or 0)
        if delay_days <= 0:
            return True
        joined = getattr(user, "date_joined", None)
        if not joined:
            return True
        cutoff = joined + timedelta(days=delay_days)
        return timezone.now() >= cutoff
    except Exception:
        return ms.is_active_now


def clear_monetization_cache():
    cache.delete(CACHE_KEY)

from django.db import models
from django.utils import timezone


def check_attempt_allowed(user):
    """Returns (allowed: bool, current_count: int)"""
    # If monetization is off, do not enforce attempt limits
    try:
        from payments.monetization import get_monetization_settings
        ms = get_monetization_settings()
        if not ms.is_active_now:
            return True, 0
        free_limit = int(ms.free_attempts_per_day or 0)
    except Exception:
        free_limit = 5

    from .models import DailyAttemptLog
    today = timezone.now().date()
    log, _ = DailyAttemptLog.objects.get_or_create(user=user, date=today)
    if free_limit > 0 and (not user.profile.membership_active) and log.attempt_count >= free_limit:
        return False, log.attempt_count
    return True, log.attempt_count


def increment_attempt_count(user):
    from .models import DailyAttemptLog
    today = timezone.now().date()
    DailyAttemptLog.objects.filter(user=user, date=today).update(
        attempt_count=models.F('attempt_count') + 1
    )

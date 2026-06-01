"""
LevelConfig — singleton-style model (one row per level 1-5).
Admin can set each level as free or members-only from the admin panel.
Cached in Django's cache for 5 minutes to avoid DB hits on every quiz load.
"""
from django.db import models
from django.core.cache import cache

LEVEL_CHOICES = [(i, f'Level {i}') for i in range(1, 6)]

CACHE_KEY = 'level_config_map'


class LevelConfig(models.Model):
    level = models.PositiveIntegerField(
        choices=LEVEL_CHOICES,
        unique=True,
        help_text='Question difficulty level (1 = easiest, 5 = hardest)'
    )
    requires_membership = models.BooleanField(
        default=False,
        help_text='If checked, only paying members can access this level'
    )
    label = models.CharField(
        max_length=100,
        blank=True,
        help_text='Optional display label, e.g. "Beginner", "Advanced"'
    )
    description = models.CharField(
        max_length=200,
        blank=True,
        help_text='Short description shown to users on the quiz start page'
    )
    max_questions = models.PositiveIntegerField(
        default=0,
        help_text='Max questions shown per quiz session at this level. 0 = no limit (show all).'
    )

    class Meta:
        ordering = ['level']
        verbose_name = 'Level Configuration'
        verbose_name_plural = 'Level Configurations'

    def __str__(self):
        status = '🔒 Members only' if self.requires_membership else '🆓 Free'
        label = f' — {self.label}' if self.label else ''
        return f'Level {self.level}{label} ({status})'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete(CACHE_KEY)  # invalidate cache on any change

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        cache.delete(CACHE_KEY)


def get_level_config_map():
    """
    Returns a dict: {level_int: {'requires_membership': bool, 'max_questions': int}}
    Cached for 5 minutes.
    """
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    rows = LevelConfig.objects.all()
    if rows.exists():
        config = {
            row.level: {
                'requires_membership': row.requires_membership,
                'max_questions': row.max_questions,
            }
            for row in rows
        }
    else:
        config = {
            1: {'requires_membership': False, 'max_questions': 0},
            2: {'requires_membership': False, 'max_questions': 0},
            3: {'requires_membership': True,  'max_questions': 0},
            4: {'requires_membership': True,  'max_questions': 0},
            5: {'requires_membership': True,  'max_questions': 0},
        }

    cache.set(CACHE_KEY, config, 300)
    return config


def get_max_questions(level: int) -> int:
    """Returns the max questions limit for a level. 0 means no limit."""
    config = get_level_config_map()
    entry = config.get(level, {})
    if isinstance(entry, dict):
        return entry.get('max_questions', 0)
    return 0


def is_level_accessible(level: int, is_member: bool, user=None) -> bool:
    """Returns True if the user can access this level."""
    # If monetization is OFF, everything should be accessible
    try:
        from payments.monetization import monetization_active_for_user
        if not monetization_active_for_user(user):
            return True
        from payments.monetization import get_monetization_settings
        ms = get_monetization_settings()
        if not ms.gate_levels:
            return True
    except Exception:
        pass

    config = get_level_config_map()
    entry = config.get(level, {'requires_membership': True})
    requires_membership = entry['requires_membership'] if isinstance(entry, dict) else entry
    if requires_membership and not is_member:
        return False
    return True


def max_accessible_level(is_member: bool, user=None) -> int:
    """Returns the highest level the user can access."""
    try:
        from payments.monetization import monetization_active_for_user, get_monetization_settings
        if not monetization_active_for_user(user):
            return 5
        ms = get_monetization_settings()
        if not ms.gate_levels:
            return 5
    except Exception:
        pass

    config = get_level_config_map()
    accessible = [
        lvl for lvl, entry in config.items()
        if not (entry['requires_membership'] if isinstance(entry, dict) else entry) or is_member
    ]
    return max(accessible) if accessible else 1


def free_levels() -> list:
    config = get_level_config_map()
    return [lvl for lvl, entry in config.items()
            if not (entry['requires_membership'] if isinstance(entry, dict) else entry)]


def paid_levels() -> list:
    config = get_level_config_map()
    return [lvl for lvl, entry in config.items()
            if (entry['requires_membership'] if isinstance(entry, dict) else entry)]

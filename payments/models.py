from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

PLAN_CHOICES = [
    ('basic', '₹10 / 30 days'),
    ('standard', '₹50 / 180 days'),
    ('premium', '₹100 / 360 days'),
]

PLAN_PRICES = {'basic': 10, 'standard': 50, 'premium': 100}
PLAN_DAYS = {'basic': 30, 'standard': 180, 'premium': 360}

PAYMENT_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('captured', 'Captured'),
    ('failed', 'Failed'),
]


class Subscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    payment_reference = models.CharField(max_length=200, blank=True)
    amount = models.PositiveIntegerField(
        default=0,
        help_text="Amount paid in INR for this subscription.",
    )
    currency = models.CharField(max_length=10, default='INR')
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending',
        help_text="Current Razorpay payment status.",
    )
    razorpay_order_id = models.CharField(max_length=255, blank=True)
    razorpay_payment_id = models.CharField(max_length=255, blank=True)
    razorpay_signature = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        status = 'paid' if self.payment_status == 'captured' else self.payment_status
        return f"{self.user.email} — {self.plan} — {self.start_date} to {self.end_date} ({status})"

    @property
    def amount_display(self) -> str:
        return f"₹{self.amount} {self.currency}"


class MonetizationSettings(models.Model):
    """
    Feature flags for enabling/disabling monetization and paywalls.
    Keep it as a singleton (one row).
    """
    monetization_enabled = models.BooleanField(
        default=False,
        help_text="If off, the site behaves as non-monetized (no paywalls / no upsell CTAs).",
    )
    monetization_starts_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Optional. If set, monetization becomes active only after this date-time.",
    )

    monetize_after_days = models.PositiveIntegerField(
        default=0,
        help_text="Delay paywalls for new users by N days after signup (0 = no delay).",
    )

    # Controls what becomes gated when monetization is active
    gate_analytics = models.BooleanField(default=True)
    gate_levels = models.BooleanField(default=True)

    # Free vs member attempt cap when monetization is active (0 = unlimited)
    free_attempts_per_day = models.PositiveIntegerField(default=5)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Monetization Settings"
        verbose_name_plural = "Monetization Settings"

    def __str__(self):
        return "Monetization Settings"

    @property
    def is_active_now(self) -> bool:
        if not self.monetization_enabled:
            return False
        if self.monetization_starts_at and timezone.now() < self.monetization_starts_at:
            return False
        return True


class RazorpaySettings(models.Model):
    """Stored Razorpay configuration used by checkout and webhook handlers."""
    razorpay_enabled = models.BooleanField(
        default=True,
        help_text="If disabled, users can subscribe directly without payment.",
    )
    key_id = models.CharField(
        max_length=200,
        blank=True,
        help_text="Razorpay Key ID for checkout integration.",
    )
    key_secret = models.TextField(
        blank=True,
        help_text="Razorpay Key Secret. Keep this confidential and do not expose it in templates.",
    )
    webhook_secret = models.TextField(
        blank=True,
        help_text="Secret used to verify Razorpay webhook payloads.",
    )
    webhook_url = models.URLField(
        blank=True,
        help_text="Public Razorpay webhook URL. If blank, the default webhook endpoint will be used.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Razorpay Settings"
        verbose_name_plural = "Razorpay Settings"

    def __str__(self):
        return "Razorpay Settings"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj


class RazorpayWebhookEvent(models.Model):
    """Audit log for Razorpay webhook deliveries."""
    event_id = models.CharField(max_length=255, blank=True, db_index=True)
    event_type = models.CharField(max_length=100, db_index=True)
    payload = models.JSONField(default=dict)
    processed = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-received_at']

    def __str__(self):
        return f"{self.event_type} ({'processed' if self.processed else 'pending'})"

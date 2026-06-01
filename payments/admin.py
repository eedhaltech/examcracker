from django import forms
from django.contrib import admin
from .models import Subscription, MonetizationSettings, RazorpaySettings, RazorpayWebhookEvent
from .monetization import clear_monetization_cache


class RazorpaySettingsAdminForm(forms.ModelForm):
    key_id = forms.CharField(
        label='Razorpay Key ID',
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'rzp_test_xxxxxxxxxxxxx'}),
        help_text='Your Razorpay API Key ID used by the checkout flow.',
    )
    key_secret = forms.CharField(
        label='Razorpay Key Secret',
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text='Keep this secret secure. Leave blank to preserve the existing secret.',
    )
    webhook_secret = forms.CharField(
        label='Razorpay Webhook Secret',
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text='Used to verify incoming Razorpay webhook payloads. Leave blank to preserve the existing secret.',
    )
    webhook_url = forms.URLField(
        label='Razorpay Webhook URL',
        required=False,
        widget=forms.URLInput(attrs={'placeholder': 'https://example.com/subscribe/webhook/'}),
        help_text='Public webhook URL. Leave blank to use the built-in webhook endpoint.',
    )

    class Meta:
        model = RazorpaySettings
        fields = ('key_id', 'key_secret', 'webhook_secret', 'webhook_url')

    def clean_key_id(self):
        key_id = self.cleaned_data.get('key_id')
        if key_id in (None, '') and self.instance.pk and self.instance.key_id:
            return self.instance.key_id
        if not key_id:
            raise forms.ValidationError('Razorpay Key ID is required.')
        if not key_id.startswith('rzp_'):
            raise forms.ValidationError('Enter a valid Razorpay Key ID, for example rzp_test_xxxxxxxxxxxxx.')
        return key_id

    def clean_key_secret(self):
        key_secret = self.cleaned_data.get('key_secret')
        if key_secret in (None, '') and self.instance.pk and self.instance.key_secret:
            return self.instance.key_secret
        if not key_secret:
            raise forms.ValidationError('Razorpay Key Secret is required.')
        return key_secret

    def clean_webhook_secret(self):
        webhook_secret = self.cleaned_data.get('webhook_secret')
        if webhook_secret in (None, '') and self.instance.pk and self.instance.webhook_secret:
            return self.instance.webhook_secret
        return webhook_secret


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'plan',
        'amount',
        'currency',
        'payment_status',
        'start_date',
        'end_date',
        'is_active',
        'created_at',
    )
    list_filter = ('plan', 'is_active', 'payment_status')
    search_fields = ('user__email', 'razorpay_order_id', 'razorpay_payment_id')
    readonly_fields = ('created_at',)


@admin.register(RazorpayWebhookEvent)
class RazorpayWebhookEventAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'event_id', 'processed', 'received_at')
    list_filter = ('event_type', 'processed')
    search_fields = ('event_id', 'error_message')
    readonly_fields = ('event_id', 'event_type', 'payload', 'processed', 'error_message', 'received_at')


@admin.register(MonetizationSettings)
class MonetizationSettingsAdmin(admin.ModelAdmin):
    list_display = (
        'monetization_enabled',
        'monetization_starts_at',
        'monetize_after_days',
        'gate_analytics',
        'gate_levels',
        'free_attempts_per_day',
        'updated_at',
    )

    def has_add_permission(self, request):
        # singleton
        return not MonetizationSettings.objects.exists()

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        clear_monetization_cache()


@admin.register(RazorpaySettings)
class RazorpaySettingsAdmin(admin.ModelAdmin):
    form = RazorpaySettingsAdminForm
    list_display = ('key_id', 'webhook_url', 'updated_at')
    fieldsets = (
        (None, {
            'fields': (
                'key_id',
                'key_secret',
                'webhook_secret',
                'webhook_url',
            ),
        }),
    )

    def has_add_permission(self, request):
        return not RazorpaySettings.objects.exists()

import json
import time
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.models import UserProfile
from .models import PLAN_DAYS, PLAN_PRICES, RazorpaySettings, RazorpayWebhookEvent, Subscription


def _get_razorpay_settings():
    return RazorpaySettings.get_solo()


def _get_razorpay_client():
    import razorpay

    settings_row = _get_razorpay_settings()
    if not settings_row.key_id or not settings_row.key_secret:
        raise ValueError('Razorpay API credentials are not configured.')
    return razorpay.Client(auth=(settings_row.key_id, settings_row.key_secret))


def _get_webhook_url(request):
    settings_row = _get_razorpay_settings()
    if settings_row.webhook_url:
        return settings_row.webhook_url
    return request.build_absolute_uri(reverse('razorpay_webhook'))


def _subscription_dates_for_user(user, plan_key):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    today = timezone.now().date()
    if profile.is_member and profile.membership_expires and profile.membership_expires >= today:
        start_date = profile.membership_expires
    else:
        start_date = today
    return start_date, start_date + timedelta(days=PLAN_DAYS.get(plan_key, 30))


def _activate_subscription(subscription, payment_id='', signature=''):
    subscription.payment_status = 'captured'
    subscription.is_active = True
    if payment_id:
        subscription.razorpay_payment_id = payment_id
        subscription.payment_reference = payment_id
    if signature:
        subscription.razorpay_signature = signature
    subscription.save()

    profile, _ = UserProfile.objects.get_or_create(user=subscription.user)
    profile.is_member = True
    profile.membership_expires = subscription.end_date
    profile.save()
    return profile


@login_required
def subscribe(request):
    settings_row = _get_razorpay_settings()
    razorpay_enabled = settings_row.razorpay_enabled

    plans = [
        {
            'key': 'basic',
            'price': 10,
            'days': 30,
            'label': '30 Days',
            'tagline': 'Cheaper than a cup of tea!',
            'features': ['Unlimited quizzes', 'All difficulty levels', 'Countdown timer', 'No ads'],
        },
        {
            'key': 'standard',
            'price': 50,
            'days': 180,
            'label': '6 Months',
            'tagline': 'Cheaper than a Black Forest cake!',
            'features': ['Everything in Basic', 'Full analytics dashboard', 'Weak area detection', 'Priority support'],
            'popular': True,
        },
        {
            'key': 'premium',
            'price': 100,
            'days': 360,
            'label': '1 Year',
            'tagline': 'Cheaper than a movie ticket!',
            'features': ['Everything in Standard', 'Early access to new features', 'Exam countdown tracker'],
        },
    ]
    for plan in plans:
        plan['checkout_url'] = reverse('payment_checkout', args=[plan['key']])
        if not razorpay_enabled:
            plan['button_text'] = 'Activate Now'
        else:
            plan['button_text'] = f"Pay ₹{plan['price']}"

    return render(request, 'payments/subscribe.html', {
        'plans': plans,
        'razorpay_enabled': razorpay_enabled,
    })


@login_required
def checkout(request, plan_key):
    if plan_key not in PLAN_PRICES:
        return HttpResponseBadRequest('Invalid payment plan selected.')

    settings_row = _get_razorpay_settings()
    
    # If Razorpay is disabled, bypass payment and activate immediately
    if not settings_row.razorpay_enabled:
        start_date, end_date = _subscription_dates_for_user(request.user, plan_key)
        subscription = Subscription.objects.create(
            user=request.user,
            plan=plan_key,
            start_date=start_date,
            end_date=end_date,
            payment_reference='free-bypass',
            amount=PLAN_PRICES[plan_key],
            currency='INR',
            payment_status='captured',
            is_active=True,
        )
        _activate_subscription(subscription, payment_id='free-bypass')
        messages.success(request, f'Your {plan_key} membership has been activated!')
        return render(request, 'payments/success.html', {
            'subscription': subscription,
            'plan_label': dict(Subscription._meta.get_field('plan').choices).get(plan_key, plan_key),
            'end_date': subscription.end_date,
            'bypassed': True,
        })

    if not settings_row.key_id or not settings_row.key_secret:
        messages.error(request, 'Razorpay is not configured. Please contact the admin.')
        return redirect('subscribe')

    client = _get_razorpay_client()
    amount_inr = PLAN_PRICES[plan_key]
    amount_paise = amount_inr * 100
    receipt = f"mcqplatform-{request.user.id}-{plan_key}-{int(time.time())}"

    try:
        order = client.order.create({
            'amount': amount_paise,
            'currency': 'INR',
            'receipt': receipt,
            'payment_capture': 1,
            'notes': {
                'user_id': str(request.user.id),
                'plan': plan_key,
            },
        })
    except Exception as exc:
        messages.error(request, 'Unable to create Razorpay order. Please try again later.')
        return redirect('subscribe')

    start_date, end_date = _subscription_dates_for_user(request.user, plan_key)
    Subscription.objects.update_or_create(
        razorpay_order_id=order.get('id'),
        defaults={
            'user': request.user,
            'plan': plan_key,
            'start_date': start_date,
            'end_date': end_date,
            'payment_reference': order.get('id', ''),
            'amount': amount_inr,
            'currency': 'INR',
            'payment_status': 'pending',
            'razorpay_payment_id': '',
            'razorpay_signature': '',
            'is_active': False,
        },
    )

    return render(request, 'payments/checkout.html', {
        'plan_key': plan_key,
        'plan_label': dict(Subscription._meta.get_field('plan').choices)[plan_key],
        'amount': amount_inr,
        'amount_paise': amount_paise,
        'order_id': order.get('id'),
        'razorpay_key_id': settings_row.key_id,
        'user_email': request.user.email,
        'webhook_url': _get_webhook_url(request),
    })


@login_required
@require_POST
def payment_success(request):
    order_id = request.POST.get('razorpay_order_id', '').strip()
    payment_id = request.POST.get('razorpay_payment_id', '').strip()
    signature = request.POST.get('razorpay_signature', '').strip()
    plan_key = request.POST.get('plan', '').strip()

    if not order_id or not payment_id or not signature or plan_key not in PLAN_PRICES:
        return HttpResponseBadRequest('Missing or invalid payment details.')

    try:
        client = _get_razorpay_client()
        client.utility.verify_payment_signature({
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature,
        })
    except Exception as exc:
        messages.error(request, 'Payment verification failed. Please contact support if the amount was charged.')
        return redirect(f"{reverse('payment_failure')}?reason=Verification failed")

    start_date, end_date = _subscription_dates_for_user(request.user, plan_key)

    subscription, created = Subscription.objects.get_or_create(
        razorpay_order_id=order_id,
        defaults={
            'user': request.user,
            'plan': plan_key,
            'start_date': start_date,
            'end_date': end_date,
            'payment_reference': payment_id,
            'amount': PLAN_PRICES[plan_key],
            'currency': 'INR',
            'payment_status': 'captured',
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature,
            'is_active': True,
        },
    )
    if not created:
        subscription.user = request.user
        subscription.plan = plan_key
        subscription.start_date = subscription.start_date or start_date
        subscription.end_date = subscription.end_date or end_date
        subscription.amount = PLAN_PRICES[plan_key]
        subscription.currency = 'INR'
        subscription.save()

    _activate_subscription(subscription, payment_id=payment_id, signature=signature)

    return render(request, 'payments/success.html', {
        'subscription': subscription,
        'plan_label': dict(Subscription._meta.get_field('plan').choices).get(plan_key, plan_key),
        'end_date': subscription.end_date,
    })


@login_required
def payment_failure(request):
    reason = request.GET.get('reason', 'Payment was not completed. Please try again.')
    order_id = request.GET.get('order_id', '').strip()
    payment_id = request.GET.get('payment_id', '').strip()
    if order_id:
        Subscription.objects.filter(
            user=request.user,
            razorpay_order_id=order_id,
            payment_status='pending',
        ).update(
            payment_status='failed',
            is_active=False,
            razorpay_payment_id=payment_id,
            payment_reference=payment_id or order_id,
        )
    return render(request, 'payments/failure.html', {'reason': reason, 'order_id': order_id})


@login_required
def payment_history(request):
    subscriptions = Subscription.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'payments/history.html', {'subscriptions': subscriptions})


@csrf_exempt
def razorpay_webhook(request):
    settings_row = _get_razorpay_settings()
    signature = request.META.get('HTTP_X_RAZORPAY_SIGNATURE', '')
    body = request.body.decode('utf-8')

    if not signature or not settings_row.webhook_secret:
        return HttpResponseForbidden('Webhook signature missing or webhook secret not configured.')

    client = _get_razorpay_client()
    try:
        client.utility.verify_webhook_signature(body, signature, settings_row.webhook_secret)
    except Exception:
        return HttpResponseForbidden('Invalid webhook signature.')

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON payload.')

    event_type = payload.get('event')
    event = RazorpayWebhookEvent.objects.create(
        event_id=payload.get('id', ''),
        event_type=event_type or 'unknown',
        payload=payload,
    )

    try:
        if event_type == 'payment.captured':
            payment = payload.get('payload', {}).get('payment', {}).get('entity', {})
            order_id = payment.get('order_id')
            payment_id = payment.get('id')
            if order_id:
                subscription = Subscription.objects.filter(razorpay_order_id=order_id).first()
                if subscription:
                    _activate_subscription(subscription, payment_id=payment_id)
                else:
                    order = client.order.fetch(order_id)
                    notes = order.get('notes', {})
                    plan_key = notes.get('plan')
                    user_id = notes.get('user_id')
                    user = User.objects.filter(pk=user_id).first()
                    if user and plan_key in PLAN_PRICES:
                        start_date, end_date = _subscription_dates_for_user(user, plan_key)
                        subscription = Subscription.objects.create(
                            user=user,
                            plan=plan_key,
                            start_date=start_date,
                            end_date=end_date,
                            payment_reference=payment_id,
                            amount=PLAN_PRICES[plan_key],
                            currency='INR',
                            payment_status='pending',
                            razorpay_order_id=order_id,
                            razorpay_payment_id=payment_id,
                            is_active=False,
                        )
                        _activate_subscription(subscription, payment_id=payment_id)

        elif event_type == 'payment.failed':
            payment = payload.get('payload', {}).get('payment', {}).get('entity', {})
            order_id = payment.get('order_id')
            payment_id = payment.get('id', '')
            subscription = Subscription.objects.filter(razorpay_order_id=order_id).first()
            if subscription:
                subscription.payment_status = 'failed'
                subscription.razorpay_payment_id = payment_id
                subscription.payment_reference = payment_id or order_id
                subscription.is_active = False
                subscription.save()

        event.processed = True
        event.save(update_fields=['processed'])
    except Exception as exc:
        event.error_message = str(exc)
        event.save(update_fields=['error_message'])
        return HttpResponseBadRequest('Webhook received but could not be processed.')

    return HttpResponse('OK')

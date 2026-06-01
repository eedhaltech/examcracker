from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Avg, Sum, Max
from django.core.paginator import Paginator

from quiz.models import Attempt, Answer
from accounts.models import UserTopicLevel
from payments.models import Subscription


@login_required
def dashboard(request):
    user = request.user
    is_member = request.is_member
    context = {'is_member': is_member}

    # ── PAST RECORDS (all users see their own history) ──────────────────────
    all_attempts = (
        Attempt.objects.filter(user=user, is_complete=True)
        .select_related('subtopic__topic__course')
        .order_by('-started_at')
    )

    # Paginate attempt history
    paginator = Paginator(all_attempts, 10)
    page_obj  = paginator.get_page(request.GET.get('page', 1))
    context['page_obj'] = page_obj

    # Overall stats (all users)
    overall = all_attempts.aggregate(
        total=Count('id'),
        avg_score=Avg('score'),
        best_score=Max('score'),
    )
    context['overall'] = overall

    # Streak: consecutive days with at least one attempt
    context['streak'] = _calc_streak(user)

    # ── PURCHASE / MEMBERSHIP RECORDS ────────────────────────────────────────
    context['subscriptions'] = Subscription.objects.filter(user=user).order_by('-created_at')[:10]

    # ── ANALYTICS (members only or when paywalls off) ────────────────────────
    if is_member:
        ten_days_ago = timezone.now() - timedelta(days=10)

        frequent = (
            Attempt.objects.filter(user=user, started_at__gte=ten_days_ago, is_complete=True)
            .values('subtopic__name', 'subtopic__slug', 'subtopic__topic__course__name')
            .annotate(attempt_count=Count('id'), avg_score=Avg('score'))
            .order_by('-attempt_count')[:10]
        )
        context['frequent_categories'] = list(frequent)

        donut_qs = (
            UserTopicLevel.objects.filter(user=user)
            .select_related('subtopic__topic__course')
            .order_by('-total_attempted')[:5]
        )
        donut_data = [
            {'label': obj.subtopic.name, 'value': round(obj.accuracy, 1)}
            for obj in donut_qs
        ]
        context['donut_data']      = donut_data
        context['donut_data_json'] = donut_data
        context['weak_areas']      = [d for d in donut_data if d['value'] < 40]
        context['total_attempts']  = all_attempts.count()

    return render(request, 'analytics/dashboard.html', context)


def _calc_streak(user):
    """Count consecutive days (ending today) with at least one completed attempt."""
    from quiz.models import Attempt
    today = timezone.now().date()
    streak = 0
    day = today
    while True:
        if Attempt.objects.filter(user=user, started_at__date=day, is_complete=True).exists():
            streak += 1
            day -= timedelta(days=1)
        else:
            break
        if streak > 365:
            break
    return streak

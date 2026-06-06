import io
import json
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Count, Avg, Sum, Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils.text import slugify
from django.core.paginator import Paginator

from questions.models import Course, Topic, SubTopic, Question, Option, Syllabus, QuestionLevelTransition
from questions.level_config import LevelConfig
from questions.import_logic import import_questions_from_csv, import_simple_csv, import_section_csv
from accounts.models import UserProfile, DailyAttemptLog
from payments.models import Subscription, PLAN_DAYS
from ads.models import PromoAd
from quiz.models import Attempt

from .decorators import staff_required

# Razorpay settings management in staff panel
from django import forms
from payments.models import RazorpaySettings


class RazorpaySettingsForm(forms.ModelForm):
    razorpay_enabled = forms.BooleanField(
        label='Enable Razorpay Payments',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'style': 'width:auto; height:auto; display:inline-block; vertical-align:middle;',
        }),
        help_text='Uncheck this to bypass payments and allow instant subscription activation.',
    )
    key_id = forms.CharField(
        label='Razorpay Key ID',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'panel-input',
            'placeholder': 'rzp_test_xxxxxxxxxxxxx',
            'autocomplete': 'off',
        }),
        help_text='Public Key ID used by Razorpay Checkout.',
    )
    key_secret = forms.CharField(
        label='Razorpay Key Secret',
        required=False,
        widget=forms.PasswordInput(render_value=False, attrs={
            'class': 'panel-input',
            'placeholder': 'Leave blank to keep the existing secret',
            'autocomplete': 'new-password',
        }),
        help_text='Keep this secret secure. Leave blank to preserve the existing secret.'
    )
    webhook_secret = forms.CharField(
        label='Razorpay Webhook Secret',
        required=False,
        widget=forms.PasswordInput(render_value=False, attrs={
            'class': 'panel-input',
            'placeholder': 'Leave blank to keep the existing webhook secret',
            'autocomplete': 'new-password',
        }),
        help_text='Used to verify incoming Razorpay webhook payloads. Leave blank to preserve existing secret.'
    )
    webhook_url = forms.URLField(
        label='Razorpay Webhook URL',
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'panel-input',
            'placeholder': 'https://your-domain.com/subscribe/webhook/',
            'autocomplete': 'off',
        }),
        help_text='Use this endpoint in the Razorpay Dashboard. Leave blank to use the built-in webhook URL.',
    )

    class Meta:
        model = RazorpaySettings
        fields = ['razorpay_enabled', 'key_id', 'key_secret', 'webhook_secret', 'webhook_url']

    def clean_key_secret(self):
        key_secret = self.cleaned_data.get('key_secret')
        if key_secret in (None, '') and self.instance.pk and self.instance.key_secret:
            return self.instance.key_secret
        # Only require if enabled
        if self.cleaned_data.get('razorpay_enabled') and not key_secret:
            raise forms.ValidationError('Razorpay Key Secret is required when enabled.')
        return key_secret

    def clean_webhook_secret(self):
        webhook_secret = self.cleaned_data.get('webhook_secret')
        if webhook_secret in (None, '') and self.instance.pk and self.instance.webhook_secret:
            return self.instance.webhook_secret
        return webhook_secret

    def clean_key_id(self):
        key_id = self.cleaned_data.get('key_id', '').strip()
        if self.cleaned_data.get('razorpay_enabled'):
            if not key_id:
                raise forms.ValidationError('Razorpay Key ID is required when enabled.')
            if not key_id.startswith('rzp_'):
                raise forms.ValidationError('Enter a valid Razorpay Key ID, for example rzp_test_xxxxxxxxxxxxx.')
        return key_id


def _clear_home_cache():
    """Clear cached syllabuses and courses so the home page reflects changes immediately."""
    from django.core.cache import cache
    cache.delete('all_syllabuses')
    cache.delete('all_courses')


@staff_required
def razorpay_settings(request):
    """Staff panel page to view and edit Razorpay configuration stored in the DB."""
    obj, _ = RazorpaySettings.objects.get_or_create(id=1)
    if request.method == 'POST':
        form = RazorpaySettingsForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Razorpay settings updated.')
            return redirect('panel_razorpay_settings')
        else:
            messages.error(request, 'Please fix the errors below.')
    else:
        form = RazorpaySettingsForm(instance=obj)

    return render(request, 'panel/razorpay_settings.html', {
        'form': form,
        'section': 'razorpay',
        'page_title': 'Razorpay Settings',
    })


@staff_required
def question_transitions(request):
    """View to show the history of question level and difficulty transitions."""
    syllabus_id = request.GET.get('syllabus')
    course_id = request.GET.get('course')
    
    qs = QuestionLevelTransition.objects.all().order_by('-created_at')
    
    if syllabus_id:
        qs = qs.filter(question__subtopic__topic__course__syllabus_id=syllabus_id)
    if course_id:
        qs = qs.filter(question__subtopic__topic__course_id=course_id)
        
    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    
    syllabuses = Syllabus.objects.all().order_by('name')
    courses = Course.objects.all().order_by('name')
    
    return render(request, 'panel/question_transitions.html', {
        'page_obj': page_obj,
        'syllabuses': syllabuses,
        'courses': courses,
        'selected_syllabus': syllabus_id,
        'selected_course': course_id,
        'section': 'questions',
        'page_title': 'Question Transitions',
    })


# ─── DASHBOARD ────────────────────────────────────────────────────────────────

@staff_required
def dashboard(request):
    today = timezone.now().date()
    week_ago = timezone.now() - timedelta(days=7)

    stats = {
        'total_users':     User.objects.count(),
        'total_members':   UserProfile.objects.filter(is_member=True).count(),
        'total_questions': Question.objects.count(),
        'total_attempts':  Attempt.objects.filter(is_complete=True).count(),
        'new_users_week':  User.objects.filter(date_joined__gte=week_ago).count(),
        'attempts_today':  Attempt.objects.filter(started_at__date=today).count(),
        'total_courses':   Course.objects.count(),
        'active_ads':      PromoAd.objects.filter(is_active=True).count(),
    }

    # Recent signups
    recent_users = User.objects.select_related('profile').order_by('-date_joined')[:8]

    # Top attempted subtopics
    top_subtopics = (
        Attempt.objects.filter(is_complete=True)
        .values('subtopic__name')
        .annotate(count=Count('id'), avg=Avg('score'))
        .order_by('-count')[:6]
    )

    # Attempts per day (last 7 days) for mini chart
    daily_attempts = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        cnt = Attempt.objects.filter(started_at__date=d).count()
        daily_attempts.append({'date': d.strftime('%d %b'), 'count': cnt})

    return render(request, 'panel/dashboard.html', {
        'stats': stats,
        'recent_users': recent_users,
        'top_subtopics': top_subtopics,
        'daily_attempts_json': json.dumps(daily_attempts),
        'section': 'dashboard',
    })


# ─── USERS ────────────────────────────────────────────────────────────────────

@staff_required
def users_list(request):
    q = request.GET.get('q', '').strip()
    filter_type = request.GET.get('filter', 'all')

    qs = User.objects.select_related('profile').order_by('-date_joined')
    if q:
        qs = qs.filter(Q(email__icontains=q) | Q(username__icontains=q))
    if filter_type == 'members':
        qs = qs.filter(profile__is_member=True)
    elif filter_type == 'free':
        qs = qs.filter(profile__is_member=False)
    elif filter_type == 'staff':
        qs = qs.filter(is_staff=True)

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'panel/users_list.html', {
        'page_obj': page_obj,
        'q': q,
        'filter_type': filter_type,
        'section': 'users',
    })


@staff_required
def user_detail(request, user_id):
    u = get_object_or_404(User, pk=user_id)
    profile, _ = UserProfile.objects.get_or_create(user=u)
    subscriptions = Subscription.objects.filter(user=u).order_by('-created_at')
    attempts = Attempt.objects.filter(user=u, is_complete=True).order_by('-started_at')[:10]

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'toggle_staff':
            u.is_staff = not u.is_staff
            u.save()
            messages.success(request, f"Staff status {'enabled' if u.is_staff else 'disabled'} for {u.email}")

        elif action == 'activate_membership':
            plan = request.POST.get('plan', 'basic')
            days = PLAN_DAYS.get(plan, 30)
            start = timezone.now().date()
            end = start + timedelta(days=days)
            Subscription.objects.create(
                user=u, plan=plan, start_date=start, end_date=end,
                payment_reference='manual-admin', is_active=True
            )
            profile.is_member = True
            profile.membership_expires = end
            profile.save()
            messages.success(request, f"Membership activated for {u.email} until {end}")

        elif action == 'revoke_membership':
            profile.is_member = False
            profile.membership_expires = None
            profile.save()
            Subscription.objects.filter(user=u, is_active=True).update(is_active=False)
            messages.success(request, f"Membership revoked for {u.email}")

        elif action == 'reset_attempts':
            DailyAttemptLog.objects.filter(user=u, date=timezone.now().date()).update(attempt_count=0)
            messages.success(request, f"Daily attempt count reset for {u.email}")

        return redirect('panel_user_detail', user_id=user_id)

    return render(request, 'panel/user_detail.html', {
        'u': u,
        'profile': profile,
        'subscriptions': subscriptions,
        'attempts': attempts,
        'plan_choices': [('basic', '30 days — ₹10'), ('standard', '180 days — ₹50'), ('premium', '360 days — ₹100')],
        'section': 'users',
    })


# ─── QUESTIONS ────────────────────────────────────────────────────────────────

@staff_required
def questions_list(request):
    q = request.GET.get('q', '').strip()
    course_id = request.GET.get('course', '')
    syllabus_id = request.GET.get('syllabus', '')
    level = request.GET.get('level', '')

    qs = Question.objects.select_related('subtopic__topic__course__syllabus').order_by('-id')
    if q:
        qs = qs.filter(body__icontains=q)
    if syllabus_id:
        qs = qs.filter(subtopic__topic__course__syllabus_id=syllabus_id)
    if course_id:
        qs = qs.filter(subtopic__topic__course_id=course_id)
    if level:
        qs = qs.filter(level=level)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    # Filter courses by syllabus if selected
    if syllabus_id:
        courses_qs = Course.objects.filter(syllabus_id=syllabus_id)
    else:
        courses_qs = Course.objects.select_related('syllabus').all()

    return render(request, 'panel/questions_list.html', {
        'page_obj': page_obj,
        'courses': courses_qs,
        'syllabuses': Syllabus.objects.all(),
        'q': q,
        'course_id': course_id,
        'syllabus_id': syllabus_id,
        'level': level,
        'section': 'questions',
    })


@staff_required
def question_add(request):
    syllabuses = Syllabus.objects.all().order_by('order', 'name')
    courses = Course.objects.select_related('syllabus').prefetch_related('topics__subtopics').all()

    if request.method == 'POST':
        subtopic_id = request.POST.get('subtopic')
        body = request.POST.get('body', '').strip()
        explanation = request.POST.get('explanation', '').strip()
        difficulty = request.POST.get('difficulty', 'medium')
        level = int(request.POST.get('level', 1))
        question_type = request.POST.get('question_type', 'theory')
        correct = request.POST.get('correct_option', 'A').upper()

        if not body or not subtopic_id:
            messages.error(request, 'Question body and sub-topic are required.')
        else:
            subtopic = get_object_or_404(SubTopic, pk=subtopic_id)
            q = Question.objects.create(
                subtopic=subtopic, created_by=request.user, body=body, explanation=explanation,
                difficulty=difficulty, level=level, question_type=question_type,
            )
            if request.FILES.get('image'):
                q.image = request.FILES['image']
                q.save()

            for label in ['A', 'B', 'C', 'D']:
                text = request.POST.get(f'option_{label}', '').strip()
                if text:
                    Option.objects.create(
                        question=q, label=label, text=text,
                        is_correct=(label == correct)
                    )
            messages.success(request, f'Question added successfully (ID {q.id})')
            return redirect('panel_questions')

    return render(request, 'panel/question_form.html', {
        'syllabuses': syllabuses,
        'courses': courses,
        'action': 'Add',
        'section': 'questions',
    })


@staff_required
def question_edit(request, question_id):
    question = get_object_or_404(Question, pk=question_id)
    syllabuses = Syllabus.objects.all().order_by('order', 'name')
    courses = Course.objects.select_related('syllabus').prefetch_related('topics__subtopics').all()
    options = {o.label: o for o in question.options.all()}

    if request.method == 'POST':
        question.body = request.POST.get('body', '').strip()
        question.explanation = request.POST.get('explanation', '').strip()
        question.difficulty = request.POST.get('difficulty', 'medium')
        question.level = int(request.POST.get('level', 1))
        question.question_type = request.POST.get('question_type', 'theory')
        subtopic_id = request.POST.get('subtopic')
        if subtopic_id:
            question.subtopic_id = subtopic_id
        if request.FILES.get('image'):
            question.image = request.FILES['image']
        question.save()

        correct = request.POST.get('correct_option', 'A').upper()
        for label in ['A', 'B', 'C', 'D']:
            text = request.POST.get(f'option_{label}', '').strip()
            if text:
                opt, _ = Option.objects.get_or_create(question=question, label=label)
                opt.text = text
                opt.is_correct = (label == correct)
                opt.save()

        messages.success(request, 'Question updated.')
        return redirect('panel_questions')

    correct_label = next((o.label for o in question.options.all() if o.is_correct), 'A')
    return render(request, 'panel/question_form.html', {
        'question': question,
        'options': options,
        'correct_label': correct_label,
        'syllabuses': syllabuses,
        'courses': courses,
        'action': 'Edit',
        'section': 'questions',
    })


@staff_required
@require_POST
def question_delete(request, question_id):
    question = get_object_or_404(Question, pk=question_id)
    question.delete()
    messages.success(request, 'Question deleted.')
    return redirect('panel_questions')


@staff_required
def csv_import(request):
    courses = Course.objects.select_related('syllabus').prefetch_related('topics__subtopics').all()
    syllabuses = Syllabus.objects.all()

    if request.method == 'POST':
        f = request.FILES.get('csv_file')
        fmt = request.POST.get('format', 'detailed')

        if not f:
            messages.error(request, 'No file selected.')
            return redirect('panel_csv_import')
        if not f.name.endswith('.csv'):
            messages.error(request, 'File must be a .csv')
            return redirect('panel_csv_import')

        try:
            if fmt == 'simple':
                subtopic_id = request.POST.get('subtopic_id')
                level = int(request.POST.get('level', 1))
                difficulty = request.POST.get('difficulty', 'medium')
                if not subtopic_id:
                    messages.error(request, 'Please select a sub-topic for simple import.')
                    return redirect('panel_csv_import')
                result = import_simple_csv(
                    f,
                    subtopic_id=subtopic_id,
                    level=level,
                    difficulty=difficulty,
                    created_by=request.user,
                )
            elif fmt == 'section':
                topic_id = request.POST.get('topic_id')
                level = int(request.POST.get('level', 1))
                difficulty = request.POST.get('difficulty', 'medium')
                if not topic_id:
                    messages.error(request, 'Please select a topic for section import.')
                    return redirect('panel_csv_import')
                result = import_section_csv(
                    f,
                    topic_id=topic_id,
                    level=level,
                    difficulty=difficulty,
                    created_by=request.user,
                )
            else:
                result = import_questions_from_csv(f, created_by=request.user)

            messages.success(request,
                f"Done: {result['inserted']} inserted, "
                f"{result['skipped']} skipped, {result['errors']} errors.")
            for d in result['error_details']:
                messages.warning(request, d)

        except Exception as e:
            messages.error(request, f'Import failed: {e}')

        return redirect('panel_csv_import')

    return render(request, 'panel/csv_import.html', {
        'courses': courses,
        'syllabuses': syllabuses,
        'section': 'questions',
    })


# ─── COURSES ──────────────────────────────────────────────────────────────────

@staff_required
def courses_list(request):
    syllabus_id = request.GET.get('syllabus', '')
    syllabuses = Syllabus.objects.all().order_by('order', 'name')

    # Build grouped structure: list of (syllabus_or_none, [courses])
    all_courses = Course.objects.select_related('syllabus').prefetch_related(
        'topics__subtopics__questions'
    ).annotate(
        q_count=Count('topics__subtopics__questions')
    ).order_by('order', 'name')

    if syllabus_id:
        all_courses = all_courses.filter(syllabus_id=syllabus_id)

    # Group courses by syllabus
    groups = []
    for syl in syllabuses:
        syl_courses = [c for c in all_courses if c.syllabus_id == syl.id]
        groups.append({'syllabus': syl, 'courses': syl_courses})

    # Orphan courses (no syllabus)
    orphans = [c for c in all_courses if c.syllabus_id is None]
    if orphans:
        groups.append({'syllabus': None, 'courses': orphans})

    return render(request, 'panel/courses_list.html', {
        'groups': groups,
        'syllabuses': syllabuses,
        'selected_syllabus': syllabus_id,
        'section': 'courses',
    })


@staff_required
def course_add(request):
    syllabuses = Syllabus.objects.all()
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        order = int(request.POST.get('order', 0))
        syllabus_id = request.POST.get('syllabus_id') or None
        if not name:
            messages.error(request, 'Name is required.')
        else:
            # Allow same name under different syllabuses — make slug unique
            base_slug = slugify(name)
            slug = base_slug
            counter = 1
            while Course.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            c = Course.objects.create(name=name, slug=slug, order=order, syllabus_id=syllabus_id)
            if request.FILES.get('icon'):
                c.icon = request.FILES['icon']
                c.save()
            _clear_home_cache()
            messages.success(request, f'Course "{name}" created.')
            return redirect('panel_courses')
    return render(request, 'panel/course_form.html', {
        'action': 'Add', 'section': 'courses', 'syllabuses': syllabuses,
    })


@staff_required
def course_edit(request, course_id, syllabus_id=None):
    course = get_object_or_404(Course.objects.select_related('syllabus'), pk=course_id)
    syllabuses = Syllabus.objects.all()
    if request.method == 'POST':
        course.name = request.POST.get('name', course.name).strip()
        course.order = int(request.POST.get('order', course.order))
        course.syllabus_id = request.POST.get('syllabus_id') or None
        if request.FILES.get('icon'):
            course.icon = request.FILES['icon']
        course.save()
        _clear_home_cache()
        messages.success(request, 'Course updated.')
        if course.syllabus_id:
            return redirect('syllabus_courses', syllabus_id=course.syllabus_id)
        return redirect('panel_courses')
    return render(request, 'panel/course_form.html', {
        'course': course, 'action': 'Edit', 'section': 'courses', 'syllabuses': syllabuses,
    })


@staff_required
@require_POST
def course_delete(request, course_id, syllabus_id=None):
    course = get_object_or_404(Course, pk=course_id)
    syl_id = course.syllabus_id
    course.delete()
    _clear_home_cache()
    messages.success(request, 'Course deleted.')
    if syl_id:
        return redirect('syllabus_courses', syllabus_id=syl_id)
    return redirect('panel_courses')


@staff_required
def course_detail(request, course_id):
    """Drill-down: show topics for a course."""
    course = get_object_or_404(Course.objects.select_related('syllabus'), pk=course_id)
    topics = Topic.objects.filter(course=course).prefetch_related('subtopics').order_by('order', 'name')
    return render(request, 'panel/course_detail.html', {
        'course': course,
        'topics': topics,
        'section': 'courses',
    })


# ─── TOPICS ───────────────────────────────────────────────────────────────────

@staff_required
def topic_add(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        order = int(request.POST.get('order', 0))
        if name:
            slug = slugify(name)
            Topic.objects.get_or_create(course=course, name=name, defaults={'slug': slug, 'order': order})
            _clear_home_cache()
            messages.success(request, f'Topic "{name}" added.')
        return redirect('panel_course_detail', course_id=course_id)
    return render(request, 'panel/topic_form.html', {'course': course, 'section': 'courses'})


@staff_required
@require_POST
def topic_delete(request, topic_id):
    topic = get_object_or_404(Topic.objects.select_related('course__syllabus'), pk=topic_id)
    course_id = topic.course_id
    syl_id = topic.course.syllabus_id
    topic.delete()
    _clear_home_cache()
    messages.success(request, 'Topic deleted.')
    if syl_id:
        return redirect('course_topics', syllabus_id=syl_id, course_id=course_id)
    return redirect('panel_course_detail', course_id=course_id)


@staff_required
def topic_detail(request, topic_id):
    """Drill-down: show subtopics for a topic."""
    topic = get_object_or_404(Topic.objects.select_related('course__syllabus'), pk=topic_id)
    subtopics = SubTopic.objects.filter(topic=topic).annotate(
        q_count=Count('questions')
    ).order_by('order', 'name')
    return render(request, 'panel/topic_detail.html', {
        'topic': topic,
        'subtopics': subtopics,
        'section': 'courses',
    })


# ─── SUBTOPICS ────────────────────────────────────────────────────────────────

@staff_required
def subtopic_add(request, topic_id):
    topic = get_object_or_404(Topic, pk=topic_id)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        order = int(request.POST.get('order', 0))
        if name:
            slug = slugify(name)
            SubTopic.objects.get_or_create(topic=topic, name=name, defaults={'slug': slug, 'order': order})
            _clear_home_cache()
            messages.success(request, f'Sub-topic "{name}" added.')
        return redirect('panel_topic_detail', topic_id=topic_id)
    return render(request, 'panel/subtopic_form.html', {'topic': topic, 'section': 'courses'})


@staff_required
@require_POST
def subtopic_delete(request, subtopic_id):
    st = get_object_or_404(SubTopic.objects.select_related('topic__course__syllabus'), pk=subtopic_id)
    topic_id = st.topic_id
    course_id = st.topic.course_id
    syl_id = st.topic.course.syllabus_id
    st.delete()
    _clear_home_cache()
    messages.success(request, 'Sub-topic deleted.')
    if syl_id:
        return redirect('topic_subtopics', syllabus_id=syl_id, course_id=course_id, topic_id=topic_id)
    return redirect('panel_topic_detail', topic_id=topic_id)


# ─── ADS ──────────────────────────────────────────────────────────────────────

@staff_required
def ads_list(request):
    ads = PromoAd.objects.all().order_by('-created_at')
    return render(request, 'panel/ads_list.html', {'ads': ads, 'section': 'ads'})


@staff_required
def ad_add(request):
    if request.method == 'POST':
        ad = PromoAd(
            title=request.POST.get('title', '').strip(),
            position=request.POST.get('position', 'display_sidebar'),
            html_content=request.POST.get('html_content', '').strip(),
            link_url=request.POST.get('link_url', '').strip(),
            is_active=request.POST.get('is_active') == 'on',
            show_to_members=request.POST.get('show_to_members') == 'on',
        )
        if request.FILES.get('image'):
            ad.image = request.FILES['image']
        ad.save()
        messages.success(request, f'Ad "{ad.title}" created.')
        return redirect('panel_ads')
    return render(request, 'panel/ad_form.html', {
        'action': 'Add',
        'positions': PromoAd._meta.get_field('position').choices,
        'section': 'ads',
    })


@staff_required
def ad_edit(request, ad_id):
    ad = get_object_or_404(PromoAd, pk=ad_id)
    if request.method == 'POST':
        ad.title = request.POST.get('title', '').strip()
        ad.position = request.POST.get('position', ad.position)
        ad.html_content = request.POST.get('html_content', '').strip()
        ad.link_url = request.POST.get('link_url', '').strip()
        ad.is_active = request.POST.get('is_active') == 'on'
        ad.show_to_members = request.POST.get('show_to_members') == 'on'
        if request.FILES.get('image'):
            ad.image = request.FILES['image']
        ad.save()
        messages.success(request, 'Ad updated.')
        return redirect('panel_ads')
    return render(request, 'panel/ad_form.html', {
        'ad': ad,
        'action': 'Edit',
        'positions': PromoAd._meta.get_field('position').choices,
        'section': 'ads',
    })


@staff_required
@require_POST
def ad_delete(request, ad_id):
    ad = get_object_or_404(PromoAd, pk=ad_id)
    ad.delete()
    messages.success(request, 'Ad deleted.')
    return redirect('panel_ads')


@staff_required
@require_POST
def ad_toggle(request, ad_id):
    ad = get_object_or_404(PromoAd, pk=ad_id)
    ad.is_active = not ad.is_active
    ad.save()
    return JsonResponse({'active': ad.is_active})


# ─── MEMBERSHIPS ──────────────────────────────────────────────────────────────

@staff_required
def memberships_list(request):
    subs = Subscription.objects.select_related('user').order_by('-created_at')
    status = request.GET.get('status', '').strip()
    if status in {'pending', 'captured', 'failed'}:
        subs = subs.filter(payment_status=status)
    paginator = Paginator(subs, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'panel/memberships_list.html', {
        'page_obj': page_obj,
        'status': status,
        'section': 'memberships',
    })


@staff_required
@require_POST
def membership_payment_action(request, subscription_id):
    sub = get_object_or_404(Subscription.objects.select_related('user'), pk=subscription_id)
    action = request.POST.get('action')

    if action == 'mark_captured':
        sub.payment_status = 'captured'
        sub.is_active = True
        sub.save()
        profile, _ = UserProfile.objects.get_or_create(user=sub.user)
        profile.is_member = True
        profile.membership_expires = sub.end_date
        profile.save()
        messages.success(request, 'Payment marked as captured and membership activated.')
    elif action == 'mark_failed':
        sub.payment_status = 'failed'
        sub.is_active = False
        sub.save()
        messages.success(request, 'Payment marked as failed.')
    elif action == 'deactivate':
        sub.is_active = False
        sub.save()
        profile, _ = UserProfile.objects.get_or_create(user=sub.user)
        if profile.membership_expires == sub.end_date:
            profile.is_member = False
            profile.membership_expires = None
            profile.save()
        messages.success(request, 'Membership deactivated.')
    else:
        messages.error(request, 'Unknown payment action.')

    return redirect('panel_memberships')


@staff_required
def membership_grant(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        plan = request.POST.get('plan', 'basic')
        try:
            u = User.objects.get(email=email)
            profile, _ = UserProfile.objects.get_or_create(user=u)
            days = PLAN_DAYS.get(plan, 30)
            start = timezone.now().date()
            end = start + timedelta(days=days)
            Subscription.objects.create(
                user=u, plan=plan, start_date=start, end_date=end,
                payment_reference='manual-panel', is_active=True
            )
            profile.is_member = True
            profile.membership_expires = end
            profile.save()
            messages.success(request, f'Membership granted to {email} until {end}')
        except User.DoesNotExist:
            messages.error(request, f'No user found with email: {email}')
        return redirect('panel_memberships')

    return render(request, 'panel/membership_grant.html', {
        'plan_choices': [('basic', '30 days — ₹10'), ('standard', '180 days — ₹50'), ('premium', '360 days — ₹100')],
        'section': 'memberships',
    })


# ─── LEVEL CONFIG ─────────────────────────────────────────────────────────────

@staff_required
def level_config(request):
    # Auto-create missing levels
    existing = set(LevelConfig.objects.values_list('level', flat=True))
    defaults = {1: (False, 'Beginner'), 2: (False, 'Elementary'),
                3: (True, 'Intermediate'), 4: (True, 'Advanced'), 5: (True, 'Expert')}
    for lvl, (paid, label) in defaults.items():
        if lvl not in existing:
            LevelConfig.objects.create(level=lvl, requires_membership=paid, label=label)

    if request.method == 'POST':
        for lvl in range(1, 6):
            lc = LevelConfig.objects.get(level=lvl)
            lc.requires_membership = request.POST.get(f'level_{lvl}_paid') == 'on'
            lc.label = request.POST.get(f'level_{lvl}_label', lc.label).strip()
            lc.description = request.POST.get(f'level_{lvl}_desc', '').strip()
            lc.max_questions = int(request.POST.get(f'level_{lvl}_max_q', 0) or 0)
            lc.save()
        messages.success(request, 'Level access settings saved.')
        return redirect('panel_level_config')

    levels = LevelConfig.objects.order_by('level')
    return render(request, 'panel/level_config.html', {
        'levels': levels, 'section': 'levels'
    })


# ─── PRODUCTS ─────────────────────────────────────────────────────────────────

@staff_required
def products_list(request):
    from products.models import Product
    products = Product.objects.all().order_by('order', '-created_at')
    return render(request, 'panel/products_list.html', {'products': products, 'section': 'products'})


@staff_required
def product_add(request):
    from products.models import Product, PRODUCT_TYPE_CHOICES
    if request.method == 'POST':
        affiliate_url = request.POST.get('affiliate_url', '').strip()
        p = Product(
            title=request.POST.get('title', '').strip(),
            product_type=request.POST.get('product_type', 'book'),
            description=request.POST.get('description', '').strip(),
            affiliate_url=affiliate_url,
            price_display=request.POST.get('price_display', '').strip(),
            badge=request.POST.get('badge', '').strip(),
            is_active=request.POST.get('is_active') == 'on',
            order=int(request.POST.get('order', 0)),
        )
        if request.FILES.get('image'):
            p.image = request.FILES['image']
        if request.FILES.get('download_file'):
            p.download_file = request.FILES['download_file']

        if not p.title:
            messages.error(request, 'Please enter a product title.')
            return render(request, 'panel/product_form.html', {
                'action': 'Add', 'type_choices': PRODUCT_TYPE_CHOICES, 'section': 'products', 'product': p
            })

        if not p.affiliate_url and not p.download_file:
            messages.error(request, 'Please provide either an Affiliate/Buy URL or a Download File.')
            return render(request, 'panel/product_form.html', {
                'action': 'Add', 'type_choices': PRODUCT_TYPE_CHOICES, 'section': 'products', 'product': p
            })
        p.save()
        messages.success(request, f'Product "{p.title}" added.')
        return redirect('panel_products')
    from products.models import PRODUCT_TYPE_CHOICES
    return render(request, 'panel/product_form.html', {
        'action': 'Add', 'type_choices': PRODUCT_TYPE_CHOICES, 'section': 'products'
    })


@staff_required
def product_edit(request, product_id):
    from products.models import Product, PRODUCT_TYPE_CHOICES
    p = get_object_or_404(Product, pk=product_id)
    if request.method == 'POST':
        p.title        = request.POST.get('title', p.title).strip()
        p.product_type = request.POST.get('product_type', p.product_type)
        p.description  = request.POST.get('description', '').strip()
        p.affiliate_url= request.POST.get('affiliate_url', '').strip()
        p.price_display= request.POST.get('price_display', '').strip()
        p.badge        = request.POST.get('badge', '').strip()
        p.is_active    = request.POST.get('is_active') == 'on'
        p.order        = int(request.POST.get('order', p.order))
        if request.FILES.get('image'):
            p.image = request.FILES['image']
        if request.FILES.get('download_file'):
            p.download_file = request.FILES['download_file']

        if not p.title:
            messages.error(request, 'Please enter a product title.')
            return render(request, 'panel/product_form.html', {
                'product': p, 'action': 'Edit',
                'type_choices': PRODUCT_TYPE_CHOICES, 'section': 'products'
            })

        if not p.affiliate_url and not p.download_file:
            messages.error(request, 'Please provide either an Affiliate/Buy URL or a Download File.')
            return render(request, 'panel/product_form.html', {
                'product': p, 'action': 'Edit',
                'type_choices': PRODUCT_TYPE_CHOICES, 'section': 'products'
            })
        p.save()
        messages.success(request, 'Product updated.')
        return redirect('panel_products')
    return render(request, 'panel/product_form.html', {
        'product': p, 'action': 'Edit',
        'type_choices': PRODUCT_TYPE_CHOICES, 'section': 'products'
    })


@staff_required
@require_POST
def product_delete(request, product_id):
    from products.models import Product
    p = get_object_or_404(Product, pk=product_id)
    p.delete()
    messages.success(request, 'Product deleted.')
    return redirect('panel_products')


# ─── COMMENTS ─────────────────────────────────────────────────────────────────

@staff_required
def comments_list(request):
    from contact.models import Comment
    status = request.GET.get('status', '')
    qs = Comment.objects.select_related('user').order_by('-created_at')
    if status:
        qs = qs.filter(status=status)
    paginator = Paginator(qs, 20)
    page_obj  = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'panel/comments_list.html', {
        'page_obj': page_obj, 'status': status, 'section': 'comments'
    })


@staff_required
@require_POST
def comment_action(request, comment_id):
    from contact.models import Comment
    comment = get_object_or_404(Comment, pk=comment_id)
    action  = request.POST.get('action')
    if action == 'approve':
        comment.status = 'approved'
        comment.save()
        messages.success(request, 'Comment approved.')
    elif action == 'reject':
        comment.status = 'rejected'
        comment.save()
        messages.success(request, 'Comment rejected.')
    elif action == 'feature':
        comment.status = 'approved'
        comment.is_featured = True
        comment.save()
        messages.success(request, 'Comment featured.')
    elif action == 'unfeature':
        comment.is_featured = False
        comment.save()
        messages.success(request, 'Comment unfeatured.')
    elif action == 'delete':
        comment.delete()
        messages.success(request, 'Comment deleted.')
    return redirect('panel_comments')


# ─── SYLLABUS ─────────────────────────────────────────────────────────────────

@staff_required
def syllabuses_home(request):
    """Level 0: Show all syllabuses as the main Courses entry point."""
    syllabuses = Syllabus.objects.annotate(
        course_count=Count('courses', distinct=True)
    ).order_by('order', 'name')
    return render(request, 'panel/syllabuses_home.html', {
        'syllabuses': syllabuses,
        'section': 'courses',
    })


@staff_required
def syllabus_courses(request, syllabus_id):
    """Level 1: Show courses under a syllabus."""
    syllabus = get_object_or_404(Syllabus, pk=syllabus_id)
    courses = Course.objects.filter(syllabus=syllabus).prefetch_related('topics').annotate(
        topic_count=Count('topics', distinct=True)
    ).order_by('order', 'name')
    return render(request, 'panel/syllabus_courses.html', {
        'syllabus': syllabus,
        'courses': courses,
        'section': 'courses',
    })


@staff_required
def syllabus_course_add(request, syllabus_id):
    """Add a course directly under a syllabus."""
    syllabus = get_object_or_404(Syllabus, pk=syllabus_id)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        order = int(request.POST.get('order', 0))
        if not name:
            messages.error(request, 'Name is required.')
        else:
            base_slug = slugify(name)
            slug = base_slug
            counter = 1
            while Course.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            c = Course.objects.create(name=name, slug=slug, order=order, syllabus=syllabus)
            if request.FILES.get('icon'):
                c.icon = request.FILES['icon']
                c.save()
            _clear_home_cache()
            messages.success(request, f'Course "{name}" created.')
            return redirect('syllabus_courses', syllabus_id=syllabus_id)
    return render(request, 'panel/syllabus_course_add.html', {
        'syllabus': syllabus,
        'section': 'courses',
    })


@staff_required
def course_topics(request, syllabus_id, course_id):
    """Level 2: Show topics under a course."""
    syllabus = get_object_or_404(Syllabus, pk=syllabus_id)
    course = get_object_or_404(Course, pk=course_id, syllabus=syllabus)
    topics = Topic.objects.filter(course=course).prefetch_related('subtopics').annotate(
        subtopic_count=Count('subtopics', distinct=True)
    ).order_by('order', 'name')
    return render(request, 'panel/course_topics.html', {
        'syllabus': syllabus,
        'course': course,
        'topics': topics,
        'section': 'courses',
    })


@staff_required
def course_topic_add(request, syllabus_id, course_id):
    """Add a topic under a course."""
    syllabus = get_object_or_404(Syllabus, pk=syllabus_id)
    course = get_object_or_404(Course, pk=course_id, syllabus=syllabus)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        order = int(request.POST.get('order', 0))
        if name:
            slug = slugify(name)
            Topic.objects.get_or_create(course=course, name=name, defaults={'slug': slug, 'order': order})
            _clear_home_cache()
            messages.success(request, f'Topic "{name}" added.')
        return redirect('course_topics', syllabus_id=syllabus_id, course_id=course_id)
    return render(request, 'panel/course_topic_add.html', {
        'syllabus': syllabus,
        'course': course,
        'section': 'courses',
    })


@staff_required
def topic_subtopics(request, syllabus_id, course_id, topic_id):
    """Level 3: Show sub-topics under a topic."""
    syllabus = get_object_or_404(Syllabus, pk=syllabus_id)
    course = get_object_or_404(Course, pk=course_id, syllabus=syllabus)
    topic = get_object_or_404(Topic, pk=topic_id, course=course)
    subtopics = SubTopic.objects.filter(topic=topic).annotate(
        q_count=Count('questions', distinct=True)
    ).order_by('order', 'name')
    return render(request, 'panel/topic_subtopics.html', {
        'syllabus': syllabus,
        'course': course,
        'topic': topic,
        'subtopics': subtopics,
        'section': 'courses',
    })


@staff_required
def topic_subtopic_add(request, syllabus_id, course_id, topic_id):
    """Add a sub-topic under a topic."""
    syllabus = get_object_or_404(Syllabus, pk=syllabus_id)
    course = get_object_or_404(Course, pk=course_id, syllabus=syllabus)
    topic = get_object_or_404(Topic, pk=topic_id, course=course)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        order = int(request.POST.get('order', 0))
        if name:
            slug = slugify(name)
            SubTopic.objects.get_or_create(topic=topic, name=name, defaults={'slug': slug, 'order': order})
            _clear_home_cache()
            messages.success(request, f'Sub-topic "{name}" added.')
        return redirect('topic_subtopics', syllabus_id=syllabus_id, course_id=course_id, topic_id=topic_id)
    return render(request, 'panel/topic_subtopic_add.html', {
        'syllabus': syllabus,
        'course': course,
        'topic': topic,
        'section': 'courses',
    })


# ─── LEGACY REDIRECTS ─────────────────────────────────────────────────────────

@staff_required
def legacy_course_add(request):
    syllabuses = Syllabus.objects.all()
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        order = int(request.POST.get('order', 0))
        syllabus_id = request.POST.get('syllabus_id') or None
        if not name:
            messages.error(request, 'Name is required.')
        else:
            base_slug = slugify(name)
            slug = base_slug
            counter = 1
            while Course.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            c = Course.objects.create(name=name, slug=slug, order=order, syllabus_id=syllabus_id)
            if request.FILES.get('icon'):
                c.icon = request.FILES['icon']
                c.save()
            _clear_home_cache()
            messages.success(request, f'Course "{name}" created.')
            if syllabus_id:
                return redirect('syllabus_courses', syllabus_id=syllabus_id)
            return redirect('panel_courses')
    return render(request, 'panel/course_form.html', {
        'action': 'Add', 'section': 'courses', 'syllabuses': syllabuses,
    })


@staff_required
def legacy_topic_add(request, course_id):
    course = get_object_or_404(Course.objects.select_related('syllabus'), pk=course_id)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        order = int(request.POST.get('order', 0))
        if name:
            slug = slugify(name)
            Topic.objects.get_or_create(course=course, name=name, defaults={'slug': slug, 'order': order})
            _clear_home_cache()
            messages.success(request, f'Topic "{name}" added.')
        if course.syllabus_id:
            return redirect('course_topics', syllabus_id=course.syllabus_id, course_id=course_id)
        return redirect('panel_course_detail', course_id=course_id)
    return render(request, 'panel/topic_form.html', {'course': course, 'section': 'courses'})


@staff_required
def legacy_subtopic_add(request, topic_id):
    topic = get_object_or_404(Topic.objects.select_related('course__syllabus'), pk=topic_id)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        order = int(request.POST.get('order', 0))
        if name:
            slug = slugify(name)
            SubTopic.objects.get_or_create(topic=topic, name=name, defaults={'slug': slug, 'order': order})
            _clear_home_cache()
            messages.success(request, f'Sub-topic "{name}" added.')
        if topic.course.syllabus_id:
            return redirect('topic_subtopics',
                syllabus_id=topic.course.syllabus_id,
                course_id=topic.course_id,
                topic_id=topic_id)
        return redirect('panel_topic_detail', topic_id=topic_id)
    return render(request, 'panel/subtopic_form.html', {'topic': topic, 'section': 'courses'})


@staff_required
def syllabus_add(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        order = int(request.POST.get('order', 0))
        if not name:
            messages.error(request, 'Name is required.')
        else:
            Syllabus.objects.create(name=name, description=description, order=order)
            _clear_home_cache()
            messages.success(request, f'Syllabus "{name}" created.')
            return redirect('panel_courses')
    return render(request, 'panel/syllabus_form.html', {'action': 'Add', 'section': 'courses'})


@staff_required
def syllabus_edit(request, syllabus_id):
    syllabus = get_object_or_404(Syllabus, pk=syllabus_id)
    if request.method == 'POST':
        syllabus.name = request.POST.get('name', syllabus.name).strip()
        syllabus.description = request.POST.get('description', '').strip()
        syllabus.order = int(request.POST.get('order', syllabus.order))
        syllabus.save()
        _clear_home_cache()
        messages.success(request, 'Syllabus updated.')
        return redirect('panel_courses')
    return render(request, 'panel/syllabus_form.html', {
        'syllabus': syllabus, 'action': 'Edit', 'section': 'courses',
    })


@staff_required
@require_POST
def syllabus_delete(request, syllabus_id):
    syllabus = get_object_or_404(Syllabus, pk=syllabus_id)
    syllabus.delete()
    _clear_home_cache()
    messages.success(request, 'Syllabus deleted.')
    return redirect('panel_courses')


# ─── SYLLABUS JSON API (for frontend dropdowns) ───────────────────────────────

def syllabus_courses_json(request):
    """Return courses for a given syllabus as JSON (used by quiz bar)."""
    syllabus_id = request.GET.get('syllabus_id')
    if not syllabus_id:
        return JsonResponse({'courses': []})
    courses = Course.objects.filter(syllabus_id=syllabus_id).order_by('order', 'name')
    data = [{'id': c.id, 'name': c.name} for c in courses]
    return JsonResponse({'courses': data})


# ─── DRILL-DOWN HIERARCHY ─────────────────────────────────────────────────────

@staff_required
def syllabus_courses(request, syllabus_id):
    """Shows all courses for a specific syllabus."""
    syllabus = get_object_or_404(Syllabus, pk=syllabus_id)
    courses = Course.objects.filter(syllabus=syllabus).prefetch_related('topics').annotate(
        topic_count=Count('topics', distinct=True)
    ).order_by('order', 'name')
    return render(request, 'panel/syllabus_courses.html', {
        'syllabus': syllabus, 'courses': courses, 'section': 'courses',
    })


@staff_required
def syllabus_course_add(request, syllabus_id):
    """Add a course directly under a syllabus."""
    syllabus = get_object_or_404(Syllabus, pk=syllabus_id)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        order = int(request.POST.get('order', 0))
        if not name:
            messages.error(request, 'Name is required.')
        else:
            base_slug = slugify(name)
            slug = base_slug
            counter = 1
            while Course.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            c = Course.objects.create(name=name, slug=slug, order=order, syllabus=syllabus)
            if request.FILES.get('icon'):
                c.icon = request.FILES['icon']
                c.save()
            _clear_home_cache()
            messages.success(request, f'Course "{name}" created.')
            return redirect('syllabus_courses', syllabus_id=syllabus_id)
    return render(request, 'panel/syllabus_course_add.html', {
        'syllabus': syllabus, 'action': 'Add', 'section': 'courses',
    })


@staff_required
def course_topics(request, course_id, syllabus_id=None):
    """Shows all topics for a specific course."""
    course_qs = Course.objects.select_related('syllabus')
    if syllabus_id is not None:
        course_qs = course_qs.filter(syllabus_id=syllabus_id)
    course = get_object_or_404(course_qs, pk=course_id)
    topics = Topic.objects.filter(course=course).annotate(
        subtopic_count=Count('subtopics', distinct=True)
    ).order_by('order', 'name')
    return render(request, 'panel/course_topics.html', {
        'syllabus': course.syllabus, 'course': course, 'topics': topics, 'section': 'courses',
    })


@staff_required
def course_topic_add(request, course_id, syllabus_id=None):
    """Add a topic directly under a course."""
    course_qs = Course.objects.select_related('syllabus')
    if syllabus_id is not None:
        course_qs = course_qs.filter(syllabus_id=syllabus_id)
    course = get_object_or_404(course_qs, pk=course_id)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        order = int(request.POST.get('order', 0))
        if name:
            slug = slugify(name)
            Topic.objects.get_or_create(course=course, name=name, defaults={'slug': slug, 'order': order})
            _clear_home_cache()
            messages.success(request, f'Topic "{name}" added.')
            if course.syllabus_id:
                return redirect('course_topics', syllabus_id=course.syllabus_id, course_id=course_id)
            return redirect('panel_course_detail', course_id=course_id)
    return render(request, 'panel/course_topic_add.html', {
        'syllabus': course.syllabus, 'course': course, 'section': 'courses',
    })


@staff_required
def topic_subtopics(request, topic_id, syllabus_id=None, course_id=None):
    """Shows all subtopics for a specific topic."""
    topic_qs = Topic.objects.select_related('course__syllabus')
    if course_id is not None:
        topic_qs = topic_qs.filter(course_id=course_id)
    if syllabus_id is not None:
        topic_qs = topic_qs.filter(course__syllabus_id=syllabus_id)
    topic = get_object_or_404(topic_qs, pk=topic_id)
    subtopics = SubTopic.objects.filter(topic=topic).annotate(
        q_count=Count('questions', distinct=True)
    ).order_by('order', 'name')
    return render(request, 'panel/topic_subtopics.html', {
        'syllabus': topic.course.syllabus, 'course': topic.course,
        'topic': topic, 'subtopics': subtopics, 'section': 'courses',
    })


@staff_required
def topic_subtopic_add(request, topic_id, syllabus_id=None, course_id=None):
    """Add a subtopic directly under a topic."""
    topic_qs = Topic.objects.select_related('course__syllabus')
    if course_id is not None:
        topic_qs = topic_qs.filter(course_id=course_id)
    if syllabus_id is not None:
        topic_qs = topic_qs.filter(course__syllabus_id=syllabus_id)
    topic = get_object_or_404(topic_qs, pk=topic_id)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        order = int(request.POST.get('order', 0))
        if name:
            slug = slugify(name)
            SubTopic.objects.get_or_create(topic=topic, name=name, defaults={'slug': slug, 'order': order})
            _clear_home_cache()
            messages.success(request, f'Sub-topic "{name}" added.')
            if topic.course.syllabus_id:
                return redirect('topic_subtopics',
                    syllabus_id=topic.course.syllabus_id,
                    course_id=topic.course_id,
                    topic_id=topic_id)
            return redirect('panel_topic_detail', topic_id=topic_id)
    return render(request, 'panel/topic_subtopic_add.html', {
        'syllabus': topic.course.syllabus, 'course': topic.course,
        'topic': topic, 'section': 'courses',
    })

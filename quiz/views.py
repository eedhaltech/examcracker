from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.http import JsonResponse, Http404
import random

from questions.models import SubTopic, Question, Topic, Course
from questions.level_config import is_level_accessible, max_accessible_level, get_level_config_map, get_max_questions
from accounts.utils import check_attempt_allowed, increment_attempt_count
from accounts.models import UserTopicLevel
from .models import Attempt, Answer
from .tasks import update_question_stats, update_user_level_task


QUESTIONS_PER_PAGE = 10


@login_required
def start_quiz(request, subtopic_slug):
    # Use filter().first() instead of get_object_or_404 to avoid MultipleObjectsReturned
    # since slugs are only unique within a topic, not globally.
    subtopic = SubTopic.objects.filter(slug=subtopic_slug).first()
    if not subtopic:
        raise Http404("Subtopic not found")
        
    is_member = request.is_member
    selected_difficulty = request.GET.get('difficulty', 'all').lower()

    # Backend enforcement: Free users can only access Easy on this page
    # If they try to force Medium/Hard/All via URL, we don't strictly redirect here
    # but the frontend popup will block them. For safety, we force 'easy'
    # if they are not members and selected a premium difficulty.
    if not is_member and selected_difficulty in ('medium', 'hard', 'all'):
        selected_difficulty = 'easy'

    if request.method == 'POST':
        allowed, count = check_attempt_allowed(request.user)
        if not allowed:
            return render(request, 'quiz/limit_reached.html', {
                'count': count, 'subtopic': subtopic,
            })

        try:
            user_level = UserTopicLevel.objects.get(user=request.user, subtopic=subtopic)
            current_level = user_level.current_level
        except UserTopicLevel.DoesNotExist:
            current_level = 1

        if not is_level_accessible(current_level, is_member):
            current_level = max_accessible_level(is_member)

        # Allow overriding current level via target_level from POST
        target_level = request.POST.get('target_level')
        if target_level:
            try:
                target_level = int(target_level)
                if is_level_accessible(target_level, is_member):
                    current_level = target_level
            except (ValueError, TypeError):
                pass

        negative_marking = request.POST.get('negative_marking') == 'on'
        attempt = Attempt.objects.create(
            user=request.user,
            subtopic=subtopic,
            negative_marking_enabled=negative_marking,
            level_at_attempt=current_level,
        )
        increment_attempt_count(request.user)
        return redirect('quiz_session', attempt_id=attempt.id)

    # GET
    try:
        user_level = UserTopicLevel.objects.get(user=request.user, subtopic=subtopic)
        current_level = user_level.current_level
    except UserTopicLevel.DoesNotExist:
        current_level = 1

    if not is_level_accessible(current_level, is_member):
        current_level = max_accessible_level(is_member)

    # Automatically map difficulty to default level if not already at a higher level
    # Easy (L1), Medium (L3), Hard (L5)
    if selected_difficulty == 'medium':
        if current_level < 3 and is_level_accessible(3, is_member):
            current_level = 3
    elif selected_difficulty == 'hard':
        if current_level < 5 and is_level_accessible(5, is_member):
            current_level = 5
    # For 'easy' or 'all', we keep the current_level (usually L1 for new users)

    question_count = Question.objects.filter(subtopic=subtopic, level=current_level).count()
    # Apply limit for display
    limit = get_max_questions(current_level)
    if limit and limit > 0:
        question_count = min(question_count, limit)
    allowed, attempt_count = check_attempt_allowed(request.user)

    level_config = get_level_config_map()
    levels_info = [
        {
            'level': lvl,
            'accessible': is_level_accessible(lvl, is_member),
            'requires_membership': level_config.get(lvl, True),
            'is_current': lvl == current_level,
        }
        for lvl in range(1, 6)
    ]

    return render(request, 'quiz/start_quiz.html', {
        'subtopic': subtopic,
        'current_level': current_level,
        'question_count': question_count,
        'is_member': is_member,
        'allowed': allowed,
        'attempt_count': attempt_count,
        'max_attempts': 5,
        'levels_info': levels_info,
        'selected_difficulty': selected_difficulty,
    })


@login_required
def quiz_session(request, attempt_id):
    attempt = get_object_or_404(Attempt, id=attempt_id, user=request.user)

    if attempt.is_complete:
        return redirect('quiz_results', attempt_id=attempt.id)

    questions = list(
        Question.objects.filter(
            subtopic=attempt.subtopic,
            level=attempt.level_at_attempt
        ).prefetch_related('options').order_by('order', 'id')
    )

    # Apply per-level question limit set in admin Level Access panel
    limit = get_max_questions(attempt.level_at_attempt)
    if limit and limit > 0:
        questions = questions[:limit]

    # answered = {question_id: selected_option_id}  (integers, for template comparison)
    answered = {
        a.question_id: a.selected_option_id
        for a in attempt.answers.all()
        if a.selected_option_id is not None
    }

    page_num = request.GET.get('page', 1)
    paginator = Paginator(questions, QUESTIONS_PER_PAGE)
    page_obj = paginator.get_page(page_num)

    # Shuffle options for questions on the current page
    for q in page_obj:
        opts = list(q.options.all())
        # Use attempt.id + q.id as seed for consistent shuffle within the same attempt
        rng = random.Random(attempt.id + q.id)
        rng.shuffle(opts)
        q.shuffled_options = opts

    timer_seconds = len(questions) * 90
    level_preference = request.session.get('level_preference', 'flow')
    show_level_prompt = len(answered) == 20 and level_preference == 'flow'

    return render(request, 'quiz/quiz_session.html', {
        'attempt': attempt,
        'page_obj': page_obj,
        'paginator': paginator,
        'questions': questions,
        'answered': answered,
        'timer_seconds': timer_seconds,
        'is_member': request.is_member,
        'show_level_prompt': show_level_prompt,
        'level_preference': level_preference,
        'total_questions': len(questions),
    })


@login_required
@require_POST
def save_answer(request, attempt_id):
    attempt = get_object_or_404(Attempt, id=attempt_id, user=request.user)
    if attempt.is_complete:
        return JsonResponse({'error': 'Attempt already completed'}, status=400)

    question_id = request.POST.get('question_id')
    option_id = request.POST.get('option_id')

    if not question_id:
        return JsonResponse({'error': 'Missing question_id'}, status=400)

    question = get_object_or_404(Question, id=question_id)
    selected_option = None
    is_correct = False
    is_skipped = True

    if option_id:
        try:
            selected_option = question.options.get(id=int(option_id))
            is_correct = bool(selected_option.is_correct)
            is_skipped = False
        except (Question.options.model.DoesNotExist, ValueError):
            pass

    Answer.objects.update_or_create(
        attempt=attempt,
        question=question,
        defaults={
            'selected_option': selected_option,
            'is_correct': is_correct,
            'is_skipped': is_skipped,
        }
    )

    return JsonResponse({
        'status': 'success',
        'is_correct': is_correct,
        'answered_count': attempt.answers.filter(is_skipped=False).count()
    })


@login_required
@require_POST
def submit_quiz(request, attempt_id):
    attempt = get_object_or_404(Attempt, id=attempt_id, user=request.user)

    if attempt.is_complete:
        return redirect('quiz_results', attempt_id=attempt.id)

    # First, save any answers present in the current POST (the last page)
    # This ensures that even if AJAX failed for the last page, the answers are captured.
    questions_in_attempt = list(
        Question.objects.filter(
            subtopic=attempt.subtopic,
            level=attempt.level_at_attempt
        ).prefetch_related('options').order_by('order', 'id')
    )
    limit = get_max_questions(attempt.level_at_attempt)
    if limit and limit > 0:
        questions_in_attempt = questions_in_attempt[:limit]

    for q in questions_in_attempt:
        option_id = request.POST.get(f'question_{q.id}')
        if option_id:
            try:
                selected_option = q.options.get(id=int(option_id))
                Answer.objects.update_or_create(
                    attempt=attempt,
                    question=q,
                    defaults={
                        'selected_option': selected_option,
                        'is_correct': bool(selected_option.is_correct),
                        'is_skipped': False,
                    }
                )
            except (Question.options.model.DoesNotExist, ValueError):
                pass
        # Note: We DON'T set is_skipped=True here if option_id is missing,
        # because the question might have been answered in a previous batch (AJAX).
        # We only mark it as skipped if it doesn't exist in Answer table at all yet.

    # Now calculate the final score based on ALL answers for this attempt
    all_answers = attempt.answers.all()
    
    # Ensure all questions that SHOULD have been in this attempt have an Answer record
    # (even if it's a 'skipped' record)
    existing_q_ids = set(all_answers.values_list('question_id', flat=True))
    missing_answers = []
    for q in questions_in_attempt:
        if q.id not in existing_q_ids:
            missing_answers.append(Answer(
                attempt=attempt,
                question=q,
                is_skipped=True,
                is_correct=False
            ))
    if missing_answers:
        Answer.objects.bulk_create(missing_answers)
        all_answers = attempt.answers.all() # Refresh

    score = 0.0
    for ans in all_answers:
        if ans.is_correct:
            score += 1
        elif attempt.negative_marking_enabled and not ans.is_skipped:
            score -= 0.25

    now = timezone.now()
    attempt.score = max(score, 0)
    attempt.ended_at = now
    attempt.time_taken_seconds = int((now - attempt.started_at).total_seconds())
    attempt.is_complete = True
    attempt.save()

    # Update stats for each question answered in this attempt
    # We call it directly instead of .delay() to ensure immediate update across accounts
    for ans in all_answers:
        update_question_stats(ans.question_id)
    
    update_user_level_task.delay(request.user.id, attempt.subtopic_id)

    return redirect('quiz_results', attempt_id=attempt.id)


@login_required
def quiz_results(request, attempt_id):
    attempt = get_object_or_404(Attempt, id=attempt_id, user=request.user)

    if not attempt.is_complete:
        return redirect('quiz_session', attempt_id=attempt.id)

    answers = attempt.answers.select_related(
        'question', 'question__subtopic', 'selected_option'
    ).prefetch_related('question__options').order_by('question__order', 'question__id')

    for ans in answers:
        q = ans.question
        opts = list(q.options.all())
        # Use same seed as in quiz_session for consistent shuffle
        rng = random.Random(attempt.id + q.id)
        rng.shuffle(opts)
        q.shuffled_options = opts

    try:
        user_level = UserTopicLevel.objects.get(user=request.user, subtopic=attempt.subtopic)
        current_level = user_level.current_level
        total_attempted = user_level.total_attempted
        accuracy = user_level.accuracy
        next_threshold = _next_level_threshold(current_level)
        progress_pct = min(int((accuracy / next_threshold) * 100), 100) if next_threshold else 100
    except UserTopicLevel.DoesNotExist:
        current_level = 1
        total_attempted = 0
        progress_pct = 0
        accuracy = 0

    minutes = attempt.time_taken_seconds // 60
    seconds = attempt.time_taken_seconds % 60

    return render(request, 'quiz/quiz_results.html', {
        'attempt': attempt,
        'answers': answers,
        'current_level': current_level,
        'total_attempted': total_attempted,
        'progress_pct': progress_pct,
        'accuracy': round(accuracy, 1),
        'time_display': f"{minutes:02d}:{seconds:02d}",
        'is_member': request.is_member,
    })


@login_required
@require_POST
def set_level_preference(request, attempt_id):
    preference = request.POST.get('preference', 'flow')
    if preference in ('flow', 'improve'):
        request.session['level_preference'] = preference
    return redirect('quiz_session', attempt_id=attempt_id)


def _next_level_threshold(current_level):
    thresholds = {1: 20, 2: 40, 3: 60, 4: 80, 5: None}
    return thresholds.get(current_level)


@login_required
def start_quiz_scoped(request):
    """
    Start a quiz scoped to a topic or course, with optional difficulty filter.
    GET  params: scope=topic|course, id=<pk>, difficulty=easy|medium|hard|all
    POST params: same + negative_marking
    """
    scope      = request.GET.get('scope') or request.POST.get('scope', 'topic')
    obj_id     = request.GET.get('id')    or request.POST.get('id')
    difficulty = (request.GET.get('difficulty') or request.POST.get('difficulty', 'all')).lower()

    # Backend enforcement: Free users can only access Easy difficulty
    if not request.is_member and difficulty in ('medium', 'hard', 'all'):
        difficulty = 'easy'

    if difficulty not in ('easy', 'medium', 'hard', 'all'):
        difficulty = 'all'

    # ── Resolve scope → list of subtopics ──
    if scope == 'course':
        course = get_object_or_404(Course, pk=obj_id)
        subtopics = list(SubTopic.objects.filter(topic__course=course).select_related('topic__course'))
        scope_name = course.name
    else:
        topic = get_object_or_404(Topic, pk=obj_id)
        subtopics = list(SubTopic.objects.filter(topic=topic).select_related('topic__course'))
        scope_name = topic.name

    if not subtopics:
        return redirect('home')

    # ── Build question queryset ──
    qs = Question.objects.filter(subtopic__in=subtopics).select_related('subtopic')
    if difficulty != 'all':
        qs = qs.filter(difficulty=difficulty)

    questions = list(qs.prefetch_related('options').order_by('?')[:50])  # max 50, randomised

    if not questions:
        # Nothing found — go back home with a message
        from django.contrib import messages
        messages.warning(request, f'No {difficulty} questions found for {scope_name}. Try a different difficulty.')
        return redirect('home')

    if request.method == 'POST':
        allowed, count = check_attempt_allowed(request.user)
        if not allowed:
            # Use first subtopic as representative for limit page
            return render(request, 'quiz/limit_reached.html', {
                'count': count, 'subtopic': subtopics[0],
            })

        negative_marking = request.POST.get('negative_marking') == 'on'

        # Store scoped quiz in session
        request.session['scoped_quiz'] = {
            'question_ids': [q.id for q in questions],
            'scope': scope,
            'scope_name': scope_name,
            'difficulty': difficulty,
            'negative_marking': negative_marking,
            'subtopic_id': subtopics[0].id,  # representative subtopic for Attempt FK
        }
        increment_attempt_count(request.user)
        return redirect('quiz_session_scoped')

    # GET — show confirmation page
    question_count = len(questions)
    allowed, attempt_count = check_attempt_allowed(request.user)

    return render(request, 'quiz/start_quiz_scoped.html', {
        'scope': scope,
        'scope_name': scope_name,
        'obj_id': obj_id,
        'difficulty': difficulty,
        'question_count': question_count,
        'allowed': allowed,
        'attempt_count': attempt_count,
        'max_attempts': 5,
        'is_member': request.is_member,
    })


@login_required
def quiz_session_scoped(request):
    """Run a scoped quiz stored in the session."""
    scoped = request.session.get('scoped_quiz')
    if not scoped:
        return redirect('home')

    question_ids  = scoped['question_ids']
    scope_name    = scoped['scope_name']
    difficulty    = scoped['difficulty']
    neg_marking   = scoped.get('negative_marking', False)
    subtopic_id   = scoped['subtopic_id']

    subtopic  = get_object_or_404(SubTopic, pk=subtopic_id)
    questions = list(
        Question.objects.filter(id__in=question_ids)
        .prefetch_related('options')
        .order_by('id')
    )
    # Restore original random order
    id_order = {qid: i for i, qid in enumerate(question_ids)}
    questions.sort(key=lambda q: id_order.get(q.id, 0))

    if request.method == 'POST':
        # ── Submit ──
        score = 0.0
        attempt = Attempt.objects.create(
            user=request.user,
            subtopic=subtopic,
            negative_marking_enabled=neg_marking,
            level_at_attempt=1,
        )
        answer_objects = []
        for question in questions:
            selected_option_id = request.POST.get(f'question_{question.id}')
            is_skipped = not selected_option_id
            is_correct = False
            selected_option = None
            if not is_skipped:
                try:
                    selected_option = question.options.get(id=int(selected_option_id))
                    is_correct = bool(selected_option.is_correct)
                    if is_correct:
                        score += 1
                    elif neg_marking:
                        score -= 0.25
                except Exception:
                    is_skipped = True
            answer_objects.append(Answer(
                attempt=attempt,
                question=question,
                selected_option=selected_option,
                is_correct=is_correct,
                is_skipped=is_skipped,
            ))

        Answer.objects.bulk_create(answer_objects)
        now = timezone.now()
        attempt.score = max(score, 0)
        attempt.ended_at = now
        attempt.time_taken_seconds = int((now - attempt.started_at).total_seconds())
        attempt.is_complete = True
        attempt.save()

        for q in questions:
            update_question_stats.delay(q.id)

        # Clear session
        del request.session['scoped_quiz']
        return redirect('quiz_results', attempt_id=attempt.id)

    # GET — show quiz
    page_num  = request.GET.get('page', 1)
    paginator = Paginator(questions, QUESTIONS_PER_PAGE)
    page_obj  = paginator.get_page(page_num)
    timer_seconds = len(questions) * 90

    return render(request, 'quiz/quiz_session_scoped.html', {
        'questions': questions,
        'page_obj': page_obj,
        'paginator': paginator,
        'scope_name': scope_name,
        'difficulty': difficulty,
        'timer_seconds': timer_seconds,
        'is_member': request.is_member,
        'total_questions': len(questions),
        'answered': {},
    })

from celery import shared_task
from django.utils import timezone


@shared_task
def update_question_stats(question_id):
    """Recalculate total_attempted and total_correct for a question after each attempt."""
    from questions.models import Question
    from quiz.models import Answer

    try:
        question = Question.objects.get(pk=question_id)
        answers = Answer.objects.filter(question=question, attempt__is_complete=True)
        question.total_attempted = answers.count()
        question.total_correct = answers.filter(is_correct=True).count()

        update_fields = ['total_attempted', 'total_correct']

        # Auto-adjust question level (admin-uploaded questions only)
        # Rule uses the latest 100 completed answers for this question:
        #   >=80% correct -> Level 1
        #   >=60% correct -> Level 2
        #   >=40% correct -> Level 3
        #   >=20% correct -> Level 4
        #   <20% correct  -> Level 5
        try:
            if question.created_by and getattr(question.created_by, 'is_staff', False):
                recent = list(
                    Answer.objects.filter(question=question, attempt__is_complete=True)
                    .order_by('-attempt__started_at')
                    .values_list('is_correct', flat=True)[:100]
                )
                if len(recent) == 100:
                    correct = sum(1 for x in recent if x)
                    pct = (correct / 100) * 100
                    if pct >= 80:
                        new_level = 1
                    elif pct >= 60:
                        new_level = 2
                    elif pct >= 40:
                        new_level = 3
                    elif pct >= 20:
                        new_level = 4
                    else:
                        new_level = 5
                    if question.level != new_level:
                        question.level = new_level
                        update_fields.append('level')
        except Exception:
            # Never fail stats update because of auto-level logic
            pass

        question.save(update_fields=update_fields)
    except Question.DoesNotExist:
        pass


@shared_task
def update_user_level_task(user_id, subtopic_id):
    """Recalculate UserTopicLevel after each completed attempt."""
    from accounts.models import UserTopicLevel
    from quiz.models import Answer

    level_obj, _ = UserTopicLevel.objects.get_or_create(
        user_id=user_id, subtopic_id=subtopic_id
    )
    answers = Answer.objects.filter(
        attempt__user_id=user_id,
        attempt__subtopic_id=subtopic_id,
        attempt__is_complete=True
    )
    total = answers.count()
    correct = answers.filter(is_correct=True).count()

    level_obj.total_attempted = total
    level_obj.total_correct = correct

    if total >= 100:
        accuracy = (correct / total) * 100
        if accuracy <= 20:
            level_obj.current_level = 1
        elif accuracy <= 40:
            level_obj.current_level = 2
        elif accuracy <= 60:
            level_obj.current_level = 3
        elif accuracy <= 80:
            level_obj.current_level = 4
        else:
            level_obj.current_level = 5

    level_obj.save()


@shared_task
def expire_memberships():
    """Run nightly. Deactivate expired memberships."""
    from accounts.models import UserProfile
    today = timezone.now().date()
    expired = UserProfile.objects.filter(is_member=True, membership_expires__lt=today)
    count = expired.update(is_member=False)
    return f"Expired {count} memberships"

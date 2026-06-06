from celery import shared_task
from django.utils import timezone


@shared_task
def update_question_stats(question_id):
    """Recalculate total_attempted and total_correct for a question after each attempt."""
    from questions.models import Question, QuestionLevelTransition
    from quiz.models import Answer
    import logging
    logger = logging.getLogger(__name__)

    try:
        question = Question.objects.select_related('subtopic__topic__course__syllabus').get(pk=question_id)
        # Count only non-skipped answers in completed attempts
        answers = Answer.objects.filter(question=question, attempt__is_complete=True, is_skipped=False)
        
        question.total_attempted = answers.count()
        question.total_correct = answers.filter(is_correct=True).count()

        update_fields = ['total_attempted', 'total_correct']
        
        logger.info(f"Updating Q{question_id}: Attempted={question.total_attempted}, Correct={question.total_correct}")
        old_level = question.level
        old_difficulty = question.difficulty

        # Auto-adjust difficulty (Easy, Medium, Hard) and Level (1-5)
        # Based on the latest 100 completed answers for this question:
        # Difficulty logic:
        #   >80% WRONG (<=20% correct) -> Hard
        #   >60% WRONG (<=40% correct) -> Medium
        #   Others (<=60% wrong)       -> Easy
        # Level logic (1-5):
        #   >=80% correct -> Level 1
        #   >=60% correct -> Level 2
        #   >=40% correct -> Level 3
        #   >=20% correct -> Level 4
        #   <20% correct  -> Level 5
        try:
            recent = list(
                Answer.objects.filter(question=question, attempt__is_complete=True)
                .order_by('-attempt__started_at')
                .values_list('is_correct', flat=True)[:100]
            )
            if len(recent) == 100:
                correct = sum(1 for x in recent if x)
                wrong = 100 - correct
                pct_correct = (correct / 100) * 100

                # 1. Determine new Difficulty
                if wrong > 80:
                    new_difficulty = 'hard'
                elif wrong > 60:
                    new_difficulty = 'medium'
                else:
                    new_difficulty = 'easy'

                # 2. Determine new Level
                if pct_correct >= 80:
                    new_level = 1
                elif pct_correct >= 60:
                    new_level = 2
                elif pct_correct >= 40:
                    new_level = 3
                elif pct_correct >= 20:
                    new_level = 4
                else:
                    new_level = 5

                # Check if anything changed
                if question.level != new_level or question.difficulty != new_difficulty:
                    # Log the transition before updating the question object
                    subtopic = question.subtopic
                    topic = subtopic.topic
                    course = topic.course
                    syllabus = course.syllabus

                    QuestionLevelTransition.objects.create(
                        question=question,
                        old_level=old_level,
                        new_level=new_level,
                        old_difficulty=old_difficulty,
                        new_difficulty=new_difficulty,
                        syllabus_name=syllabus.name if syllabus else "N/A",
                        course_name=course.name,
                        topic_name=topic.name,
                        subtopic_name=subtopic.name,
                        correct_pct_at_transition=pct_correct
                    )

                    question.level = new_level
                    question.difficulty = new_difficulty
                    if 'level' not in update_fields: update_fields.append('level')
                    if 'difficulty' not in update_fields: update_fields.append('difficulty')
        except Exception:
            # Never fail stats update because of auto-adjust logic
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

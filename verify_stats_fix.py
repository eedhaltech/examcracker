import os
import django
import random
from django.utils import timezone
# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mcqplatform.settings')
django.setup()

from django.contrib.auth.models import User
from questions.models import Question, SubTopic, Option
from quiz.models import Attempt, Answer
from quiz.tasks import update_question_stats

def fix_and_verify():
    # 1. Find all questions in 'Atoms' subtopics
    subtopics = SubTopic.objects.filter(name='Atoms')
    if not subtopics.exists():
        print("No subtopics named 'Atoms' found.")
        return

    # Create a test user if not exists
    test_user, _ = User.objects.get_or_create(username='stats_verifier', defaults={'email': 'verifier@example.com'})

    for st in subtopics:
        print(f"\nProcessing SubTopic: {st.name} (ID: {st.id}, Topic: {st.topic.name})")
        questions = Question.objects.filter(subtopic=st)
        
        for q in questions:
            print(f"  Question ID: {q.id} | Body: {q.body[:50]}...")
            print(f"  Before: Attempted={q.total_attempted}, Correct={q.total_correct}")

            # 2. Simulate 5 successful attempts for this specific question
            correct_option = q.options.filter(is_correct=True).first()
            if not correct_option:
                print(f"    Error: No correct option for Q{q.id}")
                continue

            for _ in range(5):
                # Create a completed attempt
                attempt = Attempt.objects.create(
                    user=test_user,
                    subtopic=st,
                    level_at_attempt=q.level,
                    started_at=timezone.now(),
                    ended_at=timezone.now(),
                    is_complete=True
                )
                # Record correct answer
                Answer.objects.create(
                    attempt=attempt,
                    question=q,
                    selected_option=correct_option,
                    is_correct=True,
                    is_skipped=False
                )
                # 3. Synchronously update stats
                update_question_stats(q.id)

            q.refresh_from_db()
            print(f"  After:  Attempted={q.total_attempted}, Correct={q.total_correct} | Pct: {q.percent_correct}")

if __name__ == "__main__":
    fix_and_verify()

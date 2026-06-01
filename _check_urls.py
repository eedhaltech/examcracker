import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'mcqplatform.settings_dev'
django.setup()
from django.urls import reverse

tests = [
    ('panel_syllabuses', {}, '/manage/syllabuses/'),
    ('panel_courses', {}, '/manage/courses/'),
    ('syllabus_courses', {'syllabus_id': 1}, '/manage/syllabus/1/courses/'),
    ('syllabus_course_add', {'syllabus_id': 1}, '/manage/syllabus/1/courses/add/'),
    ('course_topics', {'course_id': 1}, '/manage/course/1/topics/'),
    ('course_topic_add', {'course_id': 1}, '/manage/course/1/topics/add/'),
    ('topic_subtopics', {'topic_id': 1}, '/manage/topic/1/subtopics/'),
    ('topic_subtopic_add', {'topic_id': 1}, '/manage/topic/1/subtopics/add/'),
]

all_ok = True
for name, kwargs, expected in tests:
    url = reverse(name, kwargs=kwargs)
    ok = url == expected
    status = 'OK  ' if ok else 'FAIL'
    print(status + ' ' + name + ': ' + url)
    if not ok:
        all_ok = False

print()
print('All OK!' if all_ok else 'Some URLs failed!')

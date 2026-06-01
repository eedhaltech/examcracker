from django.urls import path
from . import views

urlpatterns = [
    path('',                              views.dashboard,        name='panel_dashboard'),

    # ── Users ──
    path('users/',                        views.users_list,       name='panel_users'),
    path('users/<int:user_id>/',          views.user_detail,      name='panel_user_detail'),

    # ── Questions ──
    path('questions/',                    views.questions_list,   name='panel_questions'),
    path('questions/add/',                views.question_add,     name='panel_question_add'),
    path('questions/<int:question_id>/edit/',   views.question_edit,   name='panel_question_edit'),
    path('questions/<int:question_id>/delete/', views.question_delete, name='panel_question_delete'),
    path('questions/import/',             views.csv_import,       name='panel_csv_import'),

    # ── Hierarchy: Syllabuses → Courses → Topics → Sub-topics ──
    # Level 0: Syllabuses list (main "Courses" entry point)
    path('courses/',                      views.syllabuses_home,  name='panel_courses'),
    path('syllabuses/add/',               views.syllabus_add,     name='panel_syllabus_add'),
    path('syllabuses/<int:syllabus_id>/edit/',   views.syllabus_edit,   name='panel_syllabus_edit'),
    path('syllabuses/<int:syllabus_id>/delete/', views.syllabus_delete, name='panel_syllabus_delete'),

    # Level 1: Courses under a syllabus
    path('syllabuses/<int:syllabus_id>/courses/',      views.syllabus_courses,    name='syllabus_courses'),
    path('syllabuses/<int:syllabus_id>/courses/add/',  views.syllabus_course_add, name='syllabus_course_add'),
    path('syllabuses/<int:syllabus_id>/courses/<int:course_id>/edit/',   views.course_edit,   name='panel_course_edit'),
    path('syllabuses/<int:syllabus_id>/courses/<int:course_id>/delete/', views.course_delete, name='panel_course_delete'),

    # Level 2: Topics under a course
    path('syllabuses/<int:syllabus_id>/courses/<int:course_id>/topics/',      views.course_topics,    name='course_topics'),
    path('syllabuses/<int:syllabus_id>/courses/<int:course_id>/topics/add/',  views.course_topic_add, name='course_topic_add'),
    path('topics/<int:topic_id>/delete/', views.topic_delete, name='panel_topic_delete'),

    # Level 3: Sub-topics under a topic
    path('syllabuses/<int:syllabus_id>/courses/<int:course_id>/topics/<int:topic_id>/subtopics/',      views.topic_subtopics,    name='topic_subtopics'),
    path('syllabuses/<int:syllabus_id>/courses/<int:course_id>/topics/<int:topic_id>/subtopics/add/',  views.topic_subtopic_add, name='topic_subtopic_add'),
    path('subtopics/<int:subtopic_id>/delete/', views.subtopic_delete, name='panel_subtopic_delete'),

    # ── Legacy redirects (keep old URLs working) ──
    path('courses/add/',                  views.legacy_course_add,    name='panel_course_add'),
    path('courses/<int:course_id>/',      views.course_detail,        name='panel_course_detail'),
    path('courses/<int:course_id>/topic/add/', views.legacy_topic_add, name='panel_topic_add'),
    path('topics/<int:topic_id>/',        views.topic_detail,         name='panel_topic_detail'),
    path('topics/<int:topic_id>/subtopic/add/', views.legacy_subtopic_add, name='panel_subtopic_add'),

    # ── Ads ──
    path('ads/',                          views.ads_list,         name='panel_ads'),
    path('ads/add/',                      views.ad_add,           name='panel_ad_add'),
    path('ads/<int:ad_id>/edit/',         views.ad_edit,          name='panel_ad_edit'),
    path('ads/<int:ad_id>/delete/',       views.ad_delete,        name='panel_ad_delete'),
    path('ads/<int:ad_id>/toggle/',       views.ad_toggle,        name='panel_ad_toggle'),

    # ── Memberships ──
    path('memberships/',                  views.memberships_list, name='panel_memberships'),
    path('memberships/<int:subscription_id>/payment-action/', views.membership_payment_action, name='panel_membership_payment_action'),
    path('memberships/grant/',            views.membership_grant, name='panel_membership_grant'),

    # Razorpay settings (staff)
    path('razorpay-settings/',            views.razorpay_settings, name='panel_razorpay_settings'),

    # ── Level config ──
    path('levels/',                       views.level_config,     name='panel_level_config'),

    # ── Products ──
    path('products/',                     views.products_list,    name='panel_products'),
    path('products/add/',                 views.product_add,      name='panel_product_add'),
    path('products/<int:product_id>/edit/',   views.product_edit,   name='panel_product_edit'),
    path('products/<int:product_id>/delete/', views.product_delete, name='panel_product_delete'),

    # ── Comments ──
    path('comments/',                     views.comments_list,    name='panel_comments'),
    path('comments/<int:comment_id>/action/', views.comment_action, name='panel_comment_action'),

    # ── Syllabus JSON API ──
    path('api/syllabus-courses/',         views.syllabus_courses_json, name='panel_syllabus_courses_json'),
]

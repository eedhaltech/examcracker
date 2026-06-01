from django.urls import path
from . import views

urlpatterns = [
    path("post-login/", views.post_login_redirect, name="post_login_redirect"),
]


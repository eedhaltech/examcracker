from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


@login_required
def post_login_redirect(request):
    """
    Unified redirect after login.

    - If user is staff (admin), take them to Django admin.
    - Otherwise go to the user dashboard.

    Note: if a "next" parameter is present, django-allauth will usually honor it
    and this view will not be used. This is the default fallback.
    """
    if request.user.is_staff:
        messages.info(request, "Welcome back! Redirected to Admin Panel.")
        return redirect("/admin/")
    return redirect("/")

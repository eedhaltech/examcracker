from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def staff_required(view_func):
    """Allow access only to staff (is_staff=True) or superusers."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f'/accounts/login/?next={request.path}')
        if not (request.user.is_staff or request.user.is_superuser):
            messages.error(request, 'You do not have permission to access the staff panel.')
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return wrapper

class MembershipMiddleware:
    """
    Attaches request.is_member (bool) to every request.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                profile = request.user.profile
                request.is_member = profile.membership_active
            except Exception:
                request.is_member = False
        else:
            request.is_member = False

        # Monetization flags / feature gating
        request.paywalls_active = False
        request.can_view_analytics = True
        request.can_access_levels = True
        request.member_features = True  # timer/no-ads style features
        request.free_attempts_per_day = 0

        try:
            from payments.monetization import get_monetization_settings, monetization_active_for_user

            ms = get_monetization_settings()
            # Per-user paywall activation (can be delayed after signup)
            request.paywalls_active = monetization_active_for_user(request.user)
            request.free_attempts_per_day = int(ms.free_attempts_per_day or 0)

            # When paywalls are OFF, everything should be accessible (no upsell screens).
            # When paywalls are ON:
            # - Analytics gating depends on ms.gate_analytics
            # - Level gating depends on ms.gate_levels (LevelConfig decides which levels are paid)
            request.can_view_analytics = (not request.paywalls_active) or (not ms.gate_analytics) or request.is_member
            request.can_access_levels = (not request.paywalls_active) or (not ms.gate_levels) or request.is_member

            # "Member features" (timer etc): available for members OR when monetization is off
            request.member_features = (not request.paywalls_active) or request.is_member
        except Exception:
            # Safe defaults (no paywalls)
            request.paywalls_active = False
            request.can_view_analytics = True
            request.can_access_levels = True
            request.member_features = True

        return self.get_response(request)


class AdminUnifiedLoginMiddleware:
    """
    Enforce "admin login is the same as customer login":
    - Visiting /admin/ while logged out redirects to the normal allauth login page.
    - Only staff users can access /admin/.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/admin/"):
            # Not logged in: send to the same login used by customers
            if not request.user.is_authenticated:
                from django.shortcuts import redirect
                from django.urls import reverse
                from urllib.parse import urlencode

                login_url = reverse("account_login")
                qs = urlencode({"next": request.get_full_path()})
                return redirect(f"{login_url}?{qs}")

            # Logged in but not staff: block access
            if not request.user.is_staff:
                from django.shortcuts import redirect
                from django.contrib import messages

                messages.error(request, "Access denied: you don’t have admin permissions.")
                return redirect("home")

        return self.get_response(request)

def social_oauth_flags(request):
    """
    Prevent template crashes when SocialApp (Google OAuth) is not configured yet.
    Exposes booleans to templates so we can hide/disable social login buttons.
    """
    try:
        from allauth.socialaccount.models import SocialApp
        has_google_oauth = SocialApp.objects.filter(provider="google").exists()
    except Exception:
        has_google_oauth = False

    return {
        "has_google_oauth": has_google_oauth,
    }


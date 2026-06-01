from .models import SEOSettings


def seo_settings(request):
    """
    Makes site-wide SEO defaults available to all templates as `seo`.
    Per-page templates can still override title/description/keywords via template blocks.
    """
    try:
        seo = SEOSettings.get()
    except Exception:
        # Keep templates resilient during migrations / initial setup
        seo = None
    return {"seo": seo}


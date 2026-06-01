from django import template
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from ads.models import PromoAd

register = template.Library()


@register.simple_tag(takes_context=True)
def render_ad(context, position):
    request = context.get('request')
    is_member = getattr(request, 'is_member', False) if request else False

    # Build query: active ads for this position
    qs = PromoAd.objects.filter(position=position, is_active=True)

    if is_member:
        # Members see ads marked show_to_members=True only
        ad = qs.filter(show_to_members=True).order_by('?').first()
    else:
        # Non-members see ads marked show_to_members=False
        ad = qs.filter(show_to_members=False).order_by('?').first()
        # Fallback: if no non-member ad, show any active ad
        if not ad:
            ad = qs.order_by('?').first()

    rendered = render_to_string(
        'ads/promo_ad.html',
        {'ad': ad, 'is_member': is_member, 'position': position},
        request=request
    )
    return mark_safe(rendered)

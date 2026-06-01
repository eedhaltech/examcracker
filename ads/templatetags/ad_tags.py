from django import template
from ads.models import PromoAd

register = template.Library()


@register.inclusion_tag('ads/promo_ad.html', takes_context=True)
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

    return {'ad': ad, 'is_member': is_member, 'position': position}

import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'mcqplatform.settings_dev'
import django; django.setup()

from ads.models import PromoAd

# Clear existing
PromoAd.objects.all().delete()

ads = [
    # Sidebar display ad (non-members)
    PromoAd(
        title='Upgrade to Member',
        position='display_sidebar',
        html_content='''
<div style="background:linear-gradient(135deg,#2563EB,#1d4ed8);border-radius:12px;padding:1.25rem;color:#fff;text-align:center;">
  <div style="font-size:1.75rem;margin-bottom:.5rem;">⭐</div>
  <div style="font-weight:800;font-size:1rem;margin-bottom:.35rem;">Go Premium</div>
  <div style="font-size:.8rem;opacity:.85;margin-bottom:1rem;">Unlimited quizzes · All levels · No ads</div>
  <a href="/subscribe/" style="background:#fff;color:#2563EB;padding:.45rem 1.1rem;border-radius:20px;font-weight:700;font-size:.82rem;text-decoration:none;display:inline-block;">View Plans ₹10 →</a>
</div>''',
        link_url='/subscribe/',
        is_active=True,
        show_to_members=False,
    ),
    # Sidebar display ad 2 (non-members)
    PromoAd(
        title='Practice Makes Perfect',
        position='display_sidebar',
        html_content='''
<div style="background:#fffbeb;border:2px solid #f59e0b;border-radius:12px;padding:1.1rem;text-align:center;">
  <div style="font-size:1.5rem;margin-bottom:.4rem;">📚</div>
  <div style="font-weight:700;font-size:.9rem;color:#92400e;margin-bottom:.3rem;">5 Free Attempts/Day</div>
  <div style="font-size:.78rem;color:#78350f;margin-bottom:.85rem;">Upgrade for unlimited practice</div>
  <a href="/subscribe/" style="background:#f59e0b;color:#fff;padding:.4rem 1rem;border-radius:20px;font-weight:700;font-size:.78rem;text-decoration:none;display:inline-block;">Upgrade Now</a>
</div>''',
        link_url='/subscribe/',
        is_active=True,
        show_to_members=False,
    ),
    # Closing ad between questions (non-members)
    PromoAd(
        title='Unlock All Levels',
        position='closing',
        html_content='''
<div style="background:#f0fdf4;border:1.5px solid #86efac;border-radius:10px;padding:1rem 1.25rem;display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap;">
  <div>
    <div style="font-weight:700;font-size:.9rem;color:#166534;">🔓 Unlock Levels 3, 4 &amp; 5</div>
    <div style="font-size:.78rem;color:#15803d;margin-top:.2rem;">Members get all difficulty levels + timer</div>
  </div>
  <a href="/subscribe/" style="background:#16a34a;color:#fff;padding:.4rem 1rem;border-radius:8px;font-weight:700;font-size:.8rem;text-decoration:none;white-space:nowrap;">From ₹10 →</a>
</div>''',
        link_url='/subscribe/',
        is_active=True,
        show_to_members=False,
    ),
    # Interstitial / overlapping ad (non-members)
    PromoAd(
        title='Member Upgrade Interstitial',
        position='overlapping',
        html_content='''
<div style="background:#fff;border-radius:16px;padding:2rem;max-width:380px;text-align:center;box-shadow:0 8px 32px rgba(0,0,0,.2);">
  <div style="font-size:2.5rem;margin-bottom:.75rem;">🚀</div>
  <h2 style="font-size:1.3rem;font-weight:800;color:#0f172a;margin-bottom:.5rem;">Enjoying the quiz?</h2>
  <p style="font-size:.875rem;color:#64748b;margin-bottom:1.25rem;">Upgrade to get unlimited attempts, all 5 levels, countdown timer, and full analytics.</p>
  <a href="/subscribe/" style="background:#2563EB;color:#fff;padding:.65rem 1.5rem;border-radius:8px;font-weight:700;font-size:.9rem;text-decoration:none;display:inline-block;margin-bottom:.75rem;">View Plans — from ₹10</a>
  <div style="font-size:.75rem;color:#94a3b8;">Cheaper than a cup of tea!</div>
</div>''',
        link_url='/subscribe/',
        is_active=True,
        show_to_members=False,
    ),
]

for ad in ads:
    ad.save()
    print(f'Created: {ad.title} [{ad.position}]')

print(f'\nTotal ads: {PromoAd.objects.count()}')

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from panel.views import razorpay_settings

urlpatterns = [
    path('admin/settings.php', razorpay_settings, name='legacy_admin_settings_php'),
    path('admin/', admin.site.urls),
    path('manage/', include('panel.urls')),
    path('', include('accounts.urls')),
    path('accounts/', include('allauth.urls')),
    path('', include('content.urls')),
    path('quiz/', include('quiz.urls')),
    path('dashboard/', include('analytics.urls')),
    path('subscribe/', include('payments.urls')),
    path('products/', include('products.urls')),
    path('contact/', include('contact.urls')),
    path('api/', include('questions.api_urls')),
    path('', include('questions.urls')),
]

if settings.DEBUG:
    # Development-only preview route to render homepage without login.
    # This is safe because it's only active when DEBUG=True.
    from .dev_views import preview_home
    urlpatterns += [
        path('dev/preview-home/', preview_home, name='dev_preview_home'),
    ]

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

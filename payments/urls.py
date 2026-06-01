from django.urls import path
from . import views

urlpatterns = [
    path('', views.subscribe, name='subscribe'),
    path('checkout/<str:plan_key>/', views.checkout, name='payment_checkout'),
    path('success/', views.payment_success, name='payment_success'),
    path('failure/', views.payment_failure, name='payment_failure'),
    path('history/', views.payment_history, name='payment_history'),
    path('webhook/', views.razorpay_webhook, name='razorpay_webhook'),
]

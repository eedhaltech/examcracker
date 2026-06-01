from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Product


@login_required
def products(request):
    product_type = request.GET.get('type', '')
    qs = Product.objects.filter(is_active=True)
    if product_type:
        qs = qs.filter(product_type=product_type)

    books      = Product.objects.filter(is_active=True, product_type='book').order_by('order')
    affiliates = Product.objects.filter(is_active=True, product_type='affiliate').order_by('order')
    courses    = Product.objects.filter(is_active=True, product_type='course').order_by('order')
    tools      = Product.objects.filter(is_active=True, product_type='tool').order_by('order')

    return render(request, 'products/products.html', {
        'books': books,
        'affiliates': affiliates,
        'courses': courses,
        'tools': tools,
        'active_type': product_type,
    })

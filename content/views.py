from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import Comment, SEOSettings


@login_required
def contact_page(request):
    # Approved + promoted comments visible to all
    comments = Comment.objects.filter(
        status__in=['approved', 'promoted']
    ).select_related('user').order_by('-is_featured', '-created_at')

    featured = comments.filter(is_featured=True)[:3]
    recent   = comments.filter(is_featured=False)[:20]

    # Check if user already submitted a comment
    user_comment = Comment.objects.filter(user=request.user).first()

    seo = SEOSettings.get()

    return render(request, 'content/contact.html', {
        'featured_comments': featured,
        'recent_comments':   recent,
        'user_comment':      user_comment,
        'total_comments':    comments.count(),
        'seo': {
            'title': 'Contact Us & Reviews — MCQ Platform',
            'description': 'Share your experience with MCQ Platform. Read what other students say about our quiz practice platform.',
            'keywords': 'MCQ platform review, student feedback, contact us, quiz platform experience',
        },
        'seo_settings': seo,
    })


@login_required
@require_POST
def submit_comment(request):
    body   = request.POST.get('body', '').strip()
    rating = int(request.POST.get('rating', 5))

    if not body:
        messages.error(request, 'Please write something before submitting.')
        return redirect('contact')

    if len(body) < 10:
        messages.error(request, 'Your comment is too short. Please write at least 10 characters.')
        return redirect('contact')

    rating = max(1, min(5, rating))

    # One comment per user — update if exists
    comment, created = Comment.objects.get_or_create(
        user=request.user,
        defaults={
            'body':   body,
            'rating': rating,
            'name':   request.user.email.split('@')[0],
            'status': 'pending',
        }
    )
    if not created:
        comment.body   = body
        comment.rating = rating
        comment.status = 'pending'  # re-review on edit
        comment.save()
        messages.success(request, 'Your review has been updated and is pending approval.')
    else:
        messages.success(request, 'Thank you! Your review has been submitted and is pending approval.')

    return redirect('contact')

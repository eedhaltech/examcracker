from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg, Count
from .models import Comment


@login_required
def contact(request):
    if request.method == 'POST':
        body   = request.POST.get('body', '').strip()
        rating = int(request.POST.get('rating', 5))

        if not body:
            messages.error(request, 'Please write something before submitting.')
            return redirect('contact')

        if len(body) < 10:
            messages.error(request, 'Your comment is too short. Please write at least 10 characters.')
            return redirect('contact')

        # One comment per user (update if exists, else create)
        Comment.objects.update_or_create(
            user=request.user,
            defaults={
                'name':   request.user.get_full_name() or request.user.email.split('@')[0],
                'email':  request.user.email,
                'body':   body,
                'rating': max(1, min(5, rating)),
                'status': 'pending',
            }
        )
        messages.success(request, 'Thank you! Your review has been submitted and is pending approval.')
        return redirect('contact')

    # Approved comments for display
    approved = Comment.objects.filter(status='approved').order_by('-is_featured', '-created_at')
    featured = approved.filter(is_featured=True)[:6]

    # Stats
    stats = Comment.objects.filter(status='approved').aggregate(
        avg_rating=Avg('rating'),
        total=Count('id'),
    )

    # Rating breakdown
    breakdown = {}
    for i in range(5, 0, -1):
        cnt = Comment.objects.filter(status='approved', rating=i).count()
        pct = round((cnt / stats['total']) * 100) if stats['total'] else 0
        breakdown[i] = {'count': cnt, 'pct': pct}

    # User's existing comment
    user_comment = Comment.objects.filter(user=request.user).first()

    return render(request, 'contact/contact.html', {
        'approved_comments': approved,
        'featured_comments': featured,
        'stats': stats,
        'breakdown': breakdown,
        'user_comment': user_comment,
    })

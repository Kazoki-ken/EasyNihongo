from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Badge, UserBadge, WeeklyStats, Profile
from .views import check_badges, get_weekly_stats # Re-using helper functions

@login_required
def test_profile_view(request):
    """
    Test view for the redesigned Profile page (Sakura Theme).
    """
    check_badges(request.user)
    weekly_stats = get_weekly_stats(request.user)

    # Barcha nishonlar va foydalanuvchi olgan nishonlar
    all_badges = Badge.objects.all().order_by('threshold')
    user_badges_ids = UserBadge.objects.filter(user=request.user).values_list('badge_id', flat=True)

    # Shablon uchun ma'lumot tayyorlash
    badges_display = []
    for badge in all_badges:
        is_earned = badge.id in user_badges_ids
        badges_display.append({
            'badge': badge,
            'is_earned': is_earned
        })

    return render(request, 'vocabulary/test_profile.html', {
        'weekly_stats': weekly_stats,
        'badges_display': badges_display
    })

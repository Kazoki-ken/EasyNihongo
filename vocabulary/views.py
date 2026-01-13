import random
import re
import json
from datetime import timedelta
import pandas as pd

from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.admin.views.decorators import staff_member_required

from .models import Word, Profile, Topic, WeeklyStats, UserWordProgress, Book, LeagueLog
from .forms import UserRegisterForm, WordForm

# =========================================================
# 1. YORDAMCHI FUNKSIYALAR (HELPERS)
# DIQQAT: Bularning tepasiga @login_required QO'YMANG!
# =========================================================

def update_word_progress(user, word, is_correct):
    """So'zning progressini yangilash (XP va Level)"""
    progress, created = UserWordProgress.objects.get_or_create(user=user, word=word)
    weekly_stats = get_weekly_stats(user)

    if is_correct:
        progress.xp += 1
        weekly_stats.xp_earned += 1 # XP qo'shish

        # Level Up logikasi: har 4 xp da 1 level
        if progress.xp >= 4:
            progress.level += 1
            progress.xp = 0
            # Keyingi takrorlash sanasi (hozircha oddiy mantiq)
            days_to_add = 3 if progress.level == 2 else 7 if progress.level == 3 else 14
            progress.next_review_date = timezone.now().date() + timedelta(days=days_to_add)
    else:
        # Jarima: -2 xp
        progress.xp -= 2
        weekly_stats.xp_earned -= 2 # XP ayirish
        if weekly_stats.xp_earned < 0:
            weekly_stats.xp_earned = 0 # Haftalik XP 0 dan tushib ketmasligi kerak

        if progress.xp < 0:
            if progress.level > 1:
                progress.level -= 1 # Level tushadi
                progress.xp = 2 # Oldingi levelning o'rtasiga tushadi
            else:
                progress.xp = 0 # 1-leveldan pastga tushmaydi

        # Xato qilsa, ertaga yana qaytarish kerak
        progress.next_review_date = timezone.now().date() + timedelta(days=1)

    progress.save()
    weekly_stats.save()

def get_weekly_stats(user):
    """Joriy hafta uchun statistika obyektini qaytaradi yoki yaratadi"""
    today = timezone.now().date()
    start_week = today - timedelta(days=today.weekday()) # Dushanba

    # 1. Oldingi haftalarning yig'ilmagan tangalarini tekshirish
    uncollected_stats = WeeklyStats.objects.filter(
        user=user,
        start_date__lt=start_week,
        is_collected=False
    )

    if uncollected_stats.exists():
        total_coins = 0
        for stat in uncollected_stats:
            total_coins += stat.coins_earned
            stat.is_collected = True
            stat.save()

        if total_coins > 0:
            profile = user.profile
            profile.coins += total_coins
            profile.save()

    # 2. Joriy hafta statistikasini olish
    stats, created = WeeklyStats.objects.get_or_create(
        user=user,
        start_date=start_week,
        defaults={'end_date': start_week + timedelta(days=6)}
    )
    return stats

def check_daily_progress(user):
    """
    Foydalanuvchi saytga kirganda ishlaydi.
    """
    if not hasattr(user, 'profile'):
        Profile.objects.create(user=user)
        
    profile = user.profile
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    
    if profile.last_game_date != today:
        profile.daily_test_count = 0
        profile.daily_match_count = 0
        profile.daily_write_count = 0
        profile.save()

    # Jarima tizimi
    if profile.last_login_date and profile.last_login_date < yesterday:
        profile.streak = 0
        profile.tree_state = 3
        profile.save()

def check_streak_update(profile):
    """
    O'yin tugagandan keyin chaqiriladi.
    """
    total_score = profile.daily_test_count + profile.daily_match_count + profile.daily_write_count
    
    if total_score == 9:
        today = timezone.now().date()
        if profile.last_login_date != today:
            profile.streak += 1
            profile.tree_state = 1
            profile.last_login_date = today
            profile.save()
            return True
    return False

def process_weekly_leagues():
    """
    O'tgan hafta natijalarini hisoblab, ligalarni yangilaydi.
    """
    today = timezone.now().date()
    start_of_current_week = today - timedelta(days=today.weekday()) # Bu Dushanba
    start_of_last_week = start_of_current_week - timedelta(days=7) # O'tgan Dushanba

    # Agar bu hafta uchun log allaqachon mavjud bo'lsa, qaytamiz (qayta ishlash shart emas)
    if LeagueLog.objects.filter(week_start_date=start_of_last_week).exists():
        return

    with transaction.atomic():
        # Qayta tekshirish (Race condition oldini olish uchun)
        if LeagueLog.objects.select_for_update().filter(week_start_date=start_of_last_week).exists():
            return

        # 1. O'tgan hafta statistikasini olamiz
        last_week_stats = WeeklyStats.objects.filter(start_date=start_of_last_week)

        if not last_week_stats.exists():
            # Hech kim o'ynamagan bo'lsa ham log yozib qo'yamiz, keyingi safar qayta tekshirmaslik uchun
            LeagueLog.objects.create(week_start_date=start_of_last_week)
            return

        # 2. Barcha profillarni olamiz
        # Profillarni bloklab turamiz (select_for_update), shunda bir vaqtning o'zida ikkita jarayon o'zgartira olmaydi
        profiles = list(Profile.objects.select_for_update().all())
        league_groups = {
            'Bronze': [], 'Silver': [], 'Gold': [], 'Platinum': [], 'Diamond': []
        }

        # Profillarni guruhlaymiz va XP sini bog'laymiz
        user_xp_map = {stat.user_id: stat.xp_earned for stat in last_week_stats}

        for p in profiles:
            xp = user_xp_map.get(p.user.id, 0)
            league_groups[p.league].append({'profile': p, 'xp': xp})

        # 3. Har bir liga bo'yicha hisob-kitob (Promote/Demote)
        leagues_order = ['Bronze', 'Silver', 'Gold', 'Platinum', 'Diamond']

        for i, league_name in enumerate(leagues_order):
            group = league_groups[league_name]
            # XP bo'yicha kamayish tartibida saralaymiz
            group.sort(key=lambda x: x['xp'], reverse=True)

            count = len(group)
            if count == 0: continue

            # Kimlar ko'tariladi va kimlar tushadi?
            # Qoida: Bir odam ham ko'tarilib, ham tusha olmaydi.
            # Shuning uchun avval Promotion ro'yxatini aniqlaymiz, keyin qolganlardan Demotion ni.

            promoted_indices = set()

            # --- PROMOTION (Yuqoriga chiqish) ---
            if i < len(leagues_order) - 1:
                next_league = leagues_order[i + 1]
                # Top 5 kishi ko'tariladi
                promoted_users = group[:5]
                for idx, item in enumerate(promoted_users):
                    # Faqat XP si 0 dan katta bo'lsa ko'tariladi
                    if item['xp'] > 0:
                        item['profile'].league = next_league
                        item['profile'].save()
                        promoted_indices.add(idx)

            # --- DEMOTION (Pastga tushish) ---
            if i > 0:
                prev_league = leagues_order[i - 1]
                # Bottom 5 kishi tushadi, LEKIN Promoted bo'lganlar bundan mustasno
                # Agar guruhda 5 kishidan kam bo'lsa, hech kim tushmaydi.
                # Agar guruhda 10 kishidan kam bo'lsa (masalan 6 kishi), va Top 5 ko'tarilsa,
                # 6-odam tushadimi?
                # User talabi: Top 5 ko'tariladi, Bottom 5 tushadi.
                # Agar 6 kishi bo'lsa: 1-5 ko'tariladi. 6-chi odam (Bottom 1) tushadi.
                # Agar 5 kishi bo'lsa: 1-5 ko'tariladi. Hech kim tushmaydi (chunki ular Top 5 da).

                # Demak, biz ro'yxatning oxiridan 5 ta odamni olamiz.
                # Agar o'sha odam 'promoted_indices' da bo'lsa, uni tushirmaymiz.

                potential_demotions = group[-5:] if count >= 5 else group # Oxirgi 5 ta (yoki boricha)

                # Lekin aniq index bo'yicha ishlashimiz kerak, chunki potential_demotions bu yangi list
                # Shuning uchun butun group bo'yicha aylanamiz

                # Quyidan 5 tasini sanaymiz
                demotion_candidates_count = 0
                for idx in range(count - 1, -1, -1): # Oxiridan boshga qarab
                    if demotion_candidates_count >= 5:
                        break

                    # Agar bu odam allaqachon ko'tarilgan bo'lsa, unga tegmaymiz
                    if idx in promoted_indices:
                        continue

                    # Aks holda, bu odam tushish zonasida
                    item = group[idx]
                    item['profile'].league = prev_league
                    item['profile'].save()
                    demotion_candidates_count += 1

        # Log yozib qo'yamiz
        LeagueLog.objects.create(week_start_date=start_of_last_week)

# =========================================================
# 2. ASOSIY SAHIFALAR (VIEWLAR)
# Bularga @login_required KERAK
# =========================================================

@login_required
def home(request):
    check_daily_progress(request.user)
    try:
        created_count = Word.objects.filter(author=request.user).count()
        saved_count = request.user.saved_words.count()
    except AttributeError:
        created_count = 0
        saved_count = 0
    
    total_words = created_count + saved_count
    
    context = {
        'total_words': total_words,
        'user': request.user,
        'profile': request.user.profile
    }
    return render(request, 'vocabulary/home.html', context)

@login_required
def dashboard(request):
    query = request.GET.get('q')
    topic_filter = request.GET.get('topic')
    words = Word.objects.filter(author__isnull=True)
    topics = Topic.objects.all()
    
    if query:
        words = words.filter(
            Q(japanese_word__icontains=query) | 
            Q(hiragana__icontains=query) | 
            Q(meaning__icontains=query)
        )
    if topic_filter:
        words = words.filter(topics__name=topic_filter)
    
    words = words.order_by('created_at').distinct()
    paginator = Paginator(words, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'words': page_obj,
        'topics': topics,
        'selected_topic': topic_filter,
        'title': 'Darslik Lugʻati',
    }
    return render(request, 'vocabulary/dashboard.html', context)

@login_required
def my_vocabulary(request):
    progress_map = {
        p.word_id: p for p in UserWordProgress.objects.filter(user=request.user)
    }
    user_words_qs = Word.objects.filter(author=request.user).order_by('-created_at')
    saved_words_qs = request.user.saved_words.all().order_by('-created_at')
    saved_books_qs = request.user.saved_books.all().order_by('-created_at')

    user_paginator = Paginator(user_words_qs, 20)
    user_page_number = request.GET.get('user_page')
    user_words = user_paginator.get_page(user_page_number)
    for word in user_words:
        word.user_progress = progress_map.get(word.id)

    saved_paginator = Paginator(saved_words_qs, 20)
    saved_page_number = request.GET.get('saved_page')
    saved_words = saved_paginator.get_page(saved_page_number)
    for word in saved_words:
        word.user_progress = progress_map.get(word.id)

    return render(request, 'vocabulary/my_vocabulary.html', {
        'user_words': user_words,
        'saved_words': saved_words,
        'saved_books': saved_books_qs
    })

@login_required
def categories_view(request):
    query = request.GET.get('q')
    tab = request.GET.get('tab', 'main')
    topics = Topic.objects.filter(book__isnull=True)
    books = Book.objects.all()

    if query:
        topics = topics.filter(name__icontains=query)
        books = books.filter(title__icontains=query)

    paginator = Paginator(topics, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'vocabulary/categories.html', {
        'page_obj': page_obj,
        'books': books,
        'search_query': query,
        'active_tab': tab
    })

@login_required
def book_details_view(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    topics = book.topics.all()
    is_saved = request.user in book.saves.all()
    return render(request, 'vocabulary/book_details.html', {
        'book': book,
        'topics': topics,
        'is_saved': is_saved
    })

@login_required
def toggle_book_save(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    if request.user in book.saves.all():
        book.saves.remove(request.user)
        saved = False
    else:
        book.saves.add(request.user)
        saved = True
    return JsonResponse({'saved': saved})

@login_required
def topic_words(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    words_qs = Word.objects.filter(author__isnull=True, topics=topic).order_by('created_at').distinct()
    paginator = Paginator(words_qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    words_all_saved = True
    saved_ids = request.user.saved_words.values_list('id', flat=True)
    has_unsaved = words_qs.exclude(id__in=saved_ids).exists()
    words_all_saved = not has_unsaved
            
    context = {
        'words': page_obj,
        'topic': topic,
        'topic_name': topic.name,
        'words_all_saved': words_all_saved
    }
    return render(request, 'vocabulary/topic_words.html', context)

@login_required
def save_all_topic_words(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    words = Word.objects.filter(author__isnull=True, topics=topic).distinct()
    user_saved_ids = request.user.saved_words.values_list('id', flat=True)
    has_unsaved = words.exclude(id__in=user_saved_ids).exists()

    saved = False
    if has_unsaved:
        new_words_to_add = words.exclude(id__in=user_saved_ids)
        count_new = new_words_to_add.count()
        for word in new_words_to_add:
            word.saves.add(request.user)
        if count_new > 0:
            stats = get_weekly_stats(request.user)
            stats.words_learned += count_new
            stats.save()
        saved = True
    else:
        count_removed = words.count()
        for word in words:
            word.saves.remove(request.user)
        if count_removed > 0:
            stats = get_weekly_stats(request.user)
            stats.words_learned -= count_removed
            stats.save()
        saved = False 
    return JsonResponse({'saved': saved})

# =========================================================
# 3. CRUD (Qo'shish/O'chirish/Saqlash)
# =========================================================

@login_required
def add_word(request):
    if request.method == 'POST':
        form = WordForm(request.POST)
        if form.is_valid():
            word = form.save(commit=False)
            word.author = request.user
            word.save()
            stats = get_weekly_stats(request.user)
            stats.words_learned += 1
            stats.save()
            return redirect('my_vocabulary')
    else:
        form = WordForm()
    return render(request, 'vocabulary/add_word.html', {'form': form})

@login_required
def toggle_save(request, word_id):
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'Login required'}, status=401)

    word = get_object_or_404(Word, id=word_id)
    if request.user in word.saves.all():
        word.saves.remove(request.user)
        saved = False
        stats = get_weekly_stats(request.user)
        stats.words_learned -= 1
        stats.save()
    else:
        word.saves.add(request.user)
        saved = True
        stats = get_weekly_stats(request.user)
        stats.words_learned += 1
        stats.save()
    return JsonResponse({'saved': saved})

@login_required
def delete_word(request, word_id):
    word = get_object_or_404(Word, id=word_id, author=request.user)
    word.delete()
    return redirect('my_vocabulary')

# =========================================================
# 4. AUTH & PROFILE
# =========================================================

@login_required
def profile_view(request):
    weekly_stats = get_weekly_stats(request.user)
    return render(request, 'vocabulary/profile.html', {'weekly_stats': weekly_stats})

@login_required
def leagues_view(request):
    """Yangi LIGALAR sahifasi"""
    # 1. Haftalik hisob-kitobni tekshirish (Lazy execution)
    process_weekly_leagues()

    # Userning league statusi process_weekly_leagues da o'zgargan bo'lishi mumkin
    # Lekin request.user keshlanib qolgan bo'lishi mumkin, shuning uchun yangilaymiz
    request.user.refresh_from_db()

    # Profile ni ham yangilaymiz (agar user.profile orqali keshlanib qolgan bo'lsa)
    user_profile = request.user.profile
    user_profile.refresh_from_db()

    current_league = user_profile.league

    # 2. Shu ligadagi foydalanuvchilarni olish
    profiles_in_league = Profile.objects.filter(league=current_league).select_related('user')

    # 3. Joriy haftalik XP bo'yicha saralash
    # Buning uchun har bir profilga uning joriy haftalik statistikasini bog'laymiz
    today = timezone.now().date()
    start_week = today - timedelta(days=today.weekday())

    # Bitta so'rov bilan shu hafta uchun barcha statistikalarni olamiz
    weekly_stats_map = {
        stat.user_id: stat.xp_earned
        for stat in WeeklyStats.objects.filter(start_date=start_week)
    }

    leaderboard_data = []
    for p in profiles_in_league:
        xp = weekly_stats_map.get(p.user.id, 0)
        leaderboard_data.append({
            'profile': p,
            'xp': xp
        })

    # XP bo'yicha kamayish tartibida saralash
    leaderboard_data.sort(key=lambda x: x['xp'], reverse=True)

    # User rankini aniqlash
    user_rank = 0
    for idx, item in enumerate(leaderboard_data):
        if item['profile'].user == request.user:
            user_rank = idx + 1
            break

    return render(request, 'vocabulary/leagues.html', {
        'current_league': current_league,
        'leaderboard_data': leaderboard_data,
        'user_rank': user_rank
    })

# Eski Leaderboard funksiyasini saqlab turamiz yoki o'chirib tashlaymiz?
# Hozircha URL da ishlatilmaydi, shuning uchun shunchaki leagues_view ga redirect qilamiz
@login_required
def leaderboard(request):
    return redirect('leagues')

def register_view(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Siz muvaffaqiyatli ro'yxatdan o'tdingiz! Endi kirishingiz mumkin.")
            return redirect('login')
    else:
        form = UserRegisterForm()
    context = {
        'form': form,
        'title': 'Roʻyxatdan oʻtish',
    }
    return render(request, 'registration/register.html', context)

def admin_dashboard(request):
    return render(request, 'vocabulary/admin_dashboard.html', {})

# =========================================================
# 5. O'YINLAR (GAMES LOGIC)
# =========================================================

@login_required
def games_menu(request):
    return render(request, 'vocabulary/games_menu.html')

# --- TEST O'YINI ---

@login_required
def test_setup(request):
    user_created = list(Word.objects.filter(author=request.user))
    user_saved = list(request.user.saved_words.all())
    unique_words = list(set(user_created + user_saved))
    word_count = len(unique_words)
    if word_count < 4:
        return render(request, 'vocabulary/low_words.html', {'count': word_count, 'threshold': 4})
    return render(request, 'vocabulary/test_setup.html')

@login_required
def test_start(request):
    if request.method == 'POST':
        limit = request.POST.get('limit')
        request.session['test_stats'] = {
            'total_questions': 0,
            'correct': 0,
            'wrong': 0,
            'limit': int(limit) if limit != 'infinite' else 'infinite',
            'potential_coins': 0,
        }
        return redirect('test_play')
    return redirect('test_setup')

@login_required
def test_play(request):
    stats = request.session.get('test_stats', None)
    if not stats:
        return redirect('games_menu')
    
    if request.GET.get('check_answer'):
        is_correct = request.GET.get('is_correct') == 'true'
        word_id = request.GET.get('word_id')
        if word_id:
            try:
                word_obj = Word.objects.get(id=word_id)
                update_word_progress(request.user, word_obj, is_correct)
            except Word.DoesNotExist:
                pass

        stats['total_questions'] += 1
        if is_correct:
            stats['correct'] += 1
        else:
            stats['wrong'] += 1

        w_stats = get_weekly_stats(request.user)
        w_stats.total_questions += 1
        if is_correct:
            w_stats.correct_answers += 1
            try:
                word_obj = Word.objects.get(id=word_id)
                if word_obj.author is None:
                     stats['potential_coins'] = stats.get('potential_coins', 0) + 1
            except Word.DoesNotExist:
                pass
        w_stats.save()
        
        request.session['test_stats'] = stats
        request.session.modified = True
        
        limit = stats['limit']
        if limit != 'infinite' and stats['total_questions'] >= limit:
            return redirect('test_result')
        return redirect('test_play')

    user_created = list(Word.objects.filter(author=request.user))
    user_saved = list(request.user.saved_words.all())
    my_vocabulary = list(set(user_created + user_saved))
    
    if len(my_vocabulary) < 4:
        return redirect('test_setup')
        
    today = timezone.now().date()
    due_ids = UserWordProgress.objects.filter(
        user=request.user,
        next_review_date__lte=today
    ).values_list('word_id', flat=True)

    due_words = [w for w in my_vocabulary if w.id in due_ids]
    if due_words:
        correct_word = random.choice(due_words)
    else:
        correct_word = random.choice(my_vocabulary)

    wrong_words = random.sample([w for w in my_vocabulary if w != correct_word], 3)
    variants = wrong_words + [correct_word]
    random.shuffle(variants)
    
    context = {
        'question': correct_word,
        'variants': variants,
        'stats': stats
    }
    return render(request, 'vocabulary/test_play.html', context)

@login_required
def test_result(request):
    stats = request.session.get('test_stats')
    if not stats:
        return redirect('games_menu')
    
    message = ""
    if stats['total_questions'] > 0:
        if not stats.get('saved_stats', False):
             w_stats = get_weekly_stats(request.user)
             w_stats.games_played += 1
             w_stats.save()
             stats['saved_stats'] = True
             request.session['test_stats'] = stats

        profile = request.user.profile
        today = timezone.now().date()
        if profile.last_game_date != today:
            profile.daily_test_count = 0
            profile.daily_match_count = 0
            profile.daily_write_count = 0
            profile.last_game_date = today
            profile.save()

        accuracy = (stats['correct'] / stats['total_questions']) * 100
        limit = stats['limit']
        eligible_for_coins = False

        if accuracy >= 60:
            if limit == 'infinite':
                if stats['total_questions'] > 30:
                    eligible_for_coins = True
            else:
                if stats['total_questions'] >= limit:
                    eligible_for_coins = True

        earned_coins = 0
        if eligible_for_coins:
            earned_coins = stats.get('potential_coins', 0)
            if earned_coins > 0:
                w_stats.coins_earned += earned_coins
                w_stats.save()

        stats['earned_coins'] = earned_coins

        if stats['total_questions'] < 10:
             message = "Ball olish uchun kamida 10 ta savol yechish kerak!"
        elif accuracy < 60:
             message = f"Natija past ({int(accuracy)}%). Ball olish uchun 60% kerak."
        elif profile.daily_test_count >= 3:
             message = "Bugungi Test limiti (3/3) to'lgan."
        else:
            profile.daily_test_count += 1
            profile.save()
            message = "Ajoyib! Kunlik maqsadga +1 ball qo'shildi."
            stats['saved'] = True
            check_streak_update(profile)

    request.session.pop('test_stats', None)
    
    context = {
        'stats': stats,
        'message': message,
        'accuracy': int(accuracy) if stats['total_questions'] > 0 else 0,
        'earned_coins': stats.get('earned_coins', 0)
    }
    return render(request, 'vocabulary/test_result.html', context)

# --- MATCHING (JUFTLIKLAR) O'YINI ---

@login_required
def match_play(request):
    created_words = Word.objects.filter(author=request.user)
    saved_words = request.user.saved_words.all()
    all_words_qs = (created_words | saved_words).distinct()
    all_words = list(all_words_qs)
    
    count = len(all_words)
    threshold = 6
    if count < threshold:
        return render(request, 'vocabulary/low_words.html', {
            'count': count,
            'threshold': threshold
        })

    if request.method == 'POST':
        rounds = int(request.POST.get('rounds', 3))
    else:
        rounds = 3
    
    cards_per_round = 5 
    total_words_needed = rounds * cards_per_round

    while len(all_words) < total_words_needed:
        all_words += all_words 
    
    random.shuffle(all_words)
    selected_words = all_words[:total_words_needed]

    system_words_count = sum(1 for w in selected_words if w.author is None)
    match_potential_coins = system_words_count // 5

    cards_data = []
    for word in selected_words:
        cards_data.append({'id': word.id, 'text': word.japanese_word})
        cards_data.append({'id': word.id, 'text': word.meaning})

    request.session['match_playing'] = True
    request.session['match_rounds'] = rounds
    request.session['match_potential_coins'] = match_potential_coins

    return render(request, 'vocabulary/match_play.html', {
        'cards_json': json.dumps(cards_data), 
        'total_rounds': rounds,
    })

@login_required
def match_result(request):
    if not request.session.get('match_playing'):
        return redirect('games_menu')

    del request.session['match_playing']
    rounds = request.session.get('match_rounds', 3)
    w_stats = get_weekly_stats(request.user)
    w_stats.games_played += 1

    earned_coins = request.session.get('match_potential_coins', 0)
    w_stats.coins_earned += earned_coins
    w_stats.save()
    request.session['match_last_earned_coins'] = earned_coins

    profile = request.user.profile
    today = timezone.now().date()
    
    if profile.last_game_date != today:
        profile.daily_test_count = 0
        profile.daily_match_count = 0
        profile.daily_write_count = 0
        profile.last_game_date = today
        profile.save()
        
    saved = False
    message = ""
    
    if profile.daily_match_count < 3:
        profile.daily_match_count += 1
        profile.save()
        saved = True
        message = "Barakalla! +1 Ball qo'shildi."
        check_streak_update(profile)
    else:
        message = "Bugungi Matching limiti to'lgan (3/3)."
        
    return render(request, 'vocabulary/match_result.html', {
        'saved': saved,
        'message': message,
        'count': profile.daily_match_count
    })

@login_required
def match_setup(request):
    return render(request, 'vocabulary/match_setup.html')

# --- WRITING (YOZISH) O'YINI ---
@login_required
def write_setup(request):
    created_words = Word.objects.filter(author=request.user)
    saved_words = request.user.saved_words.all()
    unique_words = list((created_words | saved_words).distinct())
    word_count = len(unique_words)
    if word_count < 5:
        return render(request, 'vocabulary/low_words.html', {
            'count': word_count, 
            'threshold': 5
        })
    return render(request, 'vocabulary/write_setup.html')

@login_required
def write_start(request):
    if request.method == 'POST':
        limit = request.POST.get('limit', '5')
        request.session['write_limit'] = limit
        request.session['write_stats'] = {
            'correct': 0,
            'wrong': 0,
            'total_questions': 0,
            'potential_coins': 0,
        }
        request.session['write_playing'] = True
        return redirect('write_play')
    return redirect('write_setup')

@login_required
def write_play(request):
    if not request.session.get('write_playing'):
        return redirect('write_setup')

    stats = request.session.get('write_stats')
    limit = request.session.get('write_limit')

    if request.method == 'POST':
        word_id = request.POST.get('word_id')
        user_answer = request.POST.get('user_answer', '').strip().lower()
        target_word = get_object_or_404(Word, id=word_id)
        valid_answers = []
        jp_word = target_word.japanese_word.lower()
        valid_answers.append(jp_word)
        if target_word.hiragana:
            valid_answers.append(target_word.hiragana.lower())
        match = re.search(r'(.*?)\s*\((.*?)\)', jp_word)
        if match:
            part1 = match.group(1).strip()
            part2 = match.group(2).strip()
            if part1: valid_answers.append(part1)
            if part2: valid_answers.append(part2)
        
        is_correct = (user_answer in valid_answers)
        stats['total_questions'] += 1
        if is_correct:
            stats['correct'] += 1
            messages.success(request, f"To'g'ri! {target_word.japanese_word}")
        else:
            stats['wrong'] += 1
            messages.error(request, f"Xato! To'g'ri javob: {target_word.japanese_word}")
            
        update_word_progress(request.user, target_word, is_correct)
        w_stats = get_weekly_stats(request.user)
        w_stats.total_questions += 1
        if is_correct:
            w_stats.correct_answers += 1
            if target_word.author is None:
                stats['potential_coins'] = stats.get('potential_coins', 0) + 1
        w_stats.save()
        request.session['write_stats'] = stats
        
        if limit != 'infinite':
            limit_int = int(limit)
            if stats['total_questions'] >= limit_int:
                return redirect('write_result')
        return redirect('write_play')

    created_words = Word.objects.filter(author=request.user)
    saved_words = request.user.saved_words.all()
    all_words = list((created_words | saved_words).distinct())
    if len(all_words) < 5:
         return redirect('write_setup')

    today = timezone.now().date()
    due_ids = UserWordProgress.objects.filter(
        user=request.user,
        next_review_date__lte=today
    ).values_list('word_id', flat=True)
    due_words = [w for w in all_words if w.id in due_ids]
    if due_words:
        word = random.choice(due_words)
    else:
        word = random.choice(all_words)

    context = {
        'word': word,
        'stats': stats,
        'limit': limit
    }
    return render(request, 'vocabulary/write_play.html', context)

@login_required
def write_result(request):
    if not request.session.get('write_playing'):
        return redirect('games_menu')

    del request.session['write_playing']
    stats = request.session.get('write_stats', {'correct':0, 'wrong':0, 'total_questions':0})
    limit = request.session.get('write_limit', '5')
    
    w_stats = get_weekly_stats(request.user)
    w_stats.games_played += 1
    w_stats.save()

    profile = request.user.profile
    today = timezone.now().date()
    if profile.last_game_date != today:
        profile.daily_test_count = 0
        profile.daily_match_count = 0
        profile.daily_write_count = 0
        profile.last_game_date = today
        profile.save()

    accuracy = 0
    if stats['total_questions'] > 0:
        accuracy = int((stats['correct'] / stats['total_questions']) * 100)

    eligible_for_coins = False
    if accuracy >= 60:
        if limit == 'infinite':
            if stats['total_questions'] > 30:
                eligible_for_coins = True
        else:
            if stats['total_questions'] >= int(limit):
                eligible_for_coins = True

    earned_coins = 0
    if eligible_for_coins:
        earned_coins = stats.get('potential_coins', 0)
        if earned_coins > 0:
            w_stats.coins_earned += earned_coins
            w_stats.save()

    stats['earned_coins'] = earned_coins
    saved = False
    message = ""
    
    if stats['total_questions'] < 5:
        message = "Ball olish uchun kamida 5 ta so'z yozish kerak."
    elif accuracy < 60:
        message = f"Natija past ({accuracy}%). Ball olish uchun 60% kerak."
    elif profile.daily_write_count >= 3:
        message = "Bugungi Yozish limiti (3/3) to'lgan."
    else:
        profile.daily_write_count += 1
        profile.save()
        saved = True
        message = "Ajoyib! Kunlik maqsadga +1 ball qo'shildi."
        check_streak_update(profile)

    return render(request, 'vocabulary/write_result.html', {
        'stats': stats,
        'accuracy': accuracy,
        'saved': saved,
        'message': message,
        'count': profile.daily_write_count,
        'limit': limit,
        'earned_coins': earned_coins
    })

@login_required
def quiz_home(request):
    return redirect('games_menu')

@staff_member_required
def upload_words(request):
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        try:
            df = pd.read_excel(excel_file)
            added_count = 0
            for index, row in df.iterrows():
                jap = str(row['Japanese']).strip()
                hira = str(row['Hiragana']).strip() if pd.notna(row['Hiragana']) else ""
                mean = str(row['Meaning']).strip()
                topics_str = str(row['Topics']) if pd.notna(row['Topics']) else ""
                word, created = Word.objects.get_or_create(
                    japanese_word=jap,
                    defaults={'hiragana': hira, 'meaning': mean}
                )
                if topics_str:
                    topic_names = [t.strip() for t in topics_str.split(',')]
                    for t_name in topic_names:
                        if t_name:
                            topic_obj, _ = Topic.objects.get_or_create(name=t_name)
                            word.topics.add(topic_obj)
                word.save()
                added_count += 1
            messages.success(request, f"{added_count} ta so'z muvaffaqiyatli yuklandi!")
        except Exception as e:
            messages.error(request, f"Xatolik: {str(e)}")
    return render(request, 'vocabulary/upload.html')

@staff_member_required
def upload_book_words(request):
    if request.method == 'POST':
        book_id = request.POST.get('book_id')
        new_book_title = request.POST.get('new_book_title')
        topic_id = request.POST.get('topic_id')
        new_topic_name = request.POST.get('new_topic_name')
        excel_file = request.FILES.get('excel_file')
        if not excel_file:
            messages.error(request, "Excel fayl tanlanmagan!")
            return redirect('upload_book_words')
        book = None
        if new_book_title:
            book, created = Book.objects.get_or_create(title=new_book_title)
        elif book_id:
            book = get_object_or_404(Book, id=book_id)
        else:
            messages.error(request, "Kitob tanlanmagan yoki yangi nom kiritilmagan!")
            return redirect('upload_book_words')
        topic = None
        if new_topic_name:
            topic, created = Topic.objects.get_or_create(name=new_topic_name, book=book)
        elif topic_id:
            topic = get_object_or_404(Topic, id=topic_id)
            if topic.book is None:
                topic.book = book
                topic.save()
            elif topic.book != book:
                messages.warning(request, f"Diqqat: '{topic.name}' mavzusi '{topic.book.title}' kitobiga tegishli edi. So'zlar o'sha mavzuga qo'shildi.")
        else:
            messages.error(request, "Mavzu tanlanmagan!")
            return redirect('upload_book_words')
        try:
            df = pd.read_excel(excel_file)
            added_count = 0
            for index, row in df.iterrows():
                jap = str(row['Japanese']).strip()
                hira = str(row['Hiragana']).strip() if pd.notna(row['Hiragana']) else ""
                mean = str(row['Meaning']).strip()
                word, created = Word.objects.get_or_create(
                    japanese_word=jap,
                    defaults={'hiragana': hira, 'meaning': mean}
                )
                word.topics.add(topic)
                word.save()
                added_count += 1
            messages.success(request, f"{book.title} -> {topic.name}: {added_count} ta so'z muvaffaqiyatli yuklandi!")
        except Exception as e:
            messages.error(request, f"Xatolik: {str(e)}")
        return redirect('upload_book_words')
    books = Book.objects.all()
    topics = Topic.objects.all()
    return render(request, 'vocabulary/upload_book.html', {
        'books': books,
        'topics': topics
    })

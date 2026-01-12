import random
import re
import json
from datetime import timedelta
import pandas as pd

from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.admin.views.decorators import staff_member_required

from .models import Word, Profile, Topic, WeeklyStats, UserWordProgress
from .forms import UserRegisterForm, WordForm

# =========================================================
# 1. YORDAMCHI FUNKSIYALAR (HELPERS)
# DIQQAT: Bularning tepasiga @login_required QO'YMANG!
# =========================================================

def update_word_progress(user, word, is_correct):
    """So'zning progressini yangilash (XP va Level)"""
    progress, created = UserWordProgress.objects.get_or_create(user=user, word=word)

    if is_correct:
        progress.xp += 1
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
        if progress.xp < 0:
            if progress.level > 1:
                progress.level -= 1 # Level tushadi
                progress.xp = 2 # Oldingi levelning o'rtasiga tushadi
            else:
                progress.xp = 0 # 1-leveldan pastga tushmaydi

        # Xato qilsa, ertaga yana qaytarish kerak
        progress.next_review_date = timezone.now().date() + timedelta(days=1)

    progress.save()

def get_weekly_stats(user):
    """Joriy hafta uchun statistika obyektini qaytaradi yoki yaratadi"""
    today = timezone.now().date()
    start_week = today - timedelta(days=today.weekday()) # Dushanba

    # 1. Oldingi haftalarning yig'ilmagan tangalarini tekshirish
    # DIQQAT: start_date dan foydalanish xavfsizroq, chunki end_date modelda aniq ko'rinmayapti
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
            # Xabar berish (agar kerak bo'lsa) - bu yerda request yo'q, shuning uchun shunchaki saqlaymiz

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

    # Eslatma: last_login_date faqat 9/9 bo'lganda check_streak_update da yangilanadi


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

# =========================================================
# 2. ASOSIY SAHIFALAR (VIEWLAR)
# Bularga @login_required KERAK
# =========================================================

@login_required
def home(request):
    # Mana bu yerda chaqirayotganimiz uchun xavfsiz
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
# ############################
@login_required
def dashboard(request):
    query = request.GET.get('q')
    topic_filter = request.GET.get('topic')
    
    words = Word.objects.filter(author__isnull=True)
    # Mavzular endi alohida modeldan olinadi
    topics = Topic.objects.all()
    
    if query:
        words = words.filter(
            Q(japanese_word__icontains=query) | 
            Q(hiragana__icontains=query) | 
            Q(meaning__icontains=query)
        )
    
    if topic_filter:
        # ManyToMany filtrlash
        words = words.filter(topics__name=topic_filter)
    
    # --- PAGINATION (DASHBOARD) ---
    words = words.order_by('created_at').distinct()
    paginator = Paginator(words, 20) # Sahifasiga 20 ta
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'words': page_obj, # Endi to'liq ro'yxat emas, sahifa obyekti
        'topics': topics,
        'selected_topic': topic_filter,
        'title': 'Darslik Lugʻati',
    }
    return render(request, 'vocabulary/dashboard.html', context)

@login_required
def my_vocabulary(request):
    # Progress ma'lumotlarini ham olamiz (prefetch_related)
    # Lekin shablon ichida qulay bo'lishi uchun, keling, Word modeliga "user_progress" degan
    # vaqtinchalik attribut qo'shib chiqamiz (yoki shablonda custom tag ishlatamiz).
    # Eng osone: barcha progresslarni olib, lug'at (dict) ga aylantiramiz.

    progress_map = {
        p.word_id: p for p in UserWordProgress.objects.filter(user=request.user)
    }

    # 1. Foydalanuvchi O'ZI QO'SHGAN so'zlar
    user_words_qs = Word.objects.filter(author=request.user).order_by('-created_at')
    
    # 2. Foydalanuvchi SAQLAB QO'YGAN so'zlar
    saved_words_qs = request.user.saved_words.all().order_by('-created_at')

    # --- PAGINATION (USER WORDS) ---
    user_paginator = Paginator(user_words_qs, 20)
    user_page_number = request.GET.get('user_page')
    user_words = user_paginator.get_page(user_page_number)

    # Har bir so'zga progressni biriktiramiz (User Words)
    for word in user_words:
        word.user_progress = progress_map.get(word.id)

    # --- PAGINATION (SAVED WORDS) ---
    saved_paginator = Paginator(saved_words_qs, 20)
    saved_page_number = request.GET.get('saved_page')
    saved_words = saved_paginator.get_page(saved_page_number)

    # Har bir so'zga progressni biriktiramiz (Saved Words)
    for word in saved_words:
        word.user_progress = progress_map.get(word.id)

    return render(request, 'vocabulary/my_vocabulary.html', {
        'user_words': user_words,
        'saved_words': saved_words
    })
########################################
@login_required
def categories_view(request):
    query = request.GET.get('q')
    topics = Topic.objects.all()

    if query:
        topics = topics.filter(name__icontains=query)

    # --- PAGINATION (TOPICS) ---
    # 10 ta bo'limdan chiqaramiz
    paginator = Paginator(topics, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'vocabulary/categories.html', {
        'page_obj': page_obj
    })
###########################################
@login_required
def topic_words(request, topic_name):
    # Mavzu nomi bo'yicha so'zlarni olish
    words_qs = Word.objects.filter(author__isnull=True, topics__name=topic_name).order_by('created_at').distinct()

    # --- PAGINATION (TOPIC WORDS) ---
    paginator = Paginator(words_qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # "Hammasini saqlash" tugmasi holatini tekshirish
    # DIQQAT: Bu yerda endi faqat joriy sahifadagi so'zlarni emas,
    # balki UMUMIY ro'yxatni tekshirishimiz kerak bo'lishi mumkin,
    # lekin vizual jihatdan sahifadagi so'zlar saqlanganligini ko'rsatish kifoya qiladi
    # yoki backendda to'liq tekshirish qoldiramiz.

    # Hozircha "Hammasini saqlash" mantiqi frontendda tugma bosilganda serverga murojaat qiladi.
    # Shuning uchun bu yerda 'words_all_saved' ni faqat joriy sahifa uchun hisoblash maqsadga muvofiq,
    # yoki butun QuerySet uchun. Keling butun QuerySet uchun qilamiz.
    
    words_all_saved = True
    # Optimization: exists() ishlatish samarasiz bo'lishi mumkin loop ichida,
    # lekin hozircha oddiy yondashuv:
    # Agar bitta bo'lsa ham saqlanmagan so'z bo'lsa -> False
    # (Bu yerda Paginator bo'lgani uchun loopni butun 'words_qs' bo'ylab aylanish og'ir bo'lishi mumkin
    # Agar so'zlar ko'p bo'lsa. Lekin "save_all" funksiyasi baribir hammasini o'zgartiradi).

    # Keling, optimizatsiya qilamiz:
    # Foydalanuvchi saqlagan so'zlar ID larini olamiz
    saved_ids = request.user.saved_words.values_list('id', flat=True)

    # Mavzudagi barcha so'zlar ichida saved_ids da YO'Q bo'lgan so'z bormi?
    # exclude(id__in=saved_ids).exists() -> Agar True bo'lsa, demak hammasi saqlanmagan.
    has_unsaved = words_qs.exclude(id__in=saved_ids).exists()
    words_all_saved = not has_unsaved
            
    context = {
        'words': page_obj, # Sahifalangan obyekt
        'topic_name': topic_name,
        'words_all_saved': words_all_saved
    }
    return render(request, 'vocabulary/topic_words.html', context)
################################
@login_required
def save_all_topic_words(request, topic_name):
    words = Word.objects.filter(author__isnull=True, topics__name=topic_name).distinct()
    
    # 1. Hamma so'zlar saqlanganmi?
    # Optimization: exists() bilan tekshiramiz
    user_saved_ids = request.user.saved_words.values_list('id', flat=True)
    has_unsaved = words.exclude(id__in=user_saved_ids).exists()

    saved = False

    if has_unsaved:
        # 2. HAMMASINI SAQLASH (ADD)
        # Faqat hali saqlanmagan so'zlarni topamiz (takroriy qo'shmaslik uchun)
        new_words_to_add = words.exclude(id__in=user_saved_ids)
        count_new = new_words_to_add.count()

        for word in new_words_to_add:
            word.saves.add(request.user)

        # Statistikaga qo'shish
        if count_new > 0:
            stats = get_weekly_stats(request.user)
            stats.words_learned += count_new
            stats.save()

        saved = True
    else:
        # 3. HAMMASINI O'CHIRISH (REMOVE)
        count_removed = words.count()
        for word in words:
            word.saves.remove(request.user)

        # Statistikadan ayirish
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

            # Haftalik statistikaga qo'shish
            stats = get_weekly_stats(request.user)
            stats.words_learned += 1
            stats.save()

            return redirect('my_vocabulary')
    else:
        form = WordForm()
    return render(request, 'vocabulary/add_word.html', {'form': form})

@login_required
def toggle_save(request, word_id):
    # Agar foydalanuvchi kirmagan bo'lsa, xato bermasin, shunchaki qaytarsin
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'Login required'}, status=401)

    word = get_object_or_404(Word, id=word_id)
    
    if request.user in word.saves.all():
        word.saves.remove(request.user)
        saved = False # Hozir o'chirildi

        # Statistikadan ayirish
        stats = get_weekly_stats(request.user)
        stats.words_learned -= 1
        stats.save()
    else:
        word.saves.add(request.user)
        saved = True # Hozir saqlandi

        # Haftalik statistikaga qo'shish
        stats = get_weekly_stats(request.user)
        stats.words_learned += 1
        stats.save()
    
    # Biz sahifani yangilamaymiz, faqat natijani yuboramiz
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
def leaderboard(request):
    # Top 20 foydalanuvchi: Streak bo'yicha saralangan
    # Agar streak bir xil bo'lsa, total_daily_progress bo'yicha
    # Bu yerda total_daily_progress hisoblanmaydi (property), shuning uchun oddiyroq streak bo'yicha qilamiz.

    top_profiles = Profile.objects.select_related('user').order_by('-streak', '-daily_test_count')[:20]

    # Foydalanuvchining o'z o'rni
    user_rank = 0
    all_profiles = Profile.objects.order_by('-streak')
    # Optimization: Bu katta bazada sekin ishlashi mumkin, lekin hozircha yetarli
    for index, p in enumerate(all_profiles):
        if p.user == request.user:
            user_rank = index + 1
            break

    return render(request, 'vocabulary/leaderboard.html', {
        'top_profiles': top_profiles,
        'user_rank': user_rank
    })

def register_view(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save() # Yangi foydalanuvchini saqlaymiz
            messages.success(request, "Siz muvaffaqiyatli ro'yxatdan o'tdingiz! Endi kirishingiz mumkin.")
            return redirect('login') # Muvaffaqiyatli bo'lsa, kirish sahifasiga
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

    # 1-MUAMMO YECHIMI: Universal threshold (Test uchun 4)
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

        # SRS (Aqlli Takrorlash)
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

        # Haftalik statistika (Har bir savol uchun)
        w_stats = get_weekly_stats(request.user)
        w_stats.total_questions += 1
        if is_correct:
            w_stats.correct_answers += 1
            # Coin logikasi: Faqat bazadagi (author is Null) so'zlar uchun
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
        
    # SRS Mantiq: Bugungi takrorlash kerak bo'lgan so'zlarni olamiz
    today = timezone.now().date()
    due_ids = UserWordProgress.objects.filter(
        user=request.user,
        next_review_date__lte=today
    ).values_list('word_id', flat=True)

    due_words = [w for w in my_vocabulary if w.id in due_ids]

    # Agar takrorlash kerak bo'lgan so'zlar bo'lsa, ulardan birini tanlaymiz (70% ehtimol bilan)
    # Yoki shunchaki ustunlik beramiz. Keling, agar bor bo'lsa, aniq o'shalardan so'raymiz.
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
        # Haftalik statistika: O'yin sonini oshiramiz
        if not stats.get('saved_stats', False):
             w_stats = get_weekly_stats(request.user)
             w_stats.games_played += 1
             w_stats.save()
             stats['saved_stats'] = True
             request.session['test_stats'] = stats

        profile = request.user.profile
        # KUN YANGILANGAN BO'LSA NOLLASH
        today = timezone.now().date()
        if profile.last_game_date != today:
            profile.daily_test_count = 0
            profile.daily_match_count = 0
            profile.daily_write_count = 0
            profile.last_game_date = today
            profile.save()

        accuracy = (stats['correct'] / stats['total_questions']) * 100
        
        # --- Coin berish qoidalari ---
        # 1. 60% dan yuqori aniqlik
        # 2. To'liq yechilgan (limit bo'yicha) yoki Infinite bo'lsa 30 tadan ko'p
        limit = stats['limit']
        eligible_for_coins = False

        if accuracy >= 60:
            if limit == 'infinite':
                if stats['total_questions'] > 30:
                    eligible_for_coins = True
            else:
                # Agar limit belgilangan bo'lsa, to'liq yechgan bo'lishi kerak
                # (Test o'yini avtomatik redirect qiladi limitga yetganda, demak yetib kelgan)
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
            
            # --- 2-MUAMMO YECHIMI: 9 BALL BO'LDIMI TEKSHIRAMIZ ---
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
    # 1. FAQAT FOYDALANUVCHI SO'ZLARINI OLISH
    # A) O'zi yaratgan so'zlar
    created_words = Word.objects.filter(author=request.user)
    # B) Saqlab qo'ygan (yurakcha) so'zlar
    saved_words = request.user.saved_words.all()
    
    # Ikkalasini birlashtiramiz (takrorlanishsiz)
    # | belgisi ikkita QuerySetni birlashtiradi (Union)
    all_words_qs = (created_words | saved_words).distinct()
    all_words = list(all_words_qs)
    
    count = len(all_words)
    threshold = 6  # Minimum 4 ta so'z kerak
    
    # AGAR SO'Z YETMASA -> low_words.html GA YUBORAMIZ
    if count < threshold:
        return render(request, 'vocabulary/low_words.html', {
            'count': count,
            'threshold': threshold
        })

    # 2. Raundlarni aniqlash
    if request.method == 'POST':
        rounds = int(request.POST.get('rounds', 3))
    else:
        rounds = 3
    
    cards_per_round = 5 
    total_words_needed = rounds * cards_per_round

    # Agar so'z yetmasa, borini takrorlaymiz
    # (Masalan: sizda 10 ta so'z bor, lekin 50 ta kerak -> so'zlar aylanib keladi)
    while len(all_words) < total_words_needed:
        all_words += all_words 
    
    random.shuffle(all_words)
    selected_words = all_words[:total_words_needed]

    # Coin hisoblash: Faqat tizim so'zlari (author is None)
    system_words_count = sum(1 for w in selected_words if w.author is None)
    # 5 ta tizim so'zi uchun 1 coin (ya'ni 1 raund to'liq tizim so'zi bo'lsa)
    match_potential_coins = system_words_count // 5

    # JSON tayyorlash
    cards_data = []
    for word in selected_words:
        cards_data.append({'id': word.id, 'text': word.japanese_word})
        cards_data.append({'id': word.id, 'text': word.meaning})

    # Sessiyaga yozib qo'yamiz (Refresh muammosi uchun)
    request.session['match_playing'] = True
    request.session['match_rounds'] = rounds
    request.session['match_potential_coins'] = match_potential_coins

    return render(request, 'vocabulary/match_play.html', {
        'cards_json': json.dumps(cards_data), 
        'total_rounds': rounds,
    })

@login_required
def match_result(request):
    # 1. Sessiyani tekshirish (Refresh himoyasi)
    if not request.session.get('match_playing'):
        return redirect('games_menu')

    # O'yin tugadi, sessiyani tozalaymiz
    del request.session['match_playing']

    rounds = request.session.get('match_rounds', 3)

    # Haftalik statistika: O'yin soni (Match uchun)
    w_stats = get_weekly_stats(request.user)
    w_stats.games_played += 1

    # Coinlarni qo'shish
    earned_coins = request.session.get('match_potential_coins', 0)
    w_stats.coins_earned += earned_coins
    w_stats.save()

    # Sessiyaga yozib qo'yamiz (shablonda ko'rsatish uchun)
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
        
        # --- 2-MUAMMO YECHIMI: 9 BALL BO'LDIMI TEKSHIRAMIZ ---
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
# --- 1. SOZLAMALAR (SETUP) ---
@login_required
def write_setup(request):
    # Faqat foydalanuvchiga tegishli so'zlarni olamiz
    created_words = Word.objects.filter(author=request.user)
    saved_words = request.user.saved_words.all()
    
    # Birlashtiramiz va takroriylarni olib tashlaymiz
    unique_words = list((created_words | saved_words).distinct())
    word_count = len(unique_words)
    
    # Agar so'z kam bo'lsa -> Low Words sahifasi
    if word_count < 5:
        return render(request, 'vocabulary/low_words.html', {
            'count': word_count, 
            'threshold': 5
        })

    return render(request, 'vocabulary/write_setup.html')


# --- 2. O'YINNI BOSHLASH (START) ---
@login_required
def write_start(request):
    if request.method == 'POST':
        # Limitni olamiz: '5', '10' yoki 'infinite'
        limit = request.POST.get('limit', '5')
        
        # Sessiyani tozalab, yangi o'yin uchun tayyorlaymiz
        request.session['write_limit'] = limit
        request.session['write_stats'] = {
            'correct': 0,
            'wrong': 0,
            'total_questions': 0,
            'potential_coins': 0,
        }
        # "O'yin jarayoni ketyapti" degan belgi
        request.session['write_playing'] = True
        
        return redirect('write_play')
        
    return redirect('write_setup')


# --- 3. O'YIN JARAYONI (PLAY) ---
@login_required
def write_play(request):
    # Agar o'yin rasman boshlanmagan bo'lsa (start bosilmagan bo'lsa)
    if not request.session.get('write_playing'):
        return redirect('write_setup')

    # Sessiyadagi ma'lumotlarni o'qiymiz
    stats = request.session.get('write_stats')
    limit = request.session.get('write_limit')

    # --- JAVOBNI TEKSHIRISH (POST) ---
    if request.method == 'POST':
        word_id = request.POST.get('word_id')
        user_answer = request.POST.get('user_answer', '').strip().lower()
        
        # Bazadan so'zni topamiz
        target_word = get_object_or_404(Word, id=word_id)
        
        # TO'G'RI JAVOBLAR RO'YXATINI TUZAMIZ
        valid_answers = []
        
        # 1. Asosiy so'z (masalan: "学生 (がくせい)")
        jp_word = target_word.japanese_word.lower()
        valid_answers.append(jp_word)
        
        # 2. Hiragana maydoni (agar bo'lsa)
        if target_word.hiragana:
            valid_answers.append(target_word.hiragana.lower())
            
        # 3. Qavs ichidagi va tashqarisidagi so'zlarni ajratish
        # Regex orqali: "Kanji (Kana)" formatini tahlil qilamiz
        match = re.search(r'(.*?)\s*\((.*?)\)', jp_word)
        if match:
            part1 = match.group(1).strip() # Qavsdan oldingi (Kanji)
            part2 = match.group(2).strip() # Qavs ichidagi (Kana)
            if part1: valid_answers.append(part1)
            if part2: valid_answers.append(part2)
        
        # Tekshiramiz: Foydalanuvchi javobi ro'yxatda bormi?
        is_correct = (user_answer in valid_answers)
        
        # Statistikani yangilaymiz
        stats['total_questions'] += 1
        if is_correct:
            stats['correct'] += 1
            messages.success(request, f"To'g'ri! {target_word.japanese_word}")
        else:
            stats['wrong'] += 1
            messages.error(request, f"Xato! To'g'ri javob: {target_word.japanese_word}")
            
        # Aqlli Takrorlash (Spaced Repetition)
        update_word_progress(request.user, target_word, is_correct)

        # Haftalik statistika
        w_stats = get_weekly_stats(request.user)
        w_stats.total_questions += 1
        if is_correct:
            w_stats.correct_answers += 1
            # Coin logikasi: Faqat bazadagi so'zlar uchun
            if target_word.author is None:
                stats['potential_coins'] = stats.get('potential_coins', 0) + 1
        w_stats.save()

        request.session['write_stats'] = stats
        
        # Limit tekshiruvi (Agar 'infinite' bo'lmasa)
        if limit != 'infinite':
            limit_int = int(limit)
            if stats['total_questions'] >= limit_int:
                return redirect('write_result')
        
        # Keyingi savolga o'tish (Redirect GET metodiga aylanadi)
        return redirect('write_play')

    # --- SAVOL KO'RSATISH (GET) ---
    
    # So'zlarni olish
    created_words = Word.objects.filter(author=request.user)
    saved_words = request.user.saved_words.all()
    all_words = list((created_words | saved_words).distinct())
    
    # Ehtiyot shart: so'z kam bo'lsa
    if len(all_words) < 5:
         return redirect('write_setup')

    # SRS Mantiq: Bugungi takrorlash kerak bo'lgan so'zlarni olamiz
    today = timezone.now().date()
    due_ids = UserWordProgress.objects.filter(
        user=request.user,
        next_review_date__lte=today
    ).values_list('word_id', flat=True)

    due_words = [w for w in all_words if w.id in due_ids]

    # Tasodifiy so'z tanlash (SRS ustunligi bilan)
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


# --- 4. NATIJA (RESULT) ---
@login_required
def write_result(request):
    # 1. Sessiyani tekshirish (Refresh himoyasi)
    if not request.session.get('write_playing'):
        return redirect('games_menu')

    # O'yin tugadi, sessiyani tozalaymiz
    del request.session['write_playing']
    
    stats = request.session.get('write_stats', {'correct':0, 'wrong':0, 'total_questions':0})
    limit = request.session.get('write_limit', '5')
    
    # Haftalik statistika: O'yin sonini oshiramiz
    w_stats = get_weekly_stats(request.user)
    w_stats.games_played += 1
    w_stats.save()

    profile = request.user.profile
    
    # 2. KUN YANGILANGAN BO'LSA NOLLASH (Test o'yinidagi kabi)
    today = timezone.now().date()
    if profile.last_game_date != today:
        profile.daily_test_count = 0
        profile.daily_match_count = 0
        profile.daily_write_count = 0
        profile.last_game_date = today
        profile.save()

    # 3. Natijani hisoblash
    accuracy = 0
    if stats['total_questions'] > 0:
        accuracy = int((stats['correct'] / stats['total_questions']) * 100)

    # --- Coin berish qoidalari ---
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

    # 4. BALL BERISH MANTIQI
    # Yozish mashqi qiyinroq, lekin "Oson" rejim 5 ta so'zdan iborat.
    # Shuning uchun kamida 5 ta savolga javob bergan bo'lishi kerak.
    
    if stats['total_questions'] < 5:
        message = "Ball olish uchun kamida 5 ta so'z yozish kerak."
        
    elif accuracy < 60:
        message = f"Natija past ({accuracy}%). Ball olish uchun 60% kerak."
        
    elif profile.daily_write_count >= 3:
        message = "Bugungi Yozish limiti (3/3) to'lgan."
        
    else:
        # --- MUVAFFAQIYAT! ---
        profile.daily_write_count += 1
        profile.save()
        
        saved = True
        message = "Ajoyib! Kunlik maqsadga +1 ball qo'shildi."
        
        # --- STREAK (Daraxt) TEKSHIRUVI ---
        # Bu funksiya sizning views.py faylingizda bor deb hisoblaymiz
        check_streak_update(profile)

    return render(request, 'vocabulary/write_result.html', {
        'stats': stats,
        'accuracy': accuracy,
        'saved': saved,
        'message': message,
        'count': profile.daily_write_count, # Hozirgi hisob (masalan: 2)
        'limit': limit,
        'earned_coins': earned_coins
    })
 # --- ESKI O'YIN (Agar kerak bo'lmasa o'chirib tashlasa ham bo'ladi) ---
@login_required
def quiz_home(request):
    return redirect('games_menu')






#####################################################################################

@staff_member_required
def upload_words(request):
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        
        try:
            df = pd.read_excel(excel_file)
            added_count = 0
            
            for index, row in df.iterrows():
                # Excel ustunlarini o'qiymiz
                jap = str(row['Japanese']).strip()
                # Hiragana va Ma'no bo'sh bo'lsa ham xato bermasligi uchun tekshiramiz
                hira = str(row['Hiragana']).strip() if pd.notna(row['Hiragana']) else ""
                mean = str(row['Meaning']).strip()
                topics_str = str(row['Topics']) if pd.notna(row['Topics']) else ""

                # So'zni yaratamiz
                word, created = Word.objects.get_or_create(
                    japanese_word=jap,
                    defaults={'hiragana': hira, 'meaning': mean}
                )
                
                # Mavzularni qo'shamiz (vergul bilan ajratilgan bo'lsa)
                if topics_str:
                    topic_names = [t.strip() for t in topics_str.split(',')]
                    for t_name in topic_names:
                        if t_name:
                            # Mavzu bazada yo'q bo'lsa, avtomatik yaratiladi
                            topic_obj, _ = Topic.objects.get_or_create(name=t_name)
                            word.topics.add(topic_obj)
                
                word.save()
                added_count += 1
            
            messages.success(request, f"{added_count} ta so'z muvaffaqiyatli yuklandi!")
            
        except Exception as e:
            messages.error(request, f"Xatolik: {str(e)}")
            
    return render(request, 'vocabulary/upload.html')




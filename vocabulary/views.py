import random
import re
import json
from datetime import timedelta
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import Word, Profile
from .models import Topic
from .forms import UserRegisterForm, WordForm
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse # <-- Buni qo'shish esdan chiqmasin!
from django.contrib import messages

import pandas as pd
from django.contrib.admin.views.decorators import staff_member_required
from .models import Word, Topic

# =========================================================
# 1. YORDAMCHI FUNKSIYALAR (HELPERS)
# DIQQAT: Bularning tepasiga @login_required QO'YMANG!
# =========================================================

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
    
    context = {
        'words': words.order_by('created_at').distinct(), # distinct() takrorlanishni oldini oladi
        'topics': topics,
        'selected_topic': topic_filter,
        'title': 'Darslik Lugʻati',
    }
    return render(request, 'vocabulary/dashboard.html', context)

@login_required
def my_vocabulary(request):
    # 1. Foydalanuvchi O'ZI QO'SHGAN so'zlar (Author = User)
    user_words = Word.objects.filter(author=request.user).order_by('-created_at')
    
    # 2. Foydalanuvchi SAQLAB QO'YGAN so'zlar (Likes/Saves)
    # Eslatma: related_name='saved_words' deb yozgan edik models.py da
    saved_words = request.user.saved_words.all().order_by('-created_at')

    return render(request, 'vocabulary/my_vocabulary.html', {
        'user_words': user_words,
        'saved_words': saved_words
    })
########################################
@login_required
def categories_view(request):
    # Barcha mavzularni chiqaramiz
    topics = Topic.objects.all()
    return render(request, 'vocabulary/categories.html', {'topics': topics})
###########################################
@login_required
def topic_words(request, topic_name):
    # Mavzu nomi bo'yicha so'zlarni olish
    words = Word.objects.filter(author__isnull=True, topics__name=topic_name).order_by('created_at').distinct()
    
    words_all_saved = True
    for w in words:
        if request.user not in w.saves.all():
            words_all_saved = False
            break
            
    context = {
        'words': words,
        'topic_name': topic_name,
        'words_all_saved': words_all_saved
    }
    return render(request, 'vocabulary/topic_words.html', context)
################################
@login_required
def save_all_topic_words(request, topic_name):
    words = Word.objects.filter(author__isnull=True, topics__name=topic_name).distinct()
    
    all_saved = True
    for word in words:
        if request.user not in word.saves.all():
            all_saved = False
            break

    if not all_saved:
        for word in words:
            word.saves.add(request.user)
        saved = True 
    else:
        for word in words:
            word.saves.remove(request.user)
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
    else:
        word.saves.add(request.user)
        saved = True # Hozir saqlandi
    
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
    return render(request, 'vocabulary/profile.html')

def register_view(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save() # Yangi foydalanuvchini saqlaymiz
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
            'limit': int(limit) if limit != 'infinite' else 'infinite'
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
        stats['total_questions'] += 1
        if is_correct:
            stats['correct'] += 1
        else:
            stats['wrong'] += 1
        
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
        'accuracy': int((stats['correct'] / stats['total_questions']) * 100) if stats['total_questions'] > 0 else 0
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

    # JSON tayyorlash
    cards_data = []
    for word in selected_words:
        cards_data.append({'id': word.id, 'text': word.japanese_word})
        cards_data.append({'id': word.id, 'text': word.meaning})

    # Sessiyaga yozib qo'yamiz (Refresh muammosi uchun)
    request.session['match_playing'] = True
    request.session['match_rounds'] = rounds

    return render(request, 'vocabulary/match_play.html', {
        'cards_json': json.dumps(cards_data), 
        'total_rounds': rounds,
    })

@login_required
def match_result(request):
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
            'total_questions': 0
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

    # Tasodifiy so'z tanlash
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
        'limit': limit
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


















































# import random
# from datetime import timedelta
# from django.utils import timezone
# from django.shortcuts import render, redirect, get_object_or_404
# from django.contrib.auth.decorators import login_required
# from django.db.models import Q
# from .models import Word, Profile
# from .forms import UserRegisterForm, WordForm
# import re # <-- BUNI ENG TEPAGA QO'SHISHNI UNUTMANG!

# # =========================================================
# # 1. YORDAMCHI FUNKSIYALAR (HELPERS)
# # =========================================================

# def check_daily_progress(user):
#     """
#     Foydalanuvchi kirganda yangi kunni tekshiradi.
#     """
#     if not hasattr(user, 'profile'):
#         Profile.objects.create(user=user)
        
#     profile = user.profile
#     today = timezone.now().date()
    
#     # Agar oxirgi kirgan sanasi bugun bo'lmasa (demak yangi kun)
#     if profile.last_login_date != today:
#         yesterday = today - timedelta(days=1)
        
#         # 1. STREAK MANTIQI
#         if profile.last_login_date == yesterday:
#             # Agar kecha kirgan bo'lsa, bugun davom etadi (+1)
#             profile.streak += 1
#         elif profile.last_login_date and profile.last_login_date < yesterday:
#             # Agar kechadan oldin kirgan bo'lsa (uzilish), Streak kuyadi
#             profile.streak = 1 # Bugungi kun 1-kun hisoblanadi
#             profile.tree_state = 2 # Daraxt xavf ostida
            
#             if profile.last_login_date < (today - timedelta(days=2)):
#                  profile.tree_state = 3 # Daraxt quridi
#         else:
#             # Agar umuman birinchi marta kirayotgan bo'lsa yoki streak 0 bo'lsa
#             profile.streak += 1

#         # 2. O'YINLARNI NOLLASH
#         profile.daily_test_count = 0
#         profile.daily_match_count = 0
#         profile.daily_write_count = 0
        
#         # 3. SANANI YANGILASH
#         profile.last_login_date = today
#         profile.save()

# # =========================================================
# # 2. ASOSIY SAHIFALAR
# # =========================================================

# @login_required
# def home(request):
#     check_daily_progress(request.user)
#     return render(request, 'vocabulary/home.html')

# @login_required
# def dashboard(request):
#     query = request.GET.get('q')
#     topic_filter = request.GET.get('topic')
    
#     # Faqat Admin so'zlarini olamiz
#     words = Word.objects.filter(author__isnull=True)
#     topics = Word.objects.filter(author__isnull=True).values_list('topic', flat=True).distinct()
    
#     if query:
#         words = words.filter(
#             Q(japanese_word__icontains=query) | 
#             Q(hiragana__icontains=query) | 
#             Q(meaning__icontains=query)
#         )
    
#     if topic_filter:
#         words = words.filter(topic=topic_filter)
    
#     context = {
#         'words': words.order_by('created_at'),
#         'topics': topics,
#         'selected_topic': topic_filter,
#         'title': 'Darslik Lugʻati',
#     }
#     return render(request, 'vocabulary/dashboard.html', context)

# @login_required
# def my_vocabulary(request):
#     my_created = Word.objects.filter(author=request.user).order_by('-created_at')
#     my_saved = request.user.saved_words.all().order_by('-created_at')
    
#     context = {
#         'my_created': my_created,
#         'my_saved': my_saved,
#         'title': "Mening Lug'atim"
#     }
#     return render(request, 'vocabulary/my_vocabulary.html', context)

# @login_required
# def categories_view(request):
#     topics = Word.objects.filter(author__isnull=True).values_list('topic', flat=True).distinct()
#     return render(request, 'vocabulary/categories.html', {'topics': topics})

# @login_required
# def topic_words(request, topic_name):
#     words = Word.objects.filter(author__isnull=True, topic=topic_name).order_by('created_at')
    
#     words_all_saved = True
#     for w in words:
#         if request.user not in w.saves.all():
#             words_all_saved = False
#             break
            
#     context = {
#         'words': words,
#         'topic_name': topic_name,
#         'words_all_saved': words_all_saved
#     }
#     return render(request, 'vocabulary/topic_words.html', context)

# @login_required
# def save_all_topic_words(request, topic_name):
#     words = Word.objects.filter(author__isnull=True, topic=topic_name)
#     all_saved = True
#     for word in words:
#         if request.user not in word.saves.all():
#             all_saved = False
#             break

#     if not all_saved:
#         for word in words:
#             if request.user not in word.saves.all():
#                 word.saves.add(request.user)
#     else:
#         for word in words:
#             word.saves.remove(request.user)
            
#     return redirect('topic_words', topic_name=topic_name)

# # =========================================================
# # 3. CRUD (Qo'shish/O'chirish/Saqlash)
# # =========================================================

# @login_required
# def add_word(request):
#     if request.method == 'POST':
#         form = WordForm(request.POST)
#         if form.is_valid():
#             word = form.save(commit=False)
#             word.author = request.user
#             word.save()
#             return redirect('my_vocabulary')
#     else:
#         form = WordForm()
#     return render(request, 'vocabulary/add_word.html', {'form': form})

# @login_required
# def toggle_save_word(request, word_id):
#     word = get_object_or_404(Word, id=word_id)
#     if request.user in word.saves.all():
#         word.saves.remove(request.user)
#     else:
#         word.saves.add(request.user)
#     return redirect(request.META.get('HTTP_REFERER', 'dashboard'))

# @login_required
# def delete_word(request, word_id):
#     word = get_object_or_404(Word, id=word_id, author=request.user)
#     word.delete()
#     return redirect('my_vocabulary')

# # =========================================================
# # 4. AUTH & PROFILE
# # =========================================================

# @login_required
# def profile_view(request):
#     return render(request, 'vocabulary/profile.html')

# def register_view(request):
#     if request.method == 'POST':
#         form = UserRegisterForm(request.POST)
#         if form.is_valid():
#             form.save()
#             return redirect('login')
#     else:
#         form = UserRegisterForm()
#     return render(request, 'registration/register.html', {'form': form})

# def admin_dashboard(request):
#     return render(request, 'vocabulary/admin_dashboard.html', {})

# # =========================================================
# # 5. O'YINLAR (GAMES LOGIC)
# # =========================================================

# @login_required
# def games_menu(request):
#     return render(request, 'vocabulary/games_menu.html')

# # --- TEST O'YINI ---

# @login_required
# def test_setup(request):
#     user_created = list(Word.objects.filter(author=request.user))
#     user_saved = list(request.user.saved_words.all())
#     unique_words = list(set(user_created + user_saved))
#     word_count = len(unique_words)

#     if word_count < 4:
#         # threshold=4 deb yuboramiz
#         return render(request, 'vocabulary/low_words.html', {'count': word_count, 'threshold': 4})

#     return render(request, 'vocabulary/test_setup.html')

# @login_required
# def test_start(request):
#     if request.method == 'POST':
#         limit = request.POST.get('limit')
#         request.session['test_stats'] = {
#             'total_questions': 0,
#             'correct': 0,
#             'wrong': 0,
#             'limit': int(limit) if limit != 'infinite' else 'infinite'
#         }
#         return redirect('test_play')
#     return redirect('test_setup')

# @login_required
# def test_play(request):
#     stats = request.session.get('test_stats', None)
#     if not stats:
#         return redirect('games_menu')
    
#     # Javobni tekshirish
#     if request.GET.get('check_answer'):
#         is_correct = request.GET.get('is_correct') == 'true'
#         stats['total_questions'] += 1
#         if is_correct:
#             stats['correct'] += 1
#         else:
#             stats['wrong'] += 1
        
#         request.session['test_stats'] = stats
#         request.session.modified = True
        
#         limit = stats['limit']
#         if limit != 'infinite' and stats['total_questions'] >= limit:
#             return redirect('test_result')
#         return redirect('test_play')

#     # Yangi savol tayyorlash
#     user_created = list(Word.objects.filter(author=request.user))
#     user_saved = list(request.user.saved_words.all())
#     my_vocabulary = list(set(user_created + user_saved))
    
#     if len(my_vocabulary) < 4:
#         return redirect('test_setup')
        
#     correct_word = random.choice(my_vocabulary)
#     wrong_words = random.sample([w for w in my_vocabulary if w != correct_word], 3)
#     variants = wrong_words + [correct_word]
#     random.shuffle(variants)
    
#     context = {
#         'question': correct_word,
#         'variants': variants,
#         'stats': stats
#     }
#     return render(request, 'vocabulary/test_play.html', context)

# @login_required
# def test_result(request):
#     stats = request.session.get('test_stats')
#     if not stats:
#         return redirect('games_menu')
    
#     message = ""
    
#     if stats['total_questions'] > 0:
#         profile = request.user.profile
#         today = timezone.now().date()
        
#         if profile.last_game_date != today:
#             profile.daily_test_count = 0
#             profile.daily_match_count = 0
#             profile.daily_write_count = 0
#             profile.last_game_date = today
#             profile.save()

#         accuracy = (stats['correct'] / stats['total_questions']) * 100
        
#         if stats['total_questions'] < 10:
#              message = "Ball olish uchun kamida 10 ta savol yechish kerak!"
#         elif accuracy < 60:
#              message = f"Natija past ({int(accuracy)}%). Ball olish uchun 60% kerak."
#         elif profile.daily_test_count >= 3:
#              message = "Bugungi Test limiti (3/3) to'lgan. Boshqa o'yinlarni o'ynang!"
#         else:
#             profile.daily_test_count += 1
#             profile.save()
#             message = "Ajoyib! Kunlik maqsadga +1 ball qo'shildi."
#             stats['saved'] = True

#     request.session.pop('test_stats', None)
    
#     context = {
#         'stats': stats,
#         'message': message,
#         'accuracy': int((stats['correct'] / stats['total_questions']) * 100) if stats['total_questions'] > 0 else 0
#     }
#     return render(request, 'vocabulary/test_result.html', context)

# # --- MATCHING (JUFTLIKLAR) O'YINI ---

# @login_required
# def match_play(request):
#     user_created = list(Word.objects.filter(author=request.user))
#     user_saved = list(request.user.saved_words.all())
#     my_vocabulary = list(set(user_created + user_saved))
#     word_count = len(my_vocabulary)

#     if word_count < 5:
#          # threshold=5 deb yuboramiz
#          return render(request, 'vocabulary/low_words.html', {'count': word_count, 'threshold': 5})
#     selected_words = random.sample(my_vocabulary, 5)

#     cards = []
#     for word in selected_words:
#         cards.append({'id': word.id, 'text': word.japanese_word, 'type': 'jp'})
#         cards.append({'id': word.id, 'text': word.meaning, 'type': 'uz'})

#     random.shuffle(cards)
#     return render(request, 'vocabulary/match_play.html', {'cards': cards})

# @login_required
# def match_result(request):
#     profile = request.user.profile
#     today = timezone.now().date()
    
#     if profile.last_game_date != today:
#         profile.daily_test_count = 0
#         profile.daily_match_count = 0
#         profile.daily_write_count = 0
#         profile.last_game_date = today
#         profile.save()
        
#     saved = False
#     message = ""
    
#     if profile.daily_match_count < 3:
#         profile.daily_match_count += 1
#         profile.save()
#         saved = True
#         message = "Barakalla! +1 Ball qo'shildi."
#     else:
#         message = "Bugungi Matching limiti to'lgan (3/3)."
        
#     return render(request, 'vocabulary/match_result.html', {
#         'saved': saved,
#         'message': message,
#         'count': profile.daily_match_count
#     })

# # === 3. WRITING (YOZISH) O'YINI ===

# @login_required
# def write_setup(request):
#     user_created = list(Word.objects.filter(author=request.user))
#     user_saved = list(request.user.saved_words.all())
#     unique_words = list(set(user_created + user_saved))
#     word_count = len(unique_words)
    
#     if word_count < 5:
#         # threshold=5 deb yuboramiz
#         return render(request, 'vocabulary/low_words.html', {'count': word_count, 'threshold': 5})

#     return render(request, 'vocabulary/write_setup.html')

# @login_required
# def write_start(request):
#     if request.method == 'POST':
#         # Yozish mashqi qiyinroq, shuning uchun standart 5 ta so'z qilamiz
#         request.session['write_stats'] = {
#             'total_questions': 0,
#             'correct': 0,
#             'wrong': 0,
#             'limit': 5 # Har bir raund 5 ta so'zdan iborat
#         }
#         return redirect('write_play')
#     return redirect('write_setup')

# @login_required
# def write_play(request):
#     stats = request.session.get('write_stats', None)
#     if not stats:
#         return redirect('games_menu')

#     # --- JAVOBNI TEKSHIRISH ---
#     if request.method == 'POST':
#         user_answer = request.POST.get('answer', '').strip().lower()
#         # Virgul bilan ajratilgan javoblarni ro'yxatga aylantiramiz
#         correct_answers_list = request.POST.get('valid_answers', '').split(',')
        
#         is_correct = False
#         # Har bir to'g'ri variantni tekshiramiz
#         for ans in correct_answers_list:
#             if user_answer == ans.strip().lower():
#                 is_correct = True
#                 break
        
#         stats['total_questions'] += 1
#         if is_correct:
#             stats['correct'] += 1
#         else:
#             stats['wrong'] += 1
            
#         request.session['write_stats'] = stats
#         request.session.modified = True
        
#         # Limit tugadimi?
#         if stats['total_questions'] >= stats['limit']:
#             return redirect('write_result')
        
#         return redirect('write_play')

#     # --- YANGI SAVOL TAYYORLASH ---
#     user_created = list(Word.objects.filter(author=request.user))
#     user_saved = list(request.user.saved_words.all())
#     my_vocabulary = list(set(user_created + user_saved))
    
#     if len(my_vocabulary) < 5:
#         my_vocabulary = list(Word.objects.all())
    
#     word = random.choice(my_vocabulary)
    
#     # --- JAVOBLARNI AJRATIB OLISH (AQLLI MANTIQ) ---
#     valid_answers = []
    
#     # 1. Hiragana maydoni (Sizda bu yerda "Konnichiwa" bor)
#     if word.hiragana:
#         valid_answers.append(word.hiragana)
    
#     # 2. Qavs ichidagini olamiz: "日進月歩 (こんにちは)" -> "こんにちは"
#     match = re.search(r'\((.*?)\)', word.japanese_word)
#     if match:
#         inside_parens = match.group(1)
#         valid_answers.append(inside_parens)
    
#     # 3. KANJI QISMI (YANGI): Qavsdan oldingi qismni olamiz -> "日進月歩"
#     # split('(')[0] -> qavsgacha bo'lgan qismni kesib oladi
#     kanji_part = word.japanese_word.split('(')[0].strip()
#     if kanji_part:
#         valid_answers.append(kanji_part)
        
#     # 4. Butun so'zni ham qo'shib qo'yamiz (Ehtiyot shart)
#     valid_answers.append(word.japanese_word)
    
#     # Ro'yxatni stringga aylantiramiz (HTMLga yuborish uchun)
#     valid_answers_str = ",".join(valid_answers)
    
#     context = {
#         'word': word,
#         'valid_answers': valid_answers_str,
#         'stats': stats
#     }
#     return render(request, 'vocabulary/write_play.html', context)

# @login_required
# def write_result(request):
#     stats = request.session.get('write_stats')
#     if not stats:
#         return redirect('games_menu')
    
#     profile = request.user.profile
#     today = timezone.now().date()
    
#     if profile.last_game_date != today:
#         profile.daily_test_count = 0
#         profile.daily_match_count = 0
#         profile.daily_write_count = 0
#         profile.last_game_date = today
#         profile.save()
        
#     saved = False
#     message = ""
    
#     # Yozish qiyin, shuning uchun 5 tadan 3 tasini topsa ham ball beramiz (60%)
#     accuracy = (stats['correct'] / stats['limit']) * 100
    
#     if accuracy >= 60:
#         if profile.daily_write_count < 3:
#             profile.daily_write_count += 1
#             profile.save()
#             saved = True
#             message = "Barakalla! +1 Ball qo'shildi."
#         else:
#             message = "Bugungi Yozish limiti to'lgan (3/3)."
#     else:
#         message = "Ball olish uchun 60% natija kerak."
        
#     request.session.pop('write_stats', None)
    
#     return render(request, 'vocabulary/write_result.html', {
#         'saved': saved,
#         'message': message,
#         'stats': stats,
#         'count': profile.daily_write_count
#     })


# # --- ESKI O'YIN (Agar kerak bo'lmasa o'chirib tashlasa ham bo'ladi) ---
# @login_required
# def quiz_home(request):
#     return redirect('games_menu')












































# import random # Test o'yini uchun kerak bo'ladi
# from datetime import timedelta
# from django.utils import timezone
# from django.shortcuts import render, redirect, get_object_or_404
# # ... qolgan importlar turaversin
# from django.contrib.auth.decorators import login_required   
# from django.shortcuts import render, redirect, get_object_or_404
# from .models import Word
# from .forms import UserRegisterForm, WordForm
# from django.db.models import Q 

# # vocabulary/views.py ichida

# def check_daily_progress(user):
#     profile = user.profile
#     today = timezone.now().date()
    
#     if profile.last_login_date != today:
#         yesterday = today - timedelta(days=1)
        
#         # Kecha kirmagan bo'lsa streak kuyadi va daraxt zararlanadi
#         if profile.last_login_date and profile.last_login_date < yesterday:
#             profile.tree_state = 2 
#             profile.streak = 0
#             if profile.last_login_date < (today - timedelta(days=2)):
#                  profile.tree_state = 3
        
#         # --- YANGI KUN UCHUN HAMMA O'YINLARNI NOLLAYMIZ ---
#         profile.daily_test_count = 0   # <--- BIZGA SHU KERAK
#         profile.daily_match_count = 0
#         profile.daily_write_count = 0
        
#         profile.last_login_date = today
#         profile.save()

# # 1. ASOSIY MENYU (HOME)
# @login_required
# def home(request):
#     # Profil borligini tekshirish
#     if not hasattr(request.user, 'profile'):
#         from .models import Profile
#         Profile.objects.create(user=request.user)
    
#     # --- VAQTNI TEKSHIRISHNI ISHGA TUSHIRAMIZ ---
#     check_daily_progress(request.user)
    
#     return render(request, 'vocabulary/home.html')

# # 2. DARSLIK LUG'ATI (Faqat Admin so'zlari ko'rinadi)
# @login_required
# def dashboard(request):
#     query = request.GET.get('q')
#     topic_filter = request.GET.get('topic') # Tanlangan mavzuni olamiz
    
#     # 1. Faqat Admin so'zlarini olamiz
#     words = Word.objects.filter(author__isnull=True)
    
#     # 2. Mavzular ro'yxatini shakllantiramiz (takrorlanmas qilib)
#     # Bu hamma mavzular tugmasi uchun kerak
#     topics = Word.objects.filter(author__isnull=True).values_list('topic', flat=True).distinct()
    
#     # 3. Agar qidiruv bo'lsa
#     if query:
#         words = words.filter(
#             Q(japanese_word__icontains=query) | 
#             Q(hiragana__icontains=query) | 
#             Q(meaning__icontains=query)
#         )
    
#     # 4. Agar mavzu tanlangan bo'lsa
#     if topic_filter:
#         words = words.filter(topic=topic_filter)
    
#     context = {
#         'words': words.order_by('created_at'),
#         'topics': topics,
#         'selected_topic': topic_filter,
#         'title': 'Darslik Lugʻati',
#     }
#     return render(request, 'vocabulary/dashboard.html', context)

# # 3. MENING LUG'ATIM (Faqat o'zi qo'shgan va saqlaganlari)
# @login_required
# def my_vocabulary(request):
#     # Faqat kirib turgan user qo'shgan so'zlar (Boshqaniki ko'rinmaydi)
#     my_created = Word.objects.filter(author=request.user).order_by('-created_at')
    
#     # User "Like" (Save) bosgan admin so'zlari
#     my_saved = request.user.saved_words.all().order_by('-created_at')
    
#     context = {
#         'my_created': my_created,
#         'my_saved': my_saved,
#         'title': "Mening Lug'atim"
#     }
#     return render(request, 'vocabulary/my_vocabulary.html', context)

# # 4. YANGI SO'Z QO'SHISH
# @login_required
# def add_word(request):
#     if request.method == 'POST':
#         form = WordForm(request.POST)
#         if form.is_valid():
#             word = form.save(commit=False)
#             word.author = request.user # So'z egasini belgilash
#             word.save()
#             return redirect('my_vocabulary')
#     else:
#         form = WordForm()
#     return render(request, 'vocabulary/add_word.html', {'form': form})

# # 5. SAQLASH (LIKE) FUNKSIYASI
# @login_required
# def toggle_save_word(request, word_id):
#     word = get_object_or_404(Word, id=word_id)
#     if request.user in word.saves.all():
#         word.saves.remove(request.user)
#     else:
#         word.saves.add(request.user)
#     return redirect(request.META.get('HTTP_REFERER', 'dashboard'))

# # 6. O'CHIRISH FUNKSIYASI
# @login_required
# def delete_word(request, word_id):
#     # Faqat o'ziga tegishli so'zni o'chira olishi uchun author=request.user shart
#     word = get_object_or_404(Word, id=word_id, author=request.user)
#     word.delete()
#     return redirect('my_vocabulary')

# # 7. PROFIL VA RO'YXATDAN O'TISH
# @login_required
# def profile_view(request):
#     return render(request, 'vocabulary/profile.html')

# def register_view(request):
#     if request.method == 'POST':
#         form = UserRegisterForm(request.POST)
#         if form.is_valid():
#             form.save()
#             return redirect('login')
#     else:
#         form = UserRegisterForm()
#     return render(request, 'registration/register.html', {'form': form})

# def admin_dashboard(request):
#     return render(request, 'vocabulary/admin_dashboard.html', {})

# # 1. Faqat Mavzular (Kategoriyalar) ro'yxatini ko'rsatuvchi view
# @login_required
# def categories_view(request):
#     # Admin qo'shgan so'zlar ichidagi takrorlanmas mavzularni olamiz
#     topics = Word.objects.filter(author__isnull=True).values_list('topic', flat=True).distinct()
#     return render(request, 'vocabulary/categories.html', {'topics': topics})

# # 2. Tanlangan mavzu ichidagi so'zlarni ko'rsatuvchi view
# @login_required
# def topic_words(request, topic_name):
#     words = Word.objects.filter(author__isnull=True, topic=topic_name).order_by('created_at')
    
#     # Hamma so'z saqlanganmi yoki yo'qligini tekshirish
#     words_all_saved = True
#     for w in words:
#         if request.user not in w.saves.all():
#             words_all_saved = False
#             break
            
#     context = {
#         'words': words,
#         'topic_name': topic_name,
#         'words_all_saved': words_all_saved # Buni HTMLga yuboramiz
#     }
#     return render(request, 'vocabulary/topic_words.html', context)

# # vocabulary/views.py fayliga qo'shing

# @login_required
# def save_all_topic_words(request, topic_name):
#     # Shu mavzuga tegishli barcha admin so'zlarini olamiz
#     words = Word.objects.filter(author__isnull=True, topic=topic_name)
    
#     # Bu mavzudagi so'zlar foydalanuvchi tomonidan allaqachon saqlanganmi yoki yo'qligini tekshiramiz
#     # Agar hech bo'lmaganda bitta so'z saqlanmagan bo'lsa, demak biz "Hamma saqlash" rejimidamiz
#     # Agar hammasi saqlangan bo'lsa, demak biz "Hammasini o'chirish" rejimiga o'tamiz
#     all_saved = True
#     for word in words:
#         if request.user not in word.saves.all():
#             all_saved = False
#             break

#     if not all_saved:
#         # Agar hali hammasi saqlanmagan bo'lsa -> HAMMASINI SAQLAYMIZ
#         for word in words:
#             if request.user not in word.saves.all():
#                 word.saves.add(request.user)
#     else:
#         # Agar hammasi allaqachon saqlangan bo'lsa -> HAMMASINI O'CHIRAMIZ
#         for word in words:
#             word.saves.remove(request.user)
            
#     return redirect('topic_words', topic_name=topic_name)


# @login_required
# def quiz_home(request):
#     # 1. Bazadan barcha so'zlarni olamiz
#     all_words = list(Word.objects.all())
    
#     # Agar so'zlar kam bo'lsa (4 tadan kam), o'yin o'ynab bo'lmaydi
#     if len(all_words) < 4:
#         return render(request, 'vocabulary/quiz_home.html', {'error': "O'yin uchun kamida 4 ta so'z kerak!"})
    
#     # 2. To'g'ri javobni tanlaymiz (Random)
#     correct_word = random.choice(all_words)
    
#     # 3. Noto'g'ri javoblar (3 ta boshqa so'z)
#     wrong_words = random.sample([w for w in all_words if w != correct_word], 3)
    
#     # 4. Hamma variantlarni birlashtiramiz va aralashtiramiz
#     variants = wrong_words + [correct_word]
#     random.shuffle(variants)
    
#     context = {
#         'question': correct_word,  # Savol (Yaponchasi)
#         'variants': variants,      # Variantlar (O'zbekchasi)
#     }
#     return render(request, 'vocabulary/quiz_home.html', context)

# # 1. O'YINLAR MENYUSI (3 ta o'yin tanlash)
# @login_required
# def games_menu(request):
#     return render(request, 'vocabulary/games_menu.html')

# # 2. TEST SOZLASH (Limit tanlash)
# # vocabulary/views.py ichida

# @login_required
# def test_setup(request):
#     # 1. Foydalanuvchining hamma so'zlarini sanaymiz
#     user_created = list(Word.objects.filter(author=request.user))
#     user_saved = list(request.user.saved_words.all())
    
#     # Takrorlanmasligi uchun set qilamiz
#     unique_words = list(set(user_created + user_saved))
#     word_count = len(unique_words)

#     # 2. Agar 4 tadan kam bo'lsa -> Ogohlantirish sahifasiga yuboramiz
#     if word_count < 4:
#         return render(request, 'vocabulary/low_words.html', {'count': word_count})

#     # Agar hammasi joyida bo'lsa, limit tanlash sahifasi ochiladi
#     return render(request, 'vocabulary/test_setup.html')

# # 3. TESTNI BOSHLASH (Eski ma'lumotlarni tozalash)
# @login_required
# def test_start(request):
#     if request.method == 'POST':
#         limit = request.POST.get('limit')
#         # Sessiyada o'yin holatini saqlaymiz
#         request.session['test_stats'] = {
#             'total_questions': 0,
#             'correct': 0,
#             'wrong': 0,
#             'limit': int(limit) if limit != 'infinite' else 'infinite'
#         }
#         return redirect('test_play')
#     return redirect('test_setup')

# # 4. O'YIN JARAYONI
# # vocabulary/views.py ichida

# @login_required
# def test_play(request):
#     # 1. Sessiyadan o'yin holatini olamiz
#     stats = request.session.get('test_stats', None)
    
#     # Agar o'yin boshlanmagan bo'lsa (sessiya yo'q), menyuga qaytaramiz
#     if not stats:
#         return redirect('games_menu')
    
#     # 2. JAVOBNI TEKSHIRISH (Agar foydalanuvchi javob bergan bo'lsa)
#     # Frontenddagi JS bizga '?check_answer=true' va 'is_correct' ni yuboradi
#     if request.GET.get('check_answer'):
#         is_correct = request.GET.get('is_correct') == 'true'
        
#         # Statistikani yangilaymiz
#         stats['total_questions'] += 1
#         if is_correct:
#             stats['correct'] += 1
#         else:
#             stats['wrong'] += 1
        
#         # Yangilangan statistikani sessiyaga saqlaymiz
#         request.session['test_stats'] = stats
#         request.session.modified = True
        
#         # Limitni tekshirish (Agar cheksiz bo'lmasa va limitga yetgan bo'lsa)
#         limit = stats['limit']
#         if limit != 'infinite' and stats['total_questions'] >= limit:
#             return redirect('test_result')
            
#         # Keyingi savolga o'tish (URL parametrlarini tozalash uchun redirect)
#         return redirect('test_play')

#     # 3. YANGI SAVOL TAYYORLASH
#     # Faqat foydalanuvchining o'z so'zlari (yaratgan + saqlagan)
#     user_created = list(Word.objects.filter(author=request.user))
#     user_saved = list(request.user.saved_words.all())
    
#     # Ikkalasini birlashtiramiz (takrorlanmasligi uchun 'set' qilamiz)
#     my_vocabulary = list(set(user_created + user_saved))
    
#     # XATOLIK: Agar so'zlar yetarli bo'lmasa (kamida 4 ta kerak)
#     if len(my_vocabulary) < 4:
#         return render(request, 'vocabulary/games_menu.html', {
#             'error': "Test o'ynash uchun lug'atingizda kamida 4 ta so'z bo'lishi kerak! Iltimos, so'z qo'shing yoki boshqa so'zlarni saqlang."
#         })
        
#     # To'g'ri javobni tanlaymiz
#     correct_word = random.choice(my_vocabulary)
    
#     # Noto'g'ri variantlarni tanlaymiz (to'g'ri javobdan boshqa 3 ta so'z)
#     wrong_words = random.sample([w for w in my_vocabulary if w != correct_word], 3)
    
#     # Variantlarni aralashtiramiz
#     variants = wrong_words + [correct_word]
#     random.shuffle(variants)
    
#     context = {
#         'question': correct_word,
#         'variants': variants,
#         'stats': stats
#     }
#     return render(request, 'vocabulary/test_play.html', context)

# # 5. NATIJA SAHIFASI
# # vocabulary/views.py ichida

# # vocabulary/views.py ichida

# @login_required
# def test_result(request):
#     stats = request.session.get('test_stats')
#     if not stats:
#         return redirect('games_menu')
    
#     saved_status = False # Natija saqlandimi yoki yo'q
#     message = "" # Foydalanuvchiga xabar
    
#     if stats['total_questions'] > 0:
#         profile = request.user.profile
#         today = timezone.now().date()
        
#         # Sana o'zgargan bo'lsa reset
#         if profile.last_game_date != today:
#             profile.daily_test_count = 0
#             profile.daily_match_count = 0
#             profile.daily_write_count = 0
#             profile.last_game_date = today
#             profile.save()

#         # --- YANGI MANTIQ: 60% VA MINIMUM 10 TA SAVOL ---
#         accuracy = (stats['correct'] / stats['total_questions']) * 100
        
#         # 1-SHART: Savollar soni kamida 10 ta bo'lishi kerak
#         if stats['total_questions'] < 10:
#              message = "Ball olish uchun kamida 10 ta savol yechish kerak!"
        
#         # 2-SHART: Aniqlik 60% dan baland bo'lishi kerak
#         elif accuracy < 60:
#              message = f"Natija past ({int(accuracy)}%). Ball olish uchun 60% kerak."
             
#         # 3-SHART: Kunlik limit (3 ta) to'lmagan bo'lishi kerak
#         elif profile.daily_test_count >= 3:
#              message = "Bugungi Test limiti (3/3) to'lgan. Boshqa o'yinlarni o'ynang!"
             
#         # HAMMASI ZO'R BO'LSA:
#         else:
#             profile.daily_test_count += 1
#             profile.save()
#             saved_status = True
#             message = "Ajoyib! Kunlik maqsadga +1 ball qo'shildi."
            
#             # Statistikaga 'saved' flagini qo'shamiz
#             stats['saved'] = True

#     request.session.pop('test_stats', None)
    
#     context = {
#         'stats': stats,
#         'message': message, # Xabarni shablonga yuboramiz
#         'accuracy': int((stats['correct'] / stats['total_questions']) * 100) if stats['total_questions'] > 0 else 0
#     }
#     return render(request, 'vocabulary/test_result.html', context)


# # vocabulary/views.py ichida

# @login_required
# def match_play(request):
#     # 1. So'zlarni yig'amiz (Xuddi Test o'yinidagi kabi)
#     user_created = list(Word.objects.filter(author=request.user))
#     user_saved = list(request.user.saved_words.all())
#     my_vocabulary = list(set(user_created + user_saved))

#     # Agar kam bo'lsa, bazadan olamiz (B Plan)
#     if len(my_vocabulary) < 5:
#         my_vocabulary = list(Word.objects.all())
    
#     # Agar baribir 5 taga yetmasa -> Xato
#     if len(my_vocabulary) < 5:
#         return render(request, 'vocabulary/games_menu.html', {
#             'error': "Matching o'ynash uchun kamida 5 ta so'z kerak!"
#         })

#     # 2. 5 ta tasodifiy so'z tanlaymiz
#     selected_words = random.sample(my_vocabulary, 5)

#     # 3. Kartalarni tayyorlaymiz (Jami 10 ta: 5 ta JP, 5 ta UZ)
#     cards = []
#     for word in selected_words:
#         # Yaponcha karta
#         cards.append({
#             'id': word.id,        # ID bir xil bo'ladi (moslashtirish uchun)
#             'text': word.japanese_word,
#             'type': 'jp'
#         })
#         # O'zbekcha karta
#         cards.append({
#             'id': word.id,
#             'text': word.meaning,
#             'type': 'uz'
#         })

#     # 4. Kartalarni yaxshilab aralashtiramiz
#     random.shuffle(cards)

#     return render(request, 'vocabulary/match_play.html', {'cards': cards})

# @login_required
# def match_result(request):
#     # Bu yerga faqat o'yinni yutganda keladi (JS yuboradi)
#     profile = request.user.profile
#     today = timezone.now().date()
    
#     # Kun yangilangan bo'lsa reset
#     if profile.last_game_date != today:
#         profile.daily_test_count = 0
#         profile.daily_match_count = 0
#         profile.daily_write_count = 0
#         profile.last_game_date = today
#         profile.save()
        
#     saved = False
#     message = ""
    
#     # Limitni tekshiramiz (3 ta)
#     if profile.daily_match_count < 3:
#         profile.daily_match_count += 1
#         profile.save()
#         saved = True
#         message = "Barakalla! +1 Ball qo'shildi."
#     else:
#         message = "Bugungi Matching limiti to'lgan (3/3)."
        
#     return render(request, 'vocabulary/match_result.html', {
#         'saved': saved,
#         'message': message,
#         'count': profile.daily_match_count
#     })








































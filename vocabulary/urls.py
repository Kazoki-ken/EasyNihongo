# vocabulary/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # 1. Asosiy Menyu (Hub) - Saytga kirganda birinchi chiqadigan sahifa
    path('', views.home, name='home'), 
    
    # 2. Darslik Lug'ati (Hamma so'zlar)
    path('dictionary/', views.dashboard, name='dashboard'), 
    
    # 3. Shaxsiy Lug'at va Profil
    path('my-vocabulary/', views.my_vocabulary, name='my_vocabulary'),
    path('profile/', views.profile_view, name='profile'),
    path('leaderboard/', views.leaderboard, name='leaderboard'), # <-- Reyting
    
    # 4. Ro'yxatdan o'tish va Admin qismi
    path('accounts/register/', views.register_view, name='register'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    
    # 5. Funksiyalar (Saqlash va O'chirish)
    path('toggle_save/<int:word_id>/', views.toggle_save, name='toggle_save'),
    path('delete-word/<int:word_id>/', views.delete_word, name='delete_word'),
    path('add-word/', views.add_word, name='add_word'),
    path('categories/', views.categories_view, name='categories'),
    path('categories/<str:topic_name>/', views.topic_words, name='topic_words'),
    path('books/<int:book_id>/', views.book_details_view, name='book_details'),
    path('books/save/<int:book_id>/', views.toggle_book_save, name='toggle_book_save'),
    # vocabulary/urls.py ga qo'shing
    path('save_all_topic/<str:topic_name>/', views.save_all_topic_words, name='save_all_topic_words'),
    path('quiz/', views.quiz_home, name='quiz_home'),
    path('games/', views.games_menu, name='games_menu'),      # 1. O'yinlar menyusi
    path('games/test/setup/', views.test_setup, name='test_setup'), # 2. Testni sozlash (Limit tanlash)
    path('games/test/start/', views.test_start, name='test_start'), # 3. Testni boshlash (Session tozalash)
    path('games/test/play/', views.test_play, name='test_play'),    # 4. O'yin jarayoni
    path('games/test/result/', views.test_result, name='test_result'), # 5. Natija
    # ... boshqa o'yinlar ...
    path('games/match/play/', views.match_play, name='match_play'),       # O'yin jarayoni
    path('games/match/result/', views.match_result, name='match_result'), # Natija
    path('match/setup/', views.match_setup, name='match_setup'),

# ... Match o'yini ...
    path('games/write/setup/', views.write_setup, name='write_setup'),    # Sozlash
    path('games/write/start/', views.write_start, name='write_start'),    # Boshlash
    path('games/write/play/', views.write_play, name='write_play'),       # O'yin jarayoni
    path('games/write/result/', views.write_result, name='write_result'), # Natija
    path('upload-words/', views.upload_words, name='upload_words'),
    path('upload-book-words/', views.upload_book_words, name='upload_book_words'),
]
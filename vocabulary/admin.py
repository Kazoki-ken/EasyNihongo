from django.contrib import admin
from .models import Word, Topic, Profile

# 1. Topic va Profile ni oddiy ro'yxatdan o'tkazish
# (Bularni faqat bir marta yozish kerak)
try:
    admin.site.register(Topic)
except admin.sites.AlreadyRegistered:
    pass

try:
    admin.site.register(Profile)
except admin.sites.AlreadyRegistered:
    pass

# 2. Word modeli uchun maxsus sozlamalar
# Agar Word oldin ro'yxatdan o'tgan bo'lsa, uni avval chiqarib tashlaymiz
if admin.site.is_registered(Word):
    admin.site.unregister(Word)

@admin.register(Word)
class WordAdmin(admin.ModelAdmin):
    list_display = ('japanese_word', 'meaning', 'get_topics') # Jadvalda ko'rinishi
    search_fields = ('japanese_word', 'meaning')
    filter_horizontal = ('topics',) # ManyToMany tanlash oynasi

    def get_topics(self, obj):
        return ", ".join([t.name for t in obj.topics.all()])
    
    get_topics.short_description = 'Topics'








# # vocabulary/admin.py
# from django.contrib import admin
# from .models import Word, Profile

# @admin.register(Word)
# class WordAdmin(admin.ModelAdmin):
#     # 'created_by' o'rniga 'author' va yangi 'topic' maydonini qo'shdik
#     list_display = ('japanese_word', 'hiragana', 'meaning', 'author', 'topic', 'created_at')
    
#     # Filtrlash endi muallif va mavzu bo'yicha bo'ladi
#     list_filter = ('author', 'topic', 'created_at')
    
#     # Qidiruv maydonlari
#     search_fields = ('japanese_word', 'hiragana', 'meaning')

# # Profile modelini ham admin panelda ko'radigan qilamiz
# admin.site.register(Profile)


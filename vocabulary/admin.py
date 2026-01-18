from django.contrib import admin
from .models import Word, Topic, Profile, Book, WeeklyStats, UserWordProgress, SiteConfiguration

# 0. SITE CONFIGURATION
@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'gemini_api_key')

    # Prevent adding more than one instance
    def has_add_permission(self, request):
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)

# 1. BOOK (Yangi)
@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_at', 'get_topics_count')
    search_fields = ('title', 'description')

    def get_topics_count(self, obj):
        return obj.topics.count()
    get_topics_count.short_description = "Mavzular soni"

# 2. TOPIC
# Oldingi oddiy register(Topic) ni o'chirib, custom admin qilamiz
# Agar oldin register qilingan bo'lsa, unregister qilish shart emas, chunki @admin.register ustiga yozadi,
# LEKIN kodda "try...except AlreadyRegistered" bor edi. Biz uni tozalamiz.

if admin.site.is_registered(Topic):
    admin.site.unregister(Topic)

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'book')
    list_filter = ('book',)
    search_fields = ('name',)

# 3. PROFILE
if admin.site.is_registered(Profile):
    admin.site.unregister(Profile)

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'streak', 'coins', 'level_display')
    search_fields = ('user__username',)

    def level_display(self, obj):
        # Bu yerda level yo'q, lekin kerak bo'lsa qo'shish mumkin
        return "N/A"

# 4. WORD
if admin.site.is_registered(Word):
    admin.site.unregister(Word)

@admin.register(Word)
class WordAdmin(admin.ModelAdmin):
    list_display = ('japanese_word', 'meaning', 'author', 'get_topics')
    search_fields = ('japanese_word', 'meaning')
    list_filter = ('topics', 'author')
    filter_horizontal = ('topics',)

    def get_topics(self, obj):
        return ", ".join([t.name for t in obj.topics.all()])
    get_topics.short_description = 'Topics'

# 5. STATISTIKA (Ixtiyoriy, lekin foydali)
@admin.register(WeeklyStats)
class WeeklyStatsAdmin(admin.ModelAdmin):
    list_display = ('user', 'start_date', 'words_learned', 'games_played', 'coins_earned')
    list_filter = ('start_date', 'is_collected')

@admin.register(UserWordProgress)
class UserWordProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'word', 'level', 'xp', 'next_review_date')
    search_fields = ('user__username', 'word__japanese_word')
    list_filter = ('level', 'next_review_date')

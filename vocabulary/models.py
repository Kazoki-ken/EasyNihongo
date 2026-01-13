from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

# 0. KITOBLAR MODELI (Yangi)
class Book(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    # Rasm uchun ImageField ishlatish mumkin, lekin hozircha oddiy saqlaymiz yoki icon
    # image = models.ImageField(upload_to='books/', blank=True, null=True)
    saves = models.ManyToManyField(User, related_name='saved_books', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

# 1. MAVZULAR MODELI
class Topic(models.Model):
    name = models.CharField(max_length=100)
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='topics', null=True, blank=True)
    # Agar book=None bo'lsa -> Asosiy lug'at mavzusi

    def __str__(self):
        if self.book:
            return f"{self.book.title} - {self.name}"
        return self.name


# 1. SO'ZLAR MODELI
class Word(models.Model):
    # Bitta so'z ko'p mavzuga tegishli bo'lishi mumkin
    topics = models.ManyToManyField(Topic, related_name='words', blank=True)
    
    japanese_word = models.CharField(max_length=100)
    hiragana = models.CharField(max_length=100, blank=True, null=True)
    meaning = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_words', null=True, blank=True)
    saves = models.ManyToManyField(User, related_name='saved_words', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.japanese_word} ({self.meaning})"
    
    class Meta:
        verbose_name_plural = "Words"

class Profile(models.Model):
    LEAGUE_CHOICES = [
        ('Bronze', 'Bronze'),
        ('Silver', 'Silver'),
        ('Gold', 'Gold'),
        ('Platinum', 'Platinum'),
        ('Diamond', 'Diamond'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    
    streak = models.IntegerField(default=0)
    last_login_date = models.DateField(null=True, blank=True)
    tree_state = models.IntegerField(default=1)
    
    # Har bir o'yin uchun alohida hisoblagich (Maksimum 3 tadan)
    daily_test_count = models.IntegerField(default=0)
    daily_match_count = models.IntegerField(default=0)
    daily_write_count = models.IntegerField(default=0)
    last_game_date = models.DateField(null=True, blank=True)

    coins = models.IntegerField(default=0)
    league = models.CharField(max_length=20, choices=LEAGUE_CHOICES, default='Bronze')

    # Jami kunlik progressni hisoblaydigan property (3+3+3 = 9)
    @property
    def total_daily_progress(self):
        return self.daily_test_count + self.daily_match_count + self.daily_write_count

    def __str__(self):
        return f"{self.user.username} profili ({self.league})"

# 2. HAFTALIK STATISTIKA MODELI (Yangi)
class WeeklyStats(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='weekly_stats')
    start_date = models.DateField() # Haftaning birinchi kuni (Dushanba)
    end_date = models.DateField()   # Haftaning oxirgi kuni (Yakshanba)

    words_learned = models.IntegerField(default=0) # Yangi qo'shilgan/saqlangan so'zlar
    games_played = models.IntegerField(default=0)  # O'ynalgan o'yinlar soni
    correct_answers = models.IntegerField(default=0) # To'g'ri javoblar
    total_questions = models.IntegerField(default=0) # Jami savollar (Aniqlikni hisoblash uchun)

    coins_earned = models.IntegerField(default=0) # Haftalik yig'ilgan tangalar
    xp_earned = models.IntegerField(default=0)    # Haftalik yig'ilgan XP

    is_collected = models.BooleanField(default=False) # Balansga o'tkazilganligi

    class Meta:
        unique_together = ('user', 'start_date') # Bir hafta uchun bitta statistika

    @property
    def accuracy(self):
        if self.total_questions > 0:
            return int((self.correct_answers / self.total_questions) * 100)
        return 0

    def __str__(self):
        return f"{self.user.username} - {self.start_date} haftasi"

# 3. AQLLI TAKRORLASH MODELI (Spaced Repetition)
class UserWordProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='word_progress')
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name='progress')

    xp = models.IntegerField(default=0) # 0-4 gacha
    level = models.IntegerField(default=1) # 1=Yangi, 2=Oson, 3=Yaxshi, 4=Zo'r, 5=Master
    next_review_date = models.DateField(default=timezone.now)

    class Meta:
        unique_together = ('user', 'word')

    def __str__(self):
        return f"{self.user.username} - {self.word.japanese_word} (Lvl: {self.level})"

# 5. LIGA LOGI (Yangi - Qaysi hafta hisob-kitob qilinganini bilish uchun)
class LeagueLog(models.Model):
    week_start_date = models.DateField(unique=True) # Qaysi haftaning Natijasi hisoblandi (Masalan: o'tgan dushanba)
    processed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"League Update for: {self.week_start_date}"

# 4. SIGNALLAR (Profilni avtomatik yaratish)
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    # Ba'zan profil bo'lmasa xato bermasligi uchun try/except
    try:
        instance.profile.save()
    except Profile.DoesNotExist:
        Profile.objects.create(user=instance)

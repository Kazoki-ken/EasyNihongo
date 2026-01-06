from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

# 1. MAVZULAR MODELI (Yangi)
class Topic(models.Model):
    name = models.CharField(max_length=100)
    # description = models.TextField(blank=True, null=True) # Kerak bo'lsa qo'shasiz

    def __str__(self):
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
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    
    streak = models.IntegerField(default=0)
    last_login_date = models.DateField(null=True, blank=True)
    tree_state = models.IntegerField(default=1)
    
    # Har bir o'yin uchun alohida hisoblagich (Maksimum 3 tadan)
    daily_test_count = models.IntegerField(default=0)
    daily_match_count = models.IntegerField(default=0)
    daily_write_count = models.IntegerField(default=0)
    last_game_date = models.DateField(null=True, blank=True)

    # Jami kunlik progressni hisoblaydigan property (3+3+3 = 9)
    @property
    def total_daily_progress(self):
        return self.daily_test_count + self.daily_match_count + self.daily_write_count

    def __str__(self):
        return f"{self.user.username} profili"

# 3. SIGNALLAR (Profilni avtomatik yaratish)
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
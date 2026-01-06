from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Word

# 1. FOYDALANUVCHI RO'YXATDAN O'TISH FORMASI
class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['username', 'email'] 
        # Parol maydonlarini UserCreationForm o'zi avtomatik qo'shadi

# 2. SO'Z QO'SHISH FORMASI (Oddiy foydalanuvchi uchun)
class WordForm(forms.ModelForm):
    class Meta:
        model = Word
        # 'topics' olib tashlandi, faqat shu 3 tasi qoldi
        fields = ['japanese_word', 'hiragana', 'meaning']
        
        widgets = {
            'japanese_word': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': "Yaponcha so'z"
            }),
            'hiragana': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': "Hiragana/Katakana"
            }),
            'meaning': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3, 
                'placeholder': "Ma'nosi"
            }),
        }
    # class Meta:
    #     model = Word
    #     # 'topic' o'rniga 'topics' yozamiz
    #     fields = ['japanese_word', 'hiragana', 'meaning', 'topics']
        
    #     widgets = {
    #         'japanese_word': forms.TextInput(attrs={
    #             'class': 'form-control', 
    #             'placeholder': "Yaponcha so'z"
    #         }),
    #         'hiragana': forms.TextInput(attrs={
    #             'class': 'form-control', 
    #             'placeholder': "Hiragana/Katakana"
    #         }),
    #         'meaning': forms.Textarea(attrs={
    #             'class': 'form-control', 
    #             'rows': 3, 
    #             'placeholder': "Ma'nosi"
    #         }),
    #     }

# class WordForm(forms.ModelForm):
#     class Meta:
#         model = Word
#         # Foydalanuvchi to'ldirishi kerak bo'lgan ustunlar
#         fields = ['topic', 'japanese_word', 'hiragana', 'meaning']
        
#         # Mobil qurilmalarda chiroyli chiqishi uchun Bootstrap klasslarini beramiz
#         widgets = {
#             'topic': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Mavzu (masalan: 1-dars)'}),
#             'japanese_word': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Yaponcha so\'z'}),
#             'hiragana': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Hiragana/Katakana'}),
#             'meaning': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Ma\'nosi', 'rows': 3}),
#         }

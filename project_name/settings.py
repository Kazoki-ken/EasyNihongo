# settings.py
# project_name/settings.py faylida toping va yangilang




###########################################################

# project_name/settings.py faylining eng boshiga qo'shing (agar mavjud bo'lmasa):

from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent



###########################################################


###########################################################
# project_name/settings.py (Yuqori qismda joylashgan)
SECRET_KEY = 'django-insecure-33g_t$d#n!2^153z@^=98x5g8&_qj#15c@9^6w8&p0*j3h4s'
###########################################################


###########################################################

# project_name/settings.py faylida toping va quyidagicha to'liq almashtiring:

# ALLOWED_HOSTS = [
#     '127.0.0.1',
#     'localhost',
#     # Agar biron-bir element qo'shilsa, oxiriga vergul qo'ying
# ]

ALLOWED_HOSTS = ['*']

# Shuningdek, DEBUG holatini tekshiring. 
# Agar u False bo'lsa, 'DEBUG = True' qilib o'zgartiring.
DEBUG = True


###########################################################


# settings.py faylida:

# ESKI HOLAT (odatda shunday turadi):
TIME_ZONE = 'UTC'

# YANGI HOLAT (O'zbekiston vaqtiga o'tkazish):
TIME_ZONE = 'Asia/Tashkent'


###########################################################

# project_name/settings.py

INSTALLED_APPS = [
 # Standart Django Ilovalari
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Bizning Ilova
    'vocabulary', # <- Bu qatordan keyin vergul bo'lmasligi ham mumkin, lekin yuqoridagilarda bo'lishi shart
]

###########################################################





###########################################################

# project_name/settings.py faylida toping va quyidagicha to'liq almashtiring:

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

###########################################################





###########################################################

# project_name/settings.py faylida toping va quyidagicha to'liq almashtiring:

MIDDLEWARE = [
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Bu qatorni qo'shing (agar mavjud bo'lmasa)
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware', # <- 1-chi talab
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware', # <- 2-chi talab
    'django.contrib.messages.middleware.MessageMiddleware', # <- 3-chi talab
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

###########################################################





###########################################################

# project_name/settings.py faylida toping va quyidagicha to'liq almashtiring:

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Yuqoridagi kodni qo'yishdan oldin, fayl boshida "BASE_DIR" ni o'rnatish kerak.
# Agar mavjud bo'lmasa, uni qo'shing (o'rnini almashtirmang):
from pathlib import Path
# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

###########################################################


###########################################################
# project_name/settings.py
# Bu taxminan 120-130-qatorlarda joylashgan bo'lishi mumkin.
ROOT_URLCONF = 'project_name.urls'
###########################################################


###########################################################

# project_name/settings.py faylining oxiriga quyidagilarni qo'shing

# Xabarlar uchun storage sozlamasi (muvaffaqiyat, xato xabarlari uchun)
# Bu settings.py faylida allaqachon bo'lishi mumkin, shunchaki tekshiring.
MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

# Foydalanuvchi muvaffaqiyatli kirgandan so'ng qaysi sahifaga o'tishi
LOGIN_REDIRECT_URL = 'all_words' # (Keyin yaratamiz)

# Foydalanuvchi kirish sahifasi URL manzili
LOGIN_URL = 'login' # (Keyin yaratamiz)

# Foydalanuvchi chiqqandan so'ng qaysi sahifaga o'tishi
LOGOUT_REDIRECT_URL = 'all_words'

###########################################################


###########################################################

# project_name/settings.py faylining oxiriga qo'shing:

# Statik fayllarni boshqarish uchun zarur
STATIC_URL = 'static/'

###########################################################


###########################################################

# settings.py faylining eng oxiriga qo'shing

# Foydalanuvchi muvaffaqiyatli kirgandan keyin yo'naltiriladigan manzil
LOGIN_REDIRECT_URL = '/'  # Dashboard (asosiy sahifa) ga yo'naltiramiz

# Foydalanuvchi tizimdan chiqqandan keyin yo'naltiriladigan manzil
LOGOUT_REDIRECT_URL = '/' # Dashboard (asosiy sahifa) ga yo'naltiramiz

###########################################################



# Ngrok orqali kirganda xatolik bermasligi uchun:
CSRF_TRUSTED_ORIGINS = [
    'https://*.ngrok-free.app',
    'https://*.ngrok-free.dev',
]



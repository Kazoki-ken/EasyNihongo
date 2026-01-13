import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_name.settings')
django.setup()

from django.contrib.auth.models import User
from vocabulary.models import Profile, Badge, UserBadge

import time
unique_user = f"badge_user_v2_{int(time.time())}"
password = 'password123'

if not User.objects.filter(username=unique_user).exists():
    user = User.objects.create_user(username=unique_user, password=password)
    # Profile should be created by signal, but let's ensure
    if not hasattr(user, 'profile'):
        Profile.objects.create(user=user)
    print(f"User {unique_user} created.")
else:
    print(f"User {unique_user} already exists.")

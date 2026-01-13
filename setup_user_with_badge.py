import os
import django
import time

# 1. Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_name.settings')
django.setup()

# 2. Models
from django.contrib.auth.models import User
from vocabulary.models import Badge, UserBadge, Word

# 3. Create User programmatically
unique_user = f"badge_manual_{int(time.time())}"
password = "password123"

if not User.objects.filter(username=unique_user).exists():
    user = User.objects.create_user(username=unique_user, password=password)
    # Give user a word to earn badge
    Word.objects.create(
        japanese_word="Inu",
        meaning="Dog",
        author=user
    )

    # Assign Badge manually (simulation of check_badges)
    # Normally check_badges() does this, but for verify script speed/stability:
    badge = Badge.objects.get(name="Ilk Qadam")
    UserBadge.objects.create(user=user, badge=badge)

    print(f"CREATED:{unique_user}:{password}")
else:
    print(f"EXISTS:{unique_user}:{password}")

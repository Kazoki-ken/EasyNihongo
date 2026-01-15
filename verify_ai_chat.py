import os
import django
from django.test import Client

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_name.settings')
django.setup()

from django.contrib.auth.models import User

def verify_ai_chat():
    # Create or get a test user
    user, created = User.objects.get_or_create(username='testverifyuser')
    if created:
        user.set_password('password123')
        user.save()

    client = Client()
    client.force_login(user)

    # Check if the page loads correctly (200 OK)
    response = client.get('/ai-chat/')
    if response.status_code == 200:
        print("SUCCESS: /ai-chat/ page loaded successfully.")
    else:
        print(f"FAILURE: /ai-chat/ returned status code {response.status_code}")

if __name__ == '__main__':
    verify_ai_chat()

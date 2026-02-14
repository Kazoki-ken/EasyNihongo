import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_name.settings')
django.setup()

from django.contrib.auth.models import User
from vocabulary.models import Topic, Book, Word

def setup_data():
    # Create user
    user, created = User.objects.get_or_create(username='testuser')
    if created:
        user.set_password('password123')
        user.save()
        print("User 'testuser' created.")
    else:
        print("User 'testuser' already exists.")

    # Create dummy data
    if not Topic.objects.exists():
        t1 = Topic.objects.create(name="Salomlashish")
        t2 = Topic.objects.create(name="Oila va Do'stlar")
        t3 = Topic.objects.create(name="Sayohat")
        print("Topics created.")
    else:
        print("Topics already exist.")

    if not Book.objects.exists():
        b1 = Book.objects.create(title="Minna no Nihongo 1")
        b2 = Book.objects.create(title="Genki I")
        print("Books created.")
    else:
        print("Books already exist.")

if __name__ == "__main__":
    setup_data()

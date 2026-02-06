import os
import sys
import django
from playwright.sync_api import sync_playwright, expect

# Setup Django Environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_name.settings')
django.setup()

from django.contrib.auth.models import User
from vocabulary.models import Profile

def run():
    print("Setting up user...")
    username = 'pw_user'
    password = 'password123'
    try:
        User.objects.get(username=username).delete()
    except User.DoesNotExist:
        pass

    user = User.objects.create_user(username=username, password=password)
    # Ensure profile exists
    if not hasattr(user, 'profile'):
        Profile.objects.create(user=user)

    print("Starting Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 800}) # Desktop view
        page = context.new_page()

        # 1. Login
        print("Navigating to login...")
        page.goto('http://localhost:8001/accounts/login/')

        # Check if we are already logged in (unlikely but good to know)
        if "/accounts/login/" in page.url:
            page.fill('input[name="username"]', username)
            page.fill('input[name="password"]', password)
            # Find submit button - usually inside form
            page.click('button[type="submit"]')
            print("Login submitted...")

        # 2. Wait for Home
        page.wait_for_url('http://localhost:8001/')
        print("Reached Home Page.")

        # 3. Verify Elements
        # Check for Desktop Grid
        expect(page.locator('.desktop-grid')).to_be_visible()
        print("Desktop Grid visible.")

        # Check for Home Header
        expect(page.locator('.app-header')).to_be_visible()
        print("Home Header visible.")

        # Check for Bottom Nav (inherited from base)
        expect(page.locator('.bottom-nav-fixed')).to_be_visible()
        print("Bottom Nav visible.")

        # 4. Screenshot
        output_path = 'verification/home_frontend.png'
        page.screenshot(path=output_path, full_page=True)
        print(f"Screenshot saved to {output_path}")

        browser.close()

if __name__ == '__main__':
    run()

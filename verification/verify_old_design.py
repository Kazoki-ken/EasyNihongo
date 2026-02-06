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
    username = 'pw_user_old_design'
    password = 'password123'
    try:
        User.objects.get(username=username).delete()
    except User.DoesNotExist:
        pass

    user = User.objects.create_user(username=username, password=password)
    if not hasattr(user, 'profile'):
        Profile.objects.create(user=user)

    print("Starting Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 414, 'height': 896}) # Mobile view (like iPhone)
        page = context.new_page()

        # 1. Login
        print("Navigating to login...")
        page.goto('http://localhost:8003/accounts/login/')

        # Check if we are already logged in
        if "/accounts/login/" in page.url:
            page.fill('input[name="username"]', username)
            page.fill('input[name="password"]', password)
            page.click('button[type="submit"]')
            print("Login submitted...")

        # 2. Wait for Home
        page.wait_for_url('http://localhost:8003/')
        print("Reached Home Page.")

        # 3. Verify Elements (Old Design)

        # Check for ANY tree image class to confirm presence of the tree component
        # The tree logic uses classes: tree-normal, tree-withered, tree-dead
        try:
            expect(page.locator('.tree-normal').or_(page.locator('.tree-dead')).or_(page.locator('.tree-withered'))).to_be_visible()
            print("Sakura Tree component visible.")
        except:
            print("WARNING: Tree component not found. Check screenshot.")

        # Ensure Bottom Nav is visible (Included)
        expect(page.locator('.bottom-nav-fixed')).to_be_visible()
        print("Bottom Nav visible.")

        # Check for the Base Header which I included in the standalone file
        expect(page.locator('.bi-brightness-alt-low-fill')).to_be_visible()
        print("Base Header visible (Standalone).")

        # 4. Screenshot
        output_path = 'verification/home_old_design_fixed_nav.png'
        page.screenshot(path=output_path, full_page=True)
        print(f"Screenshot saved to {output_path}")

        browser.close()

if __name__ == '__main__':
    run()

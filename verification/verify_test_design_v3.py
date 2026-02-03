import os
import sys
from playwright.sync_api import sync_playwright

# Add repo root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from django.contrib.auth import get_user_model
from django.conf import settings
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_name.settings')
django.setup()

def verify_design_update():
    User = get_user_model()
    # Ensure a test user exists
    if not User.objects.filter(username='testuser').exists():
        User.objects.create_user('testuser', 'test@example.com', 'password')
        print("Created test user")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Mobile view context
        context = browser.new_context(
            viewport={'width': 375, 'height': 812},
            user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
        )
        page = context.new_page()

        # Login
        page.goto('http://127.0.0.1:8000/accounts/login/')
        page.fill('input[name="username"]', 'testuser')
        page.fill('input[name="password"]', 'password')
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle')

        # Go to Test Design
        print("Navigating to /test-design/")
        page.goto('http://127.0.0.1:8000/test-design/')

        # Verify Translations
        stats_labels = ["Lug'at", "Yozish", "O'qish", "Tinglash", "Grammatika"]
        for label in stats_labels:
            if page.get_by_text(label).is_visible():
                print(f"Verified label: {label}")
            else:
                print(f"FAILED to find label: {label}")

        # Verify House Icon
        if page.locator('.bi-house-door-fill').count() > 0:
            print("Verified House Icon (bi-house-door-fill) exists")
        else:
            print("FAILED to find House Icon")

        # Verify AI Card Color (rough check via class or CSS, but visual is best)
        # We'll take a screenshot for manual/visual verification
        screenshot_path = "test_design_v3.png"
        page.screenshot(path=screenshot_path)
        print(f"Screenshot saved to {screenshot_path}")

        browser.close()

if __name__ == "__main__":
    verify_design_update()

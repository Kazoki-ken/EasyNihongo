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

def verify_responsive_design():
    User = get_user_model()
    # Ensure a test user exists
    if not User.objects.filter(username='testuser').exists():
        User.objects.create_user('testuser', 'test@example.com', 'password')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # 1. Desktop Verification
        print("Verifying Desktop Layout...")
        context_desktop = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page_desktop = context_desktop.new_page()

        # Login
        page_desktop.goto('http://127.0.0.1:8000/accounts/login/')
        page_desktop.fill('input[name="username"]', 'testuser')
        page_desktop.fill('input[name="password"]', 'password')
        page_desktop.click('button[type="submit"]')
        page_desktop.wait_for_load_state('networkidle')

        page_desktop.goto('http://127.0.0.1:8000/test-design/')

        # Check container width (should be max 600px)
        container_box = page_desktop.locator('.app-container').bounding_box()
        if container_box['width'] <= 600:
            print(f"PASS: Desktop container width is {container_box['width']}px (<= 600px)")
        else:
            print(f"FAIL: Desktop container width is {container_box['width']}px")

        # Check centering (approximate)
        viewport_width = 1920
        expected_x = (viewport_width - 600) / 2
        # Allow some margin of error
        if abs(container_box['x'] - expected_x) < 50:
             print(f"PASS: App container appears centered (x: {container_box['x']})")
        else:
             print(f"WARNING: App container centering check might be off (x: {container_box['x']}, expected ~{expected_x})")

        # 2. Mobile Verification
        print("\nVerifying Mobile Layout...")
        context_mobile = browser.new_context(
            viewport={'width': 375, 'height': 812},
            user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
        )
        page_mobile = context_mobile.new_page()
        # Cookie reuse or re-login needed? usually distinct context needs login
        page_mobile.goto('http://127.0.0.1:8000/accounts/login/')
        page_mobile.fill('input[name="username"]', 'testuser')
        page_mobile.fill('input[name="password"]', 'password')
        page_mobile.click('button[type="submit"]')
        page_mobile.wait_for_load_state('networkidle')

        page_mobile.goto('http://127.0.0.1:8000/test-design/')

        # Check Header Padding
        header = page_mobile.locator('.app-header')
        padding_top = header.evaluate("el => getComputedStyle(el).paddingTop")
        print(f"Mobile Header Padding-Top: {padding_top}")

        if padding_top == "45px":
            print("PASS: Mobile header has correct padding for status bar.")
        else:
             print(f"FAIL: Mobile header padding is {padding_top}, expected 45px.")

        browser.close()

if __name__ == "__main__":
    verify_responsive_design()

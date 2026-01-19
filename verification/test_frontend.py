import os
import time
from playwright.sync_api import sync_playwright

def verify_frontend():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Add permissions for microphone to avoid prompts blocking the UI (though we can't test audio in headless easily,
        # we can verify the UI structure and that no errors appear immediately)
        context = browser.new_context(permissions=['microphone'])
        page = context.new_page()

        # Login first
        page.goto("http://localhost:8000/accounts/login/")
        # Assuming a test user exists or we need to create one.
        # Let's check if we can create one via script or if we need to use existing.
        # Since I don't have credentials, I might need to create a superuser or user first.
        # But for now, let's assume I can register or use a script.

        # Actually, let's create a user in a separate script or just use the register page if needed.
        # Better: use python to create a user.

        # For this verification script, let's assume we are logged in.
        # Wait, I need to login.

        page.fill('input[name="username"]', 'testuser')
        page.fill('input[name="password"]', 'testpass123')
        page.click('button[type="submit"]')

        # Wait for navigation
        page.wait_for_load_state('networkidle')

        # Go to AI Chat Test page
        page.goto("http://localhost:8000/ai-chat-test/")

        # Check if the page loads and the "Sensei AI (Edge Audio)" header is visible
        header = page.locator("h1", has_text="Sensei AI (Edge Audio)")
        if header.is_visible():
            print("Header found.")
        else:
            print("Header NOT found.")

        # Check if the warning is hidden (since we are on localhost)
        warning = page.locator("#https-warning")
        if not warning.is_visible():
            print("HTTPS warning is correctly hidden on localhost.")

        # Take a screenshot
        page.screenshot(path="verification/ai_chat_v2_verification.png")
        print("Screenshot saved to verification/ai_chat_v2_verification.png")

        browser.close()

if __name__ == "__main__":
    verify_frontend()

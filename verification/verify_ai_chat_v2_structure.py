import os
import sys
from playwright.sync_api import sync_playwright, expect

def verify_ai_chat_v2_structure():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Login first (since it redirects to login)
        print("Logging in...")
        page.goto("http://127.0.0.1:8001/accounts/login/")
        page.fill("input[name='username']", "testverifyuser")
        page.fill("input[name='password']", "password123")
        page.click("button[type='submit']")

        # Wait for navigation. Based on logs, it redirects to /
        print("Waiting for redirect...")
        try:
             # Wait for ANY navigation or just sleep briefly, or check for success marker
             page.wait_for_load_state('networkidle')
        except Exception as e:
             print(f"Warning during login wait: {e}")

        # Navigate to the page
        print("Navigating to /ai-chat-test/...")
        try:
            page.goto("http://127.0.0.1:8001/ai-chat-test/")
        except Exception as e:
            print(f"Failed to load page: {e}")
            return

        # Check if the page title or header contains "Sensei AI"
        print("Checking page title/header...")
        expect(page.get_by_text("Sensei AI")).to_be_visible()

        # Check if the mic button exists
        print("Checking for Microphone button...")
        mic_btn = page.locator("#mic-btn")
        expect(mic_btn).to_be_visible()

        # Check for Settings button
        print("Checking for Settings button...")
        expect(page.locator("#settings-btn")).to_be_visible()

        # Take a screenshot to verify layout
        screenshot_path = "verification/ai_chat_v2_structure.png"
        page.screenshot(path=screenshot_path)
        print(f"Screenshot saved to {screenshot_path}")

        # Verify State initialization via Console Evaluation
        print("Verifying 'state' object has 'chatHistory'...")
        chat_history_exists = page.evaluate("() => typeof state !== 'undefined' && Array.isArray(state.chatHistory)")

        if chat_history_exists:
            print("SUCCESS: state.chatHistory exists.")
        else:
            print("FAILURE: state.chatHistory NOT found.")
            sys.exit(1)

        # Verify sendToGeminiText function structure (basic check)
        # We can't easily check the function body content via evaluate, but we can check existence
        print("Verifying 'sendToGeminiText' function exists...")
        func_exists = page.evaluate("() => typeof sendToGeminiText === 'function'")
        if func_exists:
            print("SUCCESS: sendToGeminiText function exists.")
        else:
            print("FAILURE: sendToGeminiText function NOT found.")
            sys.exit(1)

        browser.close()

if __name__ == "__main__":
    verify_ai_chat_v2_structure()

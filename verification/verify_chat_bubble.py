import os
import sys
from playwright.sync_api import sync_playwright, expect

def verify_chat_bubble_class():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Login first
        print("Logging in...")
        page.goto("http://127.0.0.1:8001/accounts/login/")
        page.fill("input[name='username']", "testverifyuser")
        page.fill("input[name='password']", "password123")
        page.click("button[type='submit']")

        # Wait for navigation
        print("Waiting for redirect...")
        try:
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

        # Simulate adding a user message by calling addMessage directly in browser context
        print("Simulating user message...")
        page.evaluate("addMessage('user', 'Testing Bubble Class')")

        # Verify that the added message has the 'chat-bubble' class
        print("Verifying .chat-bubble class existence...")
        # The bubble is inside the user message container.
        # User message container has 'flex-row-reverse'

        # Wait for the message to appear
        expect(page.get_by_text("Testing Bubble Class")).to_be_visible()

        # Find the element with class 'chat-bubble' containing the text
        bubble = page.locator(".chat-bubble").filter(has_text="Testing Bubble Class")

        if bubble.count() > 0:
             print("SUCCESS: Found element with class 'chat-bubble' and correct text.")
        else:
             print("FAILURE: Element with class 'chat-bubble' NOT found.")
             # Take debug screenshot
             page.screenshot(path="verification/debug_bubble_fail.png")
             sys.exit(1)

        # Take success screenshot
        screenshot_path = "verification/chat_bubble_verified.png"
        page.screenshot(path=screenshot_path)
        print(f"Screenshot saved to {screenshot_path}")

        browser.close()

if __name__ == "__main__":
    verify_chat_bubble_class()

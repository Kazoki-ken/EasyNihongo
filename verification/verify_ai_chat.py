
from playwright.sync_api import sync_playwright

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    # Login first
    page.goto("http://localhost:8000/accounts/login/")
    page.fill("input[name='username']", "testuser")
    page.fill("input[name='password']", "password123")
    page.click("button[type='submit']")

    # Wait for navigation
    page.wait_for_url("http://localhost:8000/")

    # Navigate to AI Chat
    page.goto("http://localhost:8000/ai-chat/")

    # Check if the page loaded
    page.wait_for_selector("#ai-chat-app")

    # Take a screenshot
    page.screenshot(path="verification/ai_chat_verification.png")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)

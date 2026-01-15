from playwright.sync_api import sync_playwright, expect
import os

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    # 1. Login
    page.goto("http://localhost:8000/accounts/login/")
    # Using the exact labels from the HTML
    page.get_by_label("Login").fill("testverifyuser")
    page.get_by_label("Parol").fill("password123")
    page.get_by_role("button", name="Kirish").click()

    # 2. Go to AI Chat
    page.goto("http://localhost:8000/ai-chat/")

    # 3. Verify Elements
    expect(page.locator(".chat-container")).to_be_visible()
    expect(page.get_by_text("Sensei AI")).to_be_visible()

    # Check for "Darsni Boshlash" inside the controls-area/status-text
    # Using text locator as it might not be a direct button label if inside <p> or similar
    expect(page.get_by_text("Darsni Boshlash")).to_be_visible()

    # 4. Check Console for Errors (Crucial for this task)
    page.on("console", lambda msg: print(f"CONSOLE: {msg.text}"))
    page.on("pageerror", lambda err: print(f"PAGE ERROR: {err}"))

    # 5. Screenshot
    if not os.path.exists("/home/jules/verification"):
        os.makedirs("/home/jules/verification")
    page.screenshot(path="/home/jules/verification/ai_chat_fix.png")

    browser.close()

if __name__ == "__main__":
    with sync_playwright() as playwright:
        run(playwright)

from playwright.sync_api import sync_playwright, expect
import os
import sys
import subprocess

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    # Create User
    result = subprocess.run(['python', 'setup_user_with_badge.py'], capture_output=True, text=True)
    output = result.stdout.strip()
    parts = output.split(':')
    username = parts[1]
    password = parts[2]

    print(f"Logging in with {username}")

    # 1. Login
    page.goto("http://localhost:8000/accounts/login/")
    page.wait_for_selector('input[name="username"]')
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_url("**/")

    # 2. Go to Profile
    page.goto("http://localhost:8000/profile/")
    page.wait_for_selector('.grid-btn-card')

    # 3. Verify UI Elements

    # "Yangi so'z" button in Grid
    # Use exact=True or selector to avoid ambiguity (small text vs button text)
    expect(page.get_by_text("Yangi so'z", exact=True).last).to_be_visible()

    # "Yutuqlar" section header
    expect(page.get_by_text("Yutuqlar")).to_be_visible()

    # "Ilk Qadam" badge
    expect(page.get_by_text("Ilk Qadam")).to_be_visible()
    # Check status (first because multiple badges might be unlocked if logic changes, but here 1 is unlocked)
    expect(page.get_by_text("Topdingiz!").first).to_be_visible()

    # Locked badge
    expect(page.get_by_text("Bilimdon")).to_be_visible()
    expect(page.get_by_text("Qulflangan").first).to_be_visible()

    # 4. Screenshot
    page.screenshot(path="verification/achievements_page.png", full_page=True)

    browser.close()

with sync_playwright() as playwright:
    run(playwright)

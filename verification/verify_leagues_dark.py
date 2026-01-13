from playwright.sync_api import sync_playwright, expect
import os

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    # 1. Login
    page.goto("http://localhost:8000/accounts/login/")
    page.wait_for_selector('input[name="username"]')
    page.fill('input[name="username"]', "testuser_league_v2")
    page.fill('input[name="password"]', "password123")
    page.click('button[type="submit"]')

    # Wait for login completion
    try:
        page.wait_for_url("**/", timeout=5000)
    except:
        if "login" in page.url:
             print("Still on login page")
             return

    # 2. Go to Leagues page
    page.goto("http://localhost:8000/leagues/")
    page.wait_for_selector('body')

    # 3. Enable Dark Mode via JS
    page.evaluate("document.body.classList.add('dark-mode')")

    # 4. Take Screenshot
    page.screenshot(path="verification/leagues_dark_mode.png", full_page=True)

    browser.close()

with sync_playwright() as playwright:
    run(playwright)

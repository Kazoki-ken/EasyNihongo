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

    # 2. Wait for navigation after login (increase timeout)
    try:
        page.wait_for_url("**/", timeout=5000) # Wait for redirect to home
    except:
        # If it fails, maybe it redirected but selector check failed.
        # Let's verify we are NOT on login page anymore
        if "login" in page.url:
             print("Still on login page")
             page.screenshot(path="verification/failed_login.png")
             return

    # 3. Go to Leagues page explicitly
    page.goto("http://localhost:8000/leagues/")

    # 4. Verify Elements
    # Wait for body to load
    page.wait_for_selector('body')

    # Check if we are seeing Bronze League
    expect(page.get_by_text("Bronze League")).to_be_visible()

    # 5. Take Screenshot
    page.screenshot(path="verification/leagues_page.png", full_page=True)

    browser.close()

with sync_playwright() as playwright:
    run(playwright)

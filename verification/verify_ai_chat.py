from playwright.sync_api import Page, expect, sync_playwright

def test_ai_chat_verification(page: Page):
    # Login as admin
    page.goto("http://127.0.0.1:8000/admin/login/")
    page.get_by_label("Username").fill("testadmin")
    page.get_by_label("Password").fill("password123")
    page.get_by_role("button", name="Log in").click()

    # Navigate to AI Chat
    page.goto("http://127.0.0.1:8000/ai-chat/")

    # Verify Page Loaded
    expect(page.get_by_text("EasyNihongo")).to_be_visible()
    expect(page.get_by_text("Live Japanese Tutor")).to_be_visible()

    # Verify pcmToWav function exists and works via console evaluation
    result = page.evaluate("""() => {
        try {
            if (typeof pcmToWav !== 'function') return 'Fail: pcmToWav not defined';

            // Create dummy PCM data (100 bytes of zeros)
            const pcmData = new ArrayBuffer(100);
            const wavData = pcmToWav(pcmData, 24000);

            // Basic checks on WAV header
            const view = new DataView(wavData);

            // Check 'RIFF'
            const riff = String.fromCharCode(view.getUint8(0), view.getUint8(1), view.getUint8(2), view.getUint8(3));
            if (riff !== 'RIFF') return 'Fail: No RIFF';

            // Check Sample Rate (offset 24)
            const sampleRate = view.getUint32(24, true);
            if (sampleRate !== 24000) return 'Fail: Wrong Sample Rate';

            // Check Data size (offset 40)
            const dataSize = view.getUint32(40, true);
            if (dataSize !== 100) return 'Fail: Wrong Data Size';

            return 'Success';
        } catch (e) {
            return 'Error: ' + e.message;
        }
    }""")

    if result != "Success":
        raise Exception(f"pcmToWav verification failed: {result}")

    print("pcmToWav verification successful!")

    # Screenshot
    page.screenshot(path="verification/ai_chat_verification.png")

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        try:
            test_ai_chat_verification(page)
        except Exception as e:
            print(f"Test failed: {e}")
            page.screenshot(path="verification/error.png")
        finally:
            browser.close()

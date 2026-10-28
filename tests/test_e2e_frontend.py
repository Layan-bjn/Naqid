import os
import sys
import time

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

def run_e2e_test():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()

        # 1. Load Homepage
        page.goto("http://localhost:8000/", wait_until="networkidle")
        assert "ناقد - وكيل التدقيق الذكي" in page.title()
        print("E2E: Homepage title verified.")

        # 2. Check Logo and Header
        header_text = page.locator(".logo-title").text_content()
        assert "ناقد" in header_text
        print("E2E: Logo and header verified.")

        # 3. Test DEMO mode with Checkbox Checked
        checkbox = page.locator("#demo-mode-checkbox")
        assert checkbox.is_visible()
        checkbox.check()
        print("E2E: Checked 'وضع العرض الاحتياطي (Demo)' checkbox.")

        demo_btn = page.locator("#demo-btn")
        assert demo_btn.is_visible()
        demo_btn.click()
        print("E2E: Clicked demo page button with demo mode checked.")

        # Wait for results
        page.wait_for_selector("#results-section:not(.hidden)", timeout=20000)
        mode_badge = page.locator("#audit-mode-badge").text_content()
        assert "نتيجة محفوظة" in mode_badge, f"Expected cached badge, got {mode_badge}"
        print(f"E2E: Demo Mode Badge verified: {mode_badge}")

        score_val = page.locator("#score-number").text_content()
        assert score_val.strip() == "42"
        print(f"E2E: Cached Demo Score verified: {score_val}/100")

        # 4. Test LIVE mode with Checkbox Unchecked
        checkbox.uncheck()
        print("E2E: Unchecked 'وضع العرض الاحتياطي (Demo)' for LIVE audit.")
        demo_btn.click()
        print("E2E: Clicked demo page button for LIVE audit.")

        # Wait for results
        page.wait_for_selector("#results-section:not(.hidden)", timeout=45000)
        live_mode_badge = page.locator("#audit-mode-badge").text_content()
        assert "فحص حي" in live_mode_badge, f"Expected live badge, got {live_mode_badge}"
        print(f"E2E: Live Mode Badge verified: {live_mode_badge}")

        # 5. Verify Issue Cards Rendered
        cards = page.locator(".issue-card").all()
        assert len(cards) > 0, "No issue cards rendered in live mode"
        print(f"E2E: Live issues rendered: {len(cards)} cards.")

        # 6. Test Collapsible Fix Code
        first_card = page.locator(".issue-card").first
        fix_details = first_card.locator("details").first
        fix_details.click()
        time.sleep(0.3)
        code_block = fix_details.locator(".code-block")
        assert code_block.is_visible()
        print("E2E: Suggested fix code block opened and visible.")

        # 7. Test Screenshots Tabs Switching
        mobile_tab = page.locator("button[data-tab='mobile-view']")
        mobile_tab.click()
        time.sleep(0.3)
        mobile_pane = page.locator("#mobile-view")
        assert "active" in (mobile_pane.get_attribute("class") or "")
        print("E2E: Screenshot tab switching to mobile verified.")

        browser.close()
        print("ALL E2E FRONTEND AND LIVE AUDIT TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_e2e_test()

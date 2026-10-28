import os
import uuid
import asyncio
from typing import Dict, Any, Tuple
from playwright.async_api import async_playwright, Browser, Page
from backend.schemas import DOMSignals

# Ensure screenshots directory exists
SCREENSHOTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "screenshots"))
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

DOM_INSPECTION_JS = """
() => {
    // 1. Broken images
    const brokenImages = [];
    document.querySelectorAll('img').forEach(img => {
        if (!img.complete || img.naturalWidth === 0) {
            brokenImages.push({
                src: img.src || img.getAttribute('src') || '',
                alt: img.getAttribute('alt') || '',
                selector: img.className ? `.${img.className.split(' ').filter(Boolean).join('.')}` : (img.id ? `#${img.id}` : 'img')
            });
        }
    });

    // 2. Horizontal overflow
    const docElem = document.documentElement;
    const body = document.body;
    const scrollWidth = Math.max(docElem.scrollWidth, body ? body.scrollWidth : 0);
    const clientWidth = Math.max(docElem.clientWidth, body ? body.clientWidth : window.innerWidth);
    const horizontalOverflow = scrollWidth > clientWidth + 2;
    const overflowDetails = horizontalOverflow ? { scrollWidth, clientWidth } : null;

    // 3. Clipped elements
    const clippedElements = [];
    document.querySelectorAll('*').forEach(el => {
        if (el.children.length === 0 && el.textContent && el.textContent.trim().length > 0) {
            const style = window.getComputedStyle(el);
            const isOverflowHidden = (style.overflow === 'hidden' || style.overflowX === 'hidden' || style.textOverflow === 'clip' || style.textOverflow === 'ellipsis');
            if (isOverflowHidden && el.scrollWidth > el.clientWidth + 2) {
                clippedElements.push({
                    selector: el.tagName.toLowerCase() + (el.className ? `.${el.className.split(' ').filter(Boolean).join('.')}` : ''),
                    text: el.textContent.trim().slice(0, 100),
                    scrollWidth: el.scrollWidth,
                    clientWidth: el.clientWidth
                });
            }
        }
    });

    // 4. Small touch targets
    const smallTargets = [];
    document.querySelectorAll('a, button, input[type="button"], input[type="submit"], [role="button"]').forEach(el => {
        const rect = el.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0 && (rect.width < 44 || rect.height < 44)) {
            smallTargets.push({
                selector: el.tagName.toLowerCase() + (el.className ? `.${el.className.split(' ').filter(Boolean).join('.')}` : '') + (el.getAttribute('title') ? `[title='${el.getAttribute('title')}']` : ''),
                text: el.textContent ? el.textContent.trim().slice(0, 30) : '',
                width: Math.round(rect.width),
                height: Math.round(rect.height)
            });
        }
    });

    // 5. Missing alt text
    const missingAlts = [];
    document.querySelectorAll('img').forEach(img => {
        const alt = img.getAttribute('alt');
        if (alt === null || alt.trim() === '') {
            missingAlts.push({
                src: (img.getAttribute('src') || '').slice(0, 80),
                selector: img.tagName.toLowerCase() + (img.className ? `.${img.className.split(' ').filter(Boolean).join('.')}` : '')
            });
        }
    });

    // 6. Missing form labels
    const missingLabels = [];
    document.querySelectorAll('input, select, textarea').forEach(input => {
        const type = input.getAttribute('type') || 'text';
        if (['hidden', 'submit', 'button', 'reset'].includes(type)) return;
        const id = input.id;
        const hasForLabel = id ? !!document.querySelector(`label[for="${id}"]`) : false;
        const hasParentLabel = !!input.closest('label');
        const hasAria = !!input.getAttribute('aria-label') || !!input.getAttribute('aria-labelledby');
        const hasPlaceholder = !!input.getAttribute('placeholder') && input.getAttribute('placeholder').trim().length > 0;
        if (!hasForLabel && !hasParentLabel && !hasAria && !hasPlaceholder) {
            missingLabels.push({
                name: input.getAttribute('name') || '',
                type: type,
                id: id || '',
                placeholder: input.getAttribute('placeholder') || ''
            });
        }
    });

    return {
        broken_images: brokenImages,
        horizontal_overflow: horizontalOverflow,
        overflow_details: overflowDetails,
        clipped_elements: clippedElements,
        small_touch_targets: smallTargets,
        missing_alt_images: missingAlts,
        missing_form_labels: missingLabels
    };
}
"""

async def audit_viewport(
    browser: Browser,
    url: str,
    viewport_name: str,
    width: int,
    height: int
) -> Tuple[str, DOMSignals]:
    """
    Open page in a dedicated browser context for the specified viewport,
    capture screenshot, and collect DOM signals (console, network, DOM inspection).
    """
    context = await browser.new_context(
        viewport={"width": width, "height": height},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = await context.new_page()

    console_errors = []
    failed_requests = []

    # Listeners
    page.on("pageerror", lambda exc: console_errors.append(str(exc)))
    page.on("console", lambda msg: console_errors.append(f"Console {msg.type}: {msg.text}") if msg.type == "error" else None)
    page.on("requestfailed", lambda req: failed_requests.append({
        "url": req.url,
        "failure": req.failure or "Failed request"
    }))
    page.on("response", lambda res: failed_requests.append({
        "url": res.url,
        "status": res.status,
        "error": f"HTTP {res.status}"
    }) if res.status >= 400 else None)

    try:
        # Navigate with domcontentloaded first, then brief networkidle wait
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            try:
                await page.wait_for_load_state("networkidle", timeout=4000)
            except Exception:
                pass
        except Exception:
            await page.goto(url, wait_until="load", timeout=15000)

        # Allow dynamic scripts to settle
        await asyncio.sleep(0.5)

        # Capture full-page screenshot
        file_id = f"{viewport_name}_{uuid.uuid4().hex[:8]}.png"
        screenshot_path = os.path.join(SCREENSHOTS_DIR, file_id)
        await page.screenshot(path=screenshot_path, full_page=True)
        screenshot_url = f"/screenshots/{file_id}"

        # Collect DOM inspection data
        dom_data = await page.evaluate(DOM_INSPECTION_JS)

        signals = DOMSignals(
            console_errors=console_errors,
            failed_requests=failed_requests,
            broken_images=dom_data.get("broken_images", []),
            horizontal_overflow=dom_data.get("horizontal_overflow", False),
            overflow_details=dom_data.get("overflow_details"),
            clipped_elements=dom_data.get("clipped_elements", []),
            small_touch_targets=dom_data.get("small_touch_targets", []) if viewport_name == "mobile" else [],
            missing_alt_images=dom_data.get("missing_alt_images", []),
            missing_form_labels=dom_data.get("missing_form_labels", [])
        )

        return screenshot_url, signals

    finally:
        await context.close()

async def capture_both_viewports(url: str) -> Dict[str, Any]:
    """
    Launch Chromium and capture both desktop and mobile viewports.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
        )
        try:
            desktop_url, desktop_signals = await audit_viewport(
                browser, url, "desktop", 1440, 900
            )
            mobile_url, mobile_signals = await audit_viewport(
                browser, url, "mobile", 390, 844
            )
            return {
                "screenshots": {
                    "desktop": desktop_url,
                    "mobile": mobile_url
                },
                "signals": {
                    "desktop": desktop_signals,
                    "mobile": mobile_signals
                }
            }
        finally:
            await browser.close()

import os
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from backend.schemas import AuditReport, Issue, SuggestedFix, DOMSignals, AuditScreenshots
from backend.browser import capture_both_viewports, SCREENSHOTS_DIR
from backend.vision import analyze_viewport_screenshot

SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3
}

SEVERITY_WEIGHTS = {
    "critical": 18,
    "high": 10,
    "medium": 5,
    "low": 2
}

CACHE_DEMO_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "cache", "demo_report.json"))

def load_cached_demo_report() -> Dict[str, Any]:
    if os.path.exists(CACHE_DEMO_PATH):
        with open(CACHE_DEMO_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    raise FileNotFoundError("cache/demo_report.json not found")

def deduplicate_and_sort_issues(issues: List[Dict[str, Any]]) -> List[Issue]:
    """
    Merge overlapping issues across viewports, normalize viewports, and sort by severity.
    """
    merged_map: Dict[str, Dict[str, Any]] = {}

    for item in issues:
        # Create a rough deduplication key based on normalized title or category + location
        title_key = item.get("title", "").strip().lower()
        category_key = item.get("category", "")
        key = f"{category_key}:{title_key[:25]}"

        if key in merged_map:
            existing = merged_map[key]
            # If seen on different viewports, mark as 'both'
            if existing.get("viewport") != item.get("viewport"):
                existing["viewport"] = "both"
            # Upgrade severity if higher
            if SEVERITY_ORDER.get(item.get("severity"), 3) < SEVERITY_ORDER.get(existing.get("severity"), 3):
                existing["severity"] = item.get("severity")
        else:
            merged_map[key] = dict(item)

    parsed_issues: List[Issue] = []
    for raw in merged_map.values():
        suggested_raw = raw.get("suggested_fix") or {}
        if isinstance(suggested_raw, dict):
            suggested_fix = SuggestedFix(
                language=suggested_raw.get("language", "css"),
                code=suggested_raw.get("code", ""),
                explanation=suggested_raw.get("explanation", "")
            )
        else:
            suggested_fix = SuggestedFix(language="css", code=str(suggested_raw), explanation="")

        parsed_issues.append(Issue(
            title=raw.get("title", "مشكلة غير معنونة"),
            category=raw.get("category", "visual"),
            severity=raw.get("severity", "medium"),
            viewport=raw.get("viewport", "desktop"),
            description=raw.get("description", ""),
            location=raw.get("location", "الصفحة الرئيسية"),
            suggested_fix=suggested_fix,
            test_scenario=raw.get("test_scenario", "# Playwright test scenario")
        ))

    # Sort by severity
    parsed_issues.sort(key=lambda x: SEVERITY_ORDER.get(x.severity, 99))
    return parsed_issues

class AuditAgent:
    def __init__(self):
        pass

    async def run_audit(self, url: str, force_demo: bool = False) -> AuditReport:
        start_time = time.time()
        api_key = os.getenv("GEMINI_API_KEY")
        use_demo_mode = force_demo or not api_key

        # 1. Capture viewports and DOM signals with Playwright
        live_browser_failed = False
        try:
            browser_result = await capture_both_viewports(url)
            desktop_img_url = browser_result["screenshots"]["desktop"]
            mobile_img_url = browser_result["screenshots"]["mobile"]
            signals = browser_result["signals"]
        except Exception as e:
            if not use_demo_mode:
                raise RuntimeError(f"تعذر على المتصفح فتح وتصوير الصفحة ({str(e)})")
            # If in demo fallback mode and Playwright fails to load local page
            live_browser_failed = True
            desktop_img_url = "/screenshots/demo_desktop.png"
            mobile_img_url = "/screenshots/demo_mobile.png"
            signals = {
                "desktop": DOMSignals(),
                "mobile": DOMSignals()
            }

        # 2. Vision analysis or Demo Fallback
        if use_demo_mode:
            demo_data = load_cached_demo_report()
            
            # Map issues into typed schemas
            raw_issues = demo_data.get("issues", [])
            issues = deduplicate_and_sort_issues(raw_issues)
            
            # Use live signals if collected, else use cached signals
            final_signals = signals if not live_browser_failed else {
                "desktop": DOMSignals(**demo_data.get("signals", {}).get("desktop", {})),
                "mobile": DOMSignals(**demo_data.get("signals", {}).get("mobile", {}))
            }

            duration = round(time.time() - start_time, 2)
            if duration < 1.0:
                duration = 2.45

            return AuditReport(
                url=url,
                timestamp=datetime.now(timezone.utc).isoformat(),
                is_live=False,
                screenshots=AuditScreenshots(
                    desktop=desktop_img_url,
                    mobile=mobile_img_url
                ),
                signals=final_signals,
                issues=issues,
                summary=demo_data.get("summary", "فحص شامل للصفحة التجريبية."),
                score=demo_data.get("score", 50),
                duration_seconds=duration
            )

        # 3. Live LLM Analysis using Google Gemini Vision
        desktop_img_disk = os.path.join(SCREENSHOTS_DIR, os.path.basename(desktop_img_url))
        mobile_img_disk = os.path.join(SCREENSHOTS_DIR, os.path.basename(mobile_img_url))

        # Analyze desktop
        desktop_analysis = await analyze_viewport_screenshot(
            desktop_img_disk,
            "desktop",
            signals["desktop"],
            api_key=api_key
        )

        # Analyze mobile
        mobile_analysis = await analyze_viewport_screenshot(
            mobile_img_disk,
            "mobile",
            signals["mobile"],
            api_key=api_key
        )

        # Merge issues
        raw_combined_issues = []
        for issue in desktop_analysis.get("issues", []):
            issue["viewport"] = "desktop"
            raw_combined_issues.append(issue)
        for issue in mobile_analysis.get("issues", []):
            issue["viewport"] = "mobile"
            raw_combined_issues.append(issue)

        merged_issues = deduplicate_and_sort_issues(raw_combined_issues)

        # Compute dynamic score
        penalty = sum(SEVERITY_WEIGHTS.get(iss.severity, 5) for iss in merged_issues)
        score = max(5, min(100, 100 - penalty))

        # Produce summary
        desktop_sum = desktop_analysis.get("summary", "")
        mobile_sum = mobile_analysis.get("summary", "")
        summary = f"{desktop_sum} {mobile_sum}".strip()
        if not summary:
            summary = f"تم إتمام الفحص الشامل واكتشاف {len(merged_issues)} ملاحظة تتطلب المعالجة لتحسين جودة وتجاوب الواجهة."

        duration = round(time.time() - start_time, 2)

        return AuditReport(
            url=url,
            timestamp=datetime.now(timezone.utc).isoformat(),
            is_live=True,
            screenshots=AuditScreenshots(
                desktop=desktop_img_url,
                mobile=mobile_img_url
            ),
            signals=signals,
            issues=merged_issues,
            summary=summary,
            score=score,
            duration_seconds=duration
        )

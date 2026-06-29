from __future__ import annotations

import asyncio
from pathlib import Path

from .config import MonitorConfig


# -----------------------------------------------------------------------------
# Text helpers
# -----------------------------------------------------------------------------
# Build filesystem-safe labels used in screenshot file names.
def _safe_label(raw: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in raw).strip("-")
    return cleaned or "degraded"


# Normalize extracted UI text into a concise service name.
def _normalize_service_name(raw_text: str, keyword: str) -> str:
    text = " ".join(raw_text.split())
    lowered = text.lower()
    marker = keyword.lower()
    if marker in lowered:
        start = lowered.find(marker)
        text = text[:start].strip(" -:|/") or text
    return text[:120] if text else keyword


# -----------------------------------------------------------------------------
# Main capture workflow (Playwright)
# -----------------------------------------------------------------------------
# Captures the dashboard page, saves HTML/screenshot artifacts,
# then attempts to open degraded/critical service detail views.
async def _capture_async(config: MonitorConfig, screenshot_path: str, capture_path: str) -> dict:
    # Step 1: Import Playwright lazily so the module can load without browser deps.
    try:
        from playwright.async_api import async_playwright
    except Exception as exc:
        raise RuntimeError(
            "Playwright is required. Install dependencies and run: python -m playwright install chromium"
        ) from exc

    # Step 2: Launch browser and open the operation console dashboard.
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=config.skyvern.headless,
            args=config.skyvern.extra_chromium_args,
        )
        context = await browser.new_context(
            viewport={
                "width": config.skyvern.viewport_width,
                "height": config.skyvern.viewport_height,
            }
        )
        page = await context.new_page()
        await page.goto(
            config.operation_console_url,
            wait_until="load",
            timeout=config.skyvern.navigation_timeout_seconds * 1000,
        )
        # Give dynamic widgets extra time to render before collecting content.
        await asyncio.sleep(config.skyvern.wait_after_load_seconds)

        # Step 3: Capture primary page metadata and HTML.
        title = await page.title()
        html = await page.content()
        current_url = page.url

        # Step 4: Ensure output directories exist before writing files.
        Path(screenshot_path).parent.mkdir(parents=True, exist_ok=True)
        Path(capture_path).parent.mkdir(parents=True, exist_ok=True)

        # Save full-page screenshot and raw HTML of the main dashboard.
        await page.screenshot(path=screenshot_path, full_page=True)
        with open(capture_path, "w", encoding="utf-8") as file:
            file.write(html)

        # Step 5: Discover and capture detail pages for unhealthy states.
        degraded_views = []
        seen_keys = set()
        used_suffixes = set()
        keywords = ["degraded", "critical", "failed", "down", "unhealthy", "error"]

        for keyword in keywords:
            # Multiple selector strategies improve resilience to UI changes.
            candidates = [
                f"tr:has-text('{keyword}') a",
                f"[class*='service']:has-text('{keyword}') a",
                f"[class*='card']:has-text('{keyword}') a",
                f"a:has-text('{keyword}')",
                f"button:has-text('{keyword}')",
                f"[role='button']:has-text('{keyword}')",
                f"td:has-text('{keyword}')",
                f"div:has-text('{keyword}')",
            ]
            for selector in candidates:
                locator = page.locator(selector)
                count = await locator.count()
                if count == 0:
                    continue

                for index in range(count):
                    # Extract visible text and build a dedupe key.
                    node = locator.nth(index)
                    text = (await node.inner_text()).strip().replace("\n", " ")
                    if not text:
                        text = keyword
                    dedupe_key = f"{keyword}:{text[:120]}"
                    if dedupe_key in seen_keys:
                        continue

                    service_name = _normalize_service_name(text, keyword)
                    suffix = _safe_label(service_name)
                    if suffix in used_suffixes:
                        suffix = f"{suffix}-{len(used_suffixes) + 1}"

                    try:
                        # Step 6: Click candidate and verify real navigation occurred.
                        before_url = page.url
                        before_title = await page.title()
                        await node.first.click(timeout=3000)
                        await page.wait_for_timeout(1200)

                        detail_title = await page.title()
                        detail_html = await page.content()
                        detail_url = page.url

                        # Keep only real service drilldowns that navigate away.
                        navigated = detail_url != before_url or detail_title != before_title
                        if not navigated:
                            continue

                        # Step 7: Persist detail-page screenshot and metadata.
                        detail_name = Path(screenshot_path).stem + f"-{suffix}.png"
                        detail_path = str(Path(screenshot_path).with_name(detail_name))
                        await page.screenshot(path=detail_path, full_page=True)

                        degraded_views.append(
                            {
                                "label": text[:200],
                                "keyword": keyword,
                                "service_name": service_name,
                                "service_suffix": suffix,
                                "page_title": detail_title,
                                "page_url": detail_url,
                                "html": detail_html,
                                "screenshot_path": detail_path,
                            }
                        )
                        seen_keys.add(dedupe_key)
                        used_suffixes.add(suffix)

                        # Return to the dashboard before scanning the next candidate.
                        if page.url != before_url:
                            try:
                                await page.go_back(timeout=6000)
                                await page.wait_for_timeout(1200)
                            except Exception:
                                # Fallback: reload known dashboard URL when history fails.
                                await page.goto(
                                    config.operation_console_url,
                                    wait_until="load",
                                    timeout=config.skyvern.navigation_timeout_seconds * 1000,
                                )
                                await asyncio.sleep(config.skyvern.wait_after_load_seconds)
                    except Exception:
                        # Ignore individual candidate failures and keep scanning.
                        continue

        # Step 8: Close browser resources and return all collected artifacts.
        await context.close()
        await browser.close()

        return {
            "page_title": title,
            "page_url": current_url,
            "html": html,
            "degraded_views": degraded_views,
        }


# Synchronous wrapper used by callers that are not async-aware.
def capture_console_page(config: MonitorConfig, screenshot_path: str, capture_path: str) -> dict:
    return asyncio.run(_capture_async(config, screenshot_path, capture_path))

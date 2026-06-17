from __future__ import annotations

import base64
import json
from pathlib import Path
from urllib import request

from .config import MonitorConfig


def _build_schema(max_findings: int) -> dict:
    return {
        "type": "object",
        "properties": {
            "overall_status": {"type": "string"},
            "summary": {"type": "string"},
            "summary_insights": {
                "type": "array",
                "items": {"type": "string"},
            },
            "findings": {
                "type": "array",
                "maxItems": max_findings,
                "items": {
                    "type": "object",
                    "properties": {
                        "severity": {"type": "string"},
                        "issue": {"type": "string"},
                        "recommendation": {"type": "string"},
                        "evidence": {"type": "string"},
                        "details": {"type": "string"},
                        "source_view": {"type": "string"},
                    },
                    "required": [
                        "severity",
                        "issue",
                        "recommendation",
                        "evidence",
                        "details",
                        "source_view",
                    ],
                },
            },
        },
        "required": ["overall_status", "summary", "summary_insights", "findings"],
    }


def _fallback_summary() -> dict:
    return {
        "overall_status": "unknown",
        "summary": "Analysis fallback: unable to parse model output.",
        "summary_insights": [],
        "findings": [],
    }


def analyze_page(
    config: MonitorConfig,
    screenshot_paths: list[str],
    page_title: str,
    page_url: str,
    page_html: str,
    degraded_views: list[dict] | None = None,
) -> dict:
    schema = _build_schema(config.analysis.max_findings)

    html_excerpt = (page_html or "")[: config.ollama.max_page_content_chars]
    degraded_views = degraded_views or []
    service_names = [str(view.get("service_name", "")).strip() for view in degraded_views if view.get("service_name")]

    detail_blocks = []
    for index, view in enumerate(degraded_views, start=1):
        detail_html = str(view.get("html", ""))[: max(1000, config.ollama.max_page_content_chars // 2)]
        detail_blocks.append(
            "\n".join(
                [
                    f"Detail view {index} label: {view.get('label', '')}",
                    f"Detail view {index} keyword: {view.get('keyword', '')}",
                    f"Detail view {index} service_name: {view.get('service_name', '')}",
                    f"Detail view {index} title: {view.get('page_title', '')}",
                    f"Detail view {index} url: {view.get('page_url', '')}",
                    f"Detail view {index} html excerpt:\n{detail_html}",
                ]
            )
        )

    detail_context = "\n\n".join(detail_blocks)
    prompt = (
        "You are monitoring an operation console. "
        "Return concise JSON matching the schema. "
        "Classify status as healthy, warning, or critical when possible. "
        "When degraded drilldowns are provided, include specific details from those pages.\n\n"
        "Set source_view to 'main' or an exact service_name from the list below when applicable.\n\n"
        f"Page title: {page_title}\n"
        f"Page url: {page_url}\n"
        f"Available service_name values: {service_names}\n"
        f"Page content excerpt:\n{html_excerpt}\n\n"
        f"Degraded detail context:\n{detail_context}"
    )

    user_message: dict = {"role": "user", "content": prompt}
    images = []
    if config.ollama.vision_enabled:
        for image_path in screenshot_paths:
            if Path(image_path).exists():
                with open(image_path, "rb") as file:
                    image_b64 = base64.b64encode(file.read()).decode("ascii")
                images.append(image_b64)
    if images:
        user_message["images"] = images

    payload = {
        "model": config.ollama.model,
        "messages": [
            {
                "role": "system",
                "content": "You are a strict JSON generator for operations monitoring.",
            },
            user_message,
        ],
        "stream": False,
        "format": schema,
        "options": {"temperature": 0},
    }

    url = f"{config.ollama.base_url.rstrip('/')}/api/chat"
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=config.ollama.timeout_seconds) as response:
        body = json.loads(response.read().decode("utf-8"))

    try:
        raw_content = body["message"]["content"]
        parsed = json.loads(raw_content)
        if not isinstance(parsed, dict):
            return _fallback_summary()
        parsed.setdefault("overall_status", "unknown")
        parsed.setdefault("summary", "No summary provided.")
        parsed.setdefault("summary_insights", [])
        parsed.setdefault("findings", [])
        return parsed
    except Exception:
        return _fallback_summary()

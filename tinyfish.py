"""Small, import-safe TinyFish API client for Tech Deals."""
from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

load_dotenv()


class TinyFishError(RuntimeError):
    """A useful error returned by TinyFish or the network transport."""


class TinyFishClient:
    def __init__(self, api_key: str | None = None, session: Any = requests):
        self.api_key = api_key if api_key is not None else os.getenv("TINYFISH_API_KEY", "")
        self.session = session

    @property
    def ready(self) -> bool:
        return bool(self.api_key.strip())

    def _headers(self, json_body: bool = False) -> dict[str, str]:
        headers = {"X-API-Key": self.api_key}
        if json_body:
            headers["Content-Type"] = "application/json"
        return headers

    @staticmethod
    def _json_response(response: Any) -> Any:
        if not response.ok:
            detail = response.text[:700] if response.text else f"HTTP {response.status_code}"
            raise TinyFishError(f"TinyFish request failed ({response.status_code}): {detail}")
        try:
            return response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise TinyFishError("TinyFish returned an unreadable response.") from exc

    def search(self, query: str, location: str = "IN", domain: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"query": query, "location": location, "language": "en"}
        if domain:
            params["include_domains"] = domain
        response = self.session.get(
            "https://api.search.tinyfish.ai?" + urlencode(params),
            headers=self._headers(), timeout=(10, 60),
        )
        return self._json_response(response)

    def fetch(self, url: str) -> dict[str, Any]:
        response = self.session.post(
            "https://api.fetch.tinyfish.ai",
            headers=self._headers(True), json={"urls": [url], "format": "markdown", "ttl": 0,
                                               "purpose": "Inspect current product pricing, discount and availability."},
            timeout=(10, 120),
        )
        return self._json_response(response)

    def agent(self, url: str, goal: str) -> dict[str, Any]:
        response = self.session.post(
            "https://agent.tinyfish.ai/v1/automation/run-sse",
            headers=self._headers(True), json={"url": url, "goal": goal},
            stream=True, timeout=(15, 400),
        )
        if not response.ok:
            detail = response.text[:700] if response.text else f"HTTP {response.status_code}"
            raise TinyFishError(f"TinyFish Agent failed ({response.status_code}): {detail}")
        response.encoding = response.encoding or "utf-8"
        events, final = [], None
        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            try:
                event = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue
            event_type = event.get("type") or event.get("event")
            events.append({"type": event_type, "purpose": event.get("purpose")})
            if event_type in {"COMPLETE", "complete", "final_result"}:
                final = event.get("result", event)
            if event_type in {"FAILED", "failed", "error"}:
                raise TinyFishError(event.get("error") or "TinyFish Agent run failed.")
        if final is None:
            raise TinyFishError("The Agent stream ended before a final result arrived.")
        return {"result": final, "events": events}

    def research(self, query: str) -> dict[str, Any]:
        response = self.session.post(
            "https://agent.tinyfish.ai/v1/automation/run-research",
            headers=self._headers(True), json={"query": query, "mode": "deep"},
            stream=True, timeout=(15, 400),
        )
        if not response.ok:
            detail = response.text[:700] if response.text else f"HTTP {response.status_code}"
            raise TinyFishError(f"TinyFish Research failed ({response.status_code}): {detail}")
        response.encoding = response.encoding or "utf-8"
        events = []
        for line in response.iter_lines(decode_unicode=True):
            if line and line.startswith("data:"):
                try:
                    events.append(json.loads(line[5:].strip()))
                except json.JSONDecodeError:
                    continue
        report = next((e for e in reversed(events) if e.get("event") == "final_result"), None)
        if not report:
            raise TinyFishError("Research stream ended before the report was ready.")
        return report

    def create_monitor(self, url: str, schedule_cron: str, name: str) -> dict[str, Any]:
        payload = {
            "type": "fetch", "name": name,
            "config": {"url": url, "format": "markdown", "links": False, "image_links": False},
            "schedule_cron": schedule_cron,
            "purpose": "The displayed product price, discount, stock status or sale terms change.",
        }
        response = self.session.post(
            "https://agent.tinyfish.ai/v1/monitors", headers=self._headers(True),
            json=payload, timeout=(10, 120),
        )
        return self._json_response(response)

    def create_browser_session(self, url: str) -> dict[str, Any]:
        response = self.session.post(
            "https://api.browser.tinyfish.ai", headers=self._headers(True),
            json={"url": url}, timeout=(15, 90),
        )
        return self._json_response(response)

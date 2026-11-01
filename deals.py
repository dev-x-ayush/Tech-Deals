"""Local web server for the Tech Deals frontend."""
from __future__ import annotations

import json
import os
import mimetypes
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import requests
from dotenv import load_dotenv

from tinyfish import TinyFishClient, TinyFishError

load_dotenv()

WEB_DIR = Path(__file__).resolve().parent / "web"
STORE_DOMAINS = {
    "amazon": {"IN": "amazon.in", "US": "amazon.com"},
    "flipkart": {"IN": "flipkart.com", "US": "flipkart.com"},
    "blinkit": {"IN": "blinkit.com", "US": "blinkit.com"},
    "walmart": {"IN": "walmart.com", "US": "walmart.com"},
}
ALLOWED_HOSTS = {
    "amazon.in", "amazon.com", "flipkart.com", "blinkit.com", "walmart.com",
}
MONITOR_SCHEDULES = {"daily": "0 9 * * *", "6hours": "0 */6 * * *"}
MAX_BODY_SIZE = 1_000_000


class Handler(BaseHTTPRequestHandler):
    server_version = "TechDeals/1.0"

    def _send_json(self, status: int, data: dict) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, message: str) -> None:
        self._send_json(status, {"error": message})

    def _read_json(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_error(400, "Invalid Content-Length.")
            return None
        if length <= 0 or length > MAX_BODY_SIZE:
            self._send_error(400, "Request body must be between 1 byte and 1 MB.")
            return None
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_error(400, "Request body must be valid JSON.")
            return None
        if not isinstance(payload, dict):
            self._send_error(400, "Request body must be a JSON object.")
            return None
        return payload

    @staticmethod
    def _valid_product_url(value: object) -> bool:
        if not isinstance(value, str) or len(value) > 2048:
            return False
        try:
            parsed = urlsplit(value)
            host = (parsed.hostname or "").lower().rstrip(".")
            return (
                parsed.scheme in {"http", "https"}
                and any(host == domain or host.endswith(f".{domain}") for domain in ALLOWED_HOSTS)
            )
        except ValueError:
            return False

    def _client(self) -> TinyFishClient | None:
        client = TinyFishClient()
        if not client.ready:
            self._send_error(503, "TinyFish API key is missing. Add TINYFISH_API_KEY to your .env file.")
            return None
        return client

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/health":
            self._send_json(200, {"ok": True, "tinyfish_configured": TinyFishClient().ready})
            return

        static_files = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/index.html": ("index.html", "text/html; charset=utf-8"),
            "/styles.css": ("styles.css", "text/css; charset=utf-8"),
            "/brand.css": ("brand.css", "text/css; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
        }
        asset = static_files.get(path)
        if asset is None:
            self._send_error(404, "Not found.")
            return
        filename, content_type = asset
        try:
            body = (WEB_DIR / filename).read_bytes()
        except OSError:
            self._send_error(500, "Frontend asset could not be read.")
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path not in {
            "/api/search", "/api/fetch", "/api/analyze", "/api/research",
            "/api/monitor", "/api/browser",
        }:
            self._send_error(404, "Not found.")
            return

        payload = self._read_json()
        if payload is None:
            return

        if path == "/api/search":
            self._search(payload)
            return
        if path == "/api/research":
            query = payload.get("query")
            if not isinstance(query, str) or not query.strip() or len(query) > 500:
                self._send_error(400, "Enter a product or research query (up to 500 characters).")
                return
        elif path in {"/api/fetch", "/api/analyze", "/api/monitor", "/api/browser"}:
            url = payload.get("url")
            if not self._valid_product_url(url):
                self._send_error(
                    400,
                    "Enter a valid Amazon, Flipkart, Blinkit, or Walmart product URL.",
                )
                return
            if path == "/api/monitor" and payload.get("schedule") not in MONITOR_SCHEDULES:
                self._send_error(400, "Choose a supported monitor schedule.")
                return

        client = self._client()
        if client is None:
            return
        try:
            if path == "/api/fetch":
                result, status = client.fetch(url), 200
            elif path == "/api/analyze":
                result, status = client.agent(
                    url,
                    "Inspect this product listing. Report the product name, displayed price, original price, "
                    "discount, seller and availability. Clearly mark details that are not shown.",
                ), 200
            elif path == "/api/research":
                result, status = client.research(query), 200
            elif path == "/api/monitor":
                result, status = client.create_monitor(
                    url,
                    MONITOR_SCHEDULES[payload["schedule"]],
                    f"Tech Deals price monitor: {urlsplit(url).hostname}",
                ), 201
            else:
                result, status = client.create_browser_session(url), 201
        except TinyFishError as error:
            self._send_error(502, str(error))
            return
        except requests.RequestException as error:
            self._send_error(502, f"TinyFish network request failed: {error}")
            return
        self._send_json(status, result if isinstance(result, dict) else {"result": result})

    def _search(self, payload: dict) -> None:
        query = payload.get("query")
        stores = payload.get("stores")
        region = payload.get("region", "IN")
        if not isinstance(query, str) or not query.strip() or len(query) > 180:
            self._send_error(400, "Enter a product name (up to 180 characters).")
            return
        if not isinstance(stores, list) or not stores or any(
            not isinstance(store, str) or store not in STORE_DOMAINS for store in stores
        ):
            self._send_error(400, "Select at least one supported store.")
            return
        stores = list(dict.fromkeys(stores))
        if region not in {"IN", "US"}:
            self._send_error(400, "Choose a supported search region.")
            return
        client = self._client()
        if client is None:
            return

        results, errors = [], []
        with ThreadPoolExecutor(max_workers=len(stores)) as pool:
            futures = {
                pool.submit(client.search, query.strip(), region, STORE_DOMAINS[store][region]): store
                for store in stores
            }
            for future, store in futures.items():
                try:
                    response = future.result()
                except (TinyFishError, requests.RequestException) as error:
                    errors.append({"store": store, "error": str(error)})
                    continue
                entries = response.get("results", []) if isinstance(response, dict) else []
                if isinstance(entries, list):
                    for entry in entries:
                        if isinstance(entry, dict):
                            results.append({**entry, "store": store, "site_name": store.title()})
        self._send_json(200, {"results": results, "errors": errors, "stores_searched": stores})

    def log_message(self, format: str, *args: object) -> None:
        super().log_message(format, *args)


def main() -> None:
    try:
        port = int(os.getenv("PORT", "8000"))
    except ValueError as error:
        raise SystemExit("PORT must be a valid port number.") from error
    if not 1 <= port <= 65535:
        raise SystemExit("PORT must be between 1 and 65535.")

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Tech Deals is running at http://127.0.0.1:{port} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Tech Deals.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

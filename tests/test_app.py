import json
import threading
import unittest
from http.client import HTTPConnection
from unittest.mock import patch

from http.server import ThreadingHTTPServer

from deals import Handler
from tinyfish import TinyFishClient


class FakeTinyFishClient:
    ready = True

    def search(self, query, location, domain):
        return {"results": [{"title": "Test headset", "snippet": "Sale listing", "url": "https://www.amazon.in/item"}]}

    def agent(self, url, goal): return {"result": {"name": "Test headset", "price": "₹999"}}
    def fetch(self, url): return {"results": [{"url": url, "text": "Test product page"}]}
    def research(self, query): return {"event": "final_result", "result": "Research summary", "citations": []}
    def create_monitor(self, url, schedule, name): return {"monitor": {"id": "monitor-test", "schedule_cron": schedule}}
    def create_browser_session(self, url): return {"session_id": "browser-test", "cdp_url": "wss://example.test/cdp"}


class AppSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, method, path, payload=None):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=3)
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Content-Type": "application/json"} if body else {}
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        content = response.read()
        connection.close()
        return response.status, response.getheader("Content-Type", ""), content

    def test_home_page_is_served(self):
        status, content_type, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn(b"Good tech.", body)

    def test_health_reports_missing_key_without_crashing(self):
        status, _, body = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertIn("tinyfish_configured", json.loads(body))

    def test_invalid_product_url_is_rejected(self):
        status, _, body = self.request("POST", "/api/fetch", {"url": "https://example.com/"})
        self.assertEqual(status, 400)
        self.assertIn("Amazon", json.loads(body)["error"])

    def test_search_requires_product_name(self):
        status, _, body = self.request("POST", "/api/search", {"query": "  "})
        self.assertEqual(status, 400)
        self.assertIn("product name", json.loads(body)["error"])

    def test_all_six_tinyfish_routes_reach_the_client(self):
        payloads = [
            ("/api/search", {"query": "headphones", "stores": ["amazon"], "region": "IN"}, 200),
            ("/api/fetch", {"url": "https://www.amazon.in/item"}, 200),
            ("/api/analyze", {"url": "https://www.amazon.in/item"}, 200),
            ("/api/research", {"query": "headphone sales"}, 200),
            ("/api/monitor", {"url": "https://www.amazon.in/item", "schedule": "daily"}, 201),
            ("/api/browser", {"url": "https://www.amazon.in/item"}, 201),
        ]
        with patch("deals.TinyFishClient", FakeTinyFishClient):
            for path, payload, expected_status in payloads:
                with self.subTest(path=path):
                    status, _, body = self.request("POST", path, payload)
                    self.assertEqual(status, expected_status, body.decode())
                    self.assertTrue(json.loads(body))

    def test_client_import_does_not_require_key_or_start_automation(self):
        client = TinyFishClient(api_key="")
        self.assertFalse(client.ready)


if __name__ == "__main__":
    unittest.main()

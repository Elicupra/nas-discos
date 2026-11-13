import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from disksearch.history import HistoryStore
from disksearch.search import demo_dataset
from disksearch.server import STATE, make_handler


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.store = HistoryStore(Path(cls.tmp.name) / "server.sqlite3")
        cls.data = demo_dataset()
        cls.store.record_search(cls.data)
        STATE["data"] = cls.data
        cls.httpd = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(False, False, cls.store)
        )
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.httpd.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=5)
        cls.store.close()
        cls.tmp.cleanup()
        STATE["data"] = None

    def get_json(self, path):
        with urlopen(self.base + path, timeout=10) as response:
            return json.loads(response.read().decode())

    def test_data_and_html(self):
        data = self.get_json("/api/data")
        self.assertEqual(len(data["items"]), len(self.data["items"]))
        self.assertIn("favorites", data)
        with urlopen(self.base + "/", timeout=10) as response:
            html = response.read().decode()
        self.assertIn("Discos duros internos", html)
        self.assertNotIn("/*DATA*/null", html)
        self.assertNotIn("/*HISTORY*/null", html)
        self.assertNotIn("/*CSS*/", html)
        self.assertNotIn("/*JS*/", html)

    def test_history_and_detail(self):
        listing = self.get_json("/api/history?" + urlencode({"limit": 5}))
        self.assertEqual(listing["total"], len(self.data["items"]))
        self.assertEqual(len(listing["items"]), 5)
        key = listing["items"][0]["key"]
        detail = self.get_json("/api/history/" + quote(key, safe=""))
        self.assertIn("product", detail)
        self.assertIn("offers", detail)

    def test_favorite_and_notifications(self):
        key = self.get_json("/api/history?limit=1")["items"][0]["key"]
        request = Request(
            self.base + "/api/favorites",
            data=json.dumps({"key": key, "favorite": True}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=10) as response:
            self.assertEqual(json.loads(response.read().decode())["ok"], True)
        stats = self.get_json("/api/stats")
        self.assertGreaterEqual(stats["favorites"], 1)
        notices = self.get_json("/api/notifications")
        self.assertIn("items", notices)

    def test_status_exposes_scope(self):
        status = self.get_json("/api/status")
        self.assertIn("scope", status)

    def test_invalid_favorite_is_rejected(self):
        request = Request(
            self.base + "/api/favorites",
            data=json.dumps({"favorite": True}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=10)
        caught.exception.close()


if __name__ == "__main__":
    unittest.main()

"""Wishlist + search history: persistence and per-browser isolation (offline, scrapers faked)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db  # noqa: E402

db.DB_PATH = os.path.join(tempfile.mkdtemp(), "t.db")
import app as appmod  # noqa: E402
from scrapers.common import FetchResult, Listing  # noqa: E402


def L(p, name, price, rank):
    return Listing(p, name, price, f"https://www.{'amazon.in/dp' if p == 'amazon' else 'flipkart.com/p'}/X{rank}",
                   None, 4.2, 100, rank)


def fake_fetch(query, fresh=False):
    if "nothing" in query:
        return {"amazon": FetchResult("amazon", "no_results", []),
                "flipkart": FetchResult("flipkart", "no_results", [])}
    return {"amazon": FetchResult("amazon", "ok", [L("amazon", "Apple iPhone 15 (128 GB) - Black", 70000, 0)]),
            "flipkart": FetchResult("flipkart", "ok", [L("flipkart", "Apple iPhone 15 (Blue, 128 GB)", 69500, 0)])}


class T(unittest.TestCase):
    def setUp(self):
        appmod.fetch_live = fake_fetch
        self.a = appmod.app.test_client()      # browser A (own cookie jar)
        self.b = appmod.app.test_client()      # browser B
        with db._db() as c:
            c.execute("DELETE FROM history"); c.execute("DELETE FROM wishlist")

    def test_history_saved_only_on_success_and_is_per_browser(self):
        self.a.get("/api/search?q=iPhone 15 128GB")
        self.a.get("/api/search?q=nothing here")
        self.assertEqual([i["query"] for i in self.a.get("/api/history").json["items"]], ["iPhone 15 128GB"])
        self.assertEqual(self.b.get("/api/history").json["items"], [])

    def test_history_no_duplicates_and_clear(self):
        for q in ("iPhone 15 128GB", "iphone 15 128gb"):
            self.a.get("/api/search?q=" + q)
        self.assertEqual(len(self.a.get("/api/history").json["items"]), 1)
        self.a.delete("/api/history")
        self.assertEqual(self.a.get("/api/history").json["items"], [])

    def test_wishlist_add_remove_persist_isolate(self):
        key = self.a.get("/api/search?q=iPhone 15 128GB").json["results"][0]["key"]
        self.assertEqual(self.a.post("/api/wishlist", json={"key": key}).json["count"], 1)
        items = self.a.get("/api/wishlist").json["items"]
        self.assertEqual(items[0]["flipkart"]["price"], 69500)
        self.assertEqual(self.b.get("/api/wishlist").json["items"], [])
        self.assertIn(key, self.a.get("/api/search?q=iPhone 15 128GB").json["wishlist_keys"])
        self.assertEqual(self.a.delete("/api/wishlist/" + key).json["count"], 0)
        self.assertEqual(self.a.get("/api/wishlist").json["items"], [])

    def test_wishlist_rejects_unknown_key(self):
        r = self.a.post("/api/wishlist", json={"key": "0123456789abcdef"})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.a.post("/api/wishlist", json={"key": "../x"}).status_code, 404)


if __name__ == "__main__":
    unittest.main()

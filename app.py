"""PriceWise: Amazon India vs Flipkart price comparison for electronics.

Run:  python app.py   then open http://127.0.0.1:5000
"""
import hashlib
import os
import re
import secrets
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, g, jsonify, render_template, request

import db
from comparison import build_comparison
from matching import query_is_allowed
from scrapers.amazon import search_amazon
from scrapers.flipkart import search_flipkart

app = Flask(__name__)

CACHE_TTL = int(os.getenv("PRICEWISE_CACHE_TTL", "120"))   # seconds; 0 disables caching
_cache = {}
_cache_lock = threading.Lock()
_slots = threading.Semaphore(2)                            # max 2 searches (4 browsers) at once

VID_COOKIE = "pw_vid"                                      # anonymous per-browser id (no login)
KEY_RE = re.compile(r"[0-9a-f]{16}")
_seen = OrderedDict()                                      # key -> row from a recent search
_seen_lock = threading.Lock()
SEEN_MAX = 1000


def product_key(row):
    """Stable id for a compared product, built from its real retailer URLs."""
    raw = "|".join((row.get(p) or {}).get("url", "") for p in ("amazon", "flipkart"))
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def remember(rows):
    with _seen_lock:
        for r in rows:
            r["key"] = product_key(r)
            _seen[r["key"]] = r
            _seen.move_to_end(r["key"])
        while len(_seen) > SEEN_MAX:
            _seen.popitem(last=False)


@app.before_request
def _visitor():
    vid = request.cookies.get(VID_COOKIE, "")
    g.new_vid = None
    if not re.fullmatch(r"[0-9a-f]{32}", vid):
        vid = secrets.token_hex(16)
        g.new_vid = vid
    g.vid = vid


@app.after_request
def _set_visitor_cookie(resp):
    if getattr(g, "new_vid", None):
        resp.set_cookie(VID_COOKIE, g.new_vid, max_age=60 * 60 * 24 * 365,
                        httponly=True, samesite="Lax")
    return resp


def fetch_live(query: str, fresh: bool):
    key = " ".join(query.lower().split())
    now = time.time()
    with _cache_lock:
        hit = _cache.get(key)
    if hit and not fresh and CACHE_TTL and now - hit[0] < CACHE_TTL:
        return hit[1]
    with _slots, ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(search_amazon, query)
        ff = pool.submit(search_flipkart, query)
        data = {"amazon": fa.result(), "flipkart": ff.result()}
    # Only cache complete fetches; failures are always retried live.
    if CACHE_TTL and all(r.status in ("ok", "no_results") for r in data.values()):
        with _cache_lock:
            _cache[key] = (now, data)
    return data


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/search")
def search():
    q = " ".join(request.args.get("q", "").split())
    if len(q) < 2 or len(q) > 100:
        return jsonify(error="Enter a product name between 2 and 100 characters."), 400
    if not query_is_allowed(q):
        return jsonify(error="PriceWise compares electronic products only "
                             "(phones, laptops, headphones, TVs and similar)."), 400
    data = fetch_live(q, fresh=request.args.get("fresh") == "1")
    payload = build_comparison(q, data)
    payload["server_time"] = time.time()
    remember(payload["results"])
    if payload["results"]:                      # only successful searches are saved
        db.history_add(g.vid, q)
    payload["wishlist_keys"] = db.wishlist_keys(g.vid)
    return jsonify(payload)


# ---------------- wishlist ----------------
@app.get("/api/wishlist")
def wishlist_get():
    items = db.wishlist_list(g.vid)
    return jsonify(items=items, keys=[i["key"] for i in items])


@app.post("/api/wishlist")
def wishlist_add():
    key = str((request.get_json(silent=True) or {}).get("key", ""))
    with _seen_lock:
        row = _seen.get(key) if KEY_RE.fullmatch(key) else None
    if row is None:
        return jsonify(error="This product has expired. Search for it again, then save it."), 404
    db.wishlist_add(g.vid, key, row)
    return jsonify(ok=True, count=len(db.wishlist_keys(g.vid)))


@app.delete("/api/wishlist/<key>")
def wishlist_remove(key):
    if KEY_RE.fullmatch(key):
        db.wishlist_remove(g.vid, key)
    return jsonify(ok=True, count=len(db.wishlist_keys(g.vid)))


# ---------------- search history ----------------
@app.get("/api/history")
def history_get():
    return jsonify(items=db.history_list(g.vid))


@app.delete("/api/history")
def history_clear():
    db.history_clear(g.vid)
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)

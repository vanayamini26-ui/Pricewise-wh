# PriceWise: Amazon vs Flipkart price comparison for electronics

Searches **Amazon India** and **Flipkart** live when you press the button, keeps only electronics,
matches the same product variant on both sites, and shows the price difference.
No paid API, no static dataset, no stored prices.

## Setup (Python 3.9+)

```
python -m venv venv
venv\Scripts\activate          # Windows   (Linux/macOS: source venv/bin/activate)
pip install -r requirements.txt
playwright install chromium
python app.py
```
Open http://127.0.0.1:5000

## If a platform shows "data unavailable"

Amazon and Flipkart actively block automated browsers, so this can happen. Try, in order:

1. Run headed (a visible browser window is blocked far less often):
   `set PRICEWISE_HEADLESS=0` (Windows) or `export PRICEWISE_HEADLESS=0` (Linux/macOS), then `python app.py`.
2. Search slowly; avoid many searches in a row.
3. Turn on debug dumps: `PRICEWISE_DEBUG=1`. Screenshots and HTML are saved in `debug/`
   so you can see whether it was a CAPTCHA or a changed page layout, and fix the selector in
   `scrapers/amazon.py` or `scrapers/flipkart.py` (the `_JS` block at the top of each file).

PriceWise never fills in a missing side with made-up or old data; it says "Data unavailable".

## Wishlist and Search History (added)

* **Wishlist**: every result has a heart button. Hearts are saved in SQLite (`instance/pricewise.db`),
  so they survive restarts. The Wishlist tab shows saved products with a Remove button. A saved
  product is a snapshot, labelled with the date you saved it. Search again for current prices.
* **Search History**: every search that returns products is saved automatically (up to 50, no
  duplicates). Tap one to search it again, or use Clear History. Failed or empty searches are not saved.
* **No login in this version**, so each browser gets an anonymous cookie id (`pw_vid`) and sees only its
  own wishlist and history. Clearing cookies or switching browser starts fresh. Real per-user accounts
  would need a login system, which this version does not have.
* New files: `db.py`, `tests/test_wishlist_history.py`. Changed: `app.py` (new `/api/wishlist`,
  `/api/history` routes) and `templates/index.html` (tabs, hearts, two views).
* `PRICEWISE_DB` sets the database path.

## Architecture

```
browser (templates/index.html)
   | GET /api/search?q=...
app.py ---- runs both scrapers in parallel (2 threads)
   |-- scrapers/amazon.py     Playwright -> Amazon India search page -> listings
   |-- scrapers/flipkart.py   Playwright -> Flipkart search page    -> listings
comparison.py                 filter + pair + price difference
matching.py                   electronics filter, accessory filter, variant matching
```

How matching works (`matching.py`): each title is parsed into brand, RAM, storage, model
numbers (e.g. `15`, `s24`) and variant words (`pro`, `max`, `plus`, `ultra`, `fe`...).
Two listings are paired only if brand, variant words, storage and RAM agree and the model
numbers match. "iPhone 15" never pairs with "iPhone 15 Pro" or a different storage size.

## Settings (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `PRICEWISE_HEADLESS` | `1` | `0` shows the browser window |
| `PRICEWISE_DEBUG` | `0` | `1` saves screenshots/HTML to `debug/` |
| `PRICEWISE_CACHE_TTL` | `120` | seconds a repeated search reuses its result; `0` = always fetch live. The UI shows "Fetched N seconds ago" and a "Fetch live prices again" button. |

## Tests (no internet needed)

```
python -m unittest discover -s tests -v
```

## Limitations (mention these in your report)

- Scraping depends on the sites' page structure and anti-bot systems; selectors may need updating.
- Both sites' terms restrict automated access. Use for low-volume academic demonstration only.
- Prices are the listed prices (not including coupons or bank offers).
- Matching is heuristic (title-based). Unusual titles can be missed or, rarely, mismatched.

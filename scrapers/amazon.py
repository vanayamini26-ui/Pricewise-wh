"""Amazon India search-results scraper (Playwright, no paid API)."""
import time
from urllib.parse import quote_plus

from .common import (FetchResult, Listing, PWTimeout, dump_debug, open_page,
                     parse_count, parse_price, parse_rating)

PLATFORM = "amazon"

# Runs inside the page. Uses stable data-* attributes and the canonical /dp/ASIN link,
# not Amazon's generated CSS class names.
_JS = r"""
() => Array.from(document.querySelectorAll('div[data-component-type="s-search-result"][data-asin]'))
  .map(el => {
    const asin = el.getAttribute('data-asin');
    if (!asin) return null;
    const h2 = el.querySelector('h2');
    let title = '';
    if (h2) title = (h2.getAttribute('aria-label') || h2.textContent || '').trim();
    const priceEl = el.querySelector('.a-price:not(.a-text-price) .a-offscreen');
    const img = el.querySelector('img.s-image');
    const ratingEl = el.querySelector('[aria-label*="out of 5 stars"], .a-icon-alt');
    let ratingText = '';
    if (ratingEl) ratingText = ratingEl.getAttribute('aria-label') || ratingEl.textContent || '';
    let reviewsText = '';
    const rA = el.querySelector('a[aria-label*=" ratings"], span[aria-label*=" ratings"]');
    if (rA) reviewsText = rA.getAttribute('aria-label') || '';
    else { const u = el.querySelector('span.s-underline-text'); if (u) reviewsText = u.textContent || ''; }
    return { asin, title, price: priceEl ? priceEl.textContent : '',
             image: img ? img.src : '', ratingText, reviewsText };
  }).filter(Boolean)
"""

_BLOCK_MARKERS = (
    "enter the characters you see below",
    "type the characters you see in this image",
    "automated access",
    "not a robot",
)


def _blocked(page) -> bool:
    try:
        title = (page.title() or "").lower()
        if "robot check" in title or "captcha" in title:
            return True
        if page.query_selector('form[action*="validateCaptcha"]'):
            return True
        text = page.inner_text("body", timeout=3000).lower()[:3000]
        return any(m in text for m in _BLOCK_MARKERS)
    except Exception:
        return False


def search_amazon(query: str, max_items: int = 20) -> FetchResult:
    url = "https://www.amazon.in/s?k=" + quote_plus(query)
    try:
        with open_page() as page:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=35000)
            if (resp and resp.status in (403, 429, 503)) or _blocked(page):
                dump_debug(page, "amazon_blocked")
                return FetchResult(PLATFORM, "blocked",
                                   message="Amazon showed a bot check (CAPTCHA) instead of results.")
            try:
                page.wait_for_selector('div[data-component-type="s-search-result"]', timeout=12000)
            except PWTimeout:
                dump_debug(page, "amazon_empty")
                if _blocked(page):
                    return FetchResult(PLATFORM, "blocked",
                                       message="Amazon showed a bot check (CAPTCHA) instead of results.")
                return FetchResult(PLATFORM, "no_results", message="Amazon returned no results.")
            raw = page.evaluate(_JS)
            dump_debug(page, "amazon_ok")
    except Exception as exc:  # network error, timeout, browser missing...
        return FetchResult(PLATFORM, "error", message=f"Amazon fetch failed: {type(exc).__name__}: {exc}")

    listings = []
    for r in raw:
        price = parse_price(r["price"])
        if not r["title"] or price is None:     # skip unavailable / no-price cards, never guess
            continue
        listings.append(Listing(
            platform=PLATFORM, name=r["title"], price=price,
            url=f"https://www.amazon.in/dp/{r['asin']}",
            image=r["image"] or None,
            rating=parse_rating(r["ratingText"]),
            reviews=parse_count(r["reviewsText"]),
            rank=len(listings),
        ))
        if len(listings) >= max_items:
            break
    if not listings:
        return FetchResult(PLATFORM, "no_results", message="Amazon results had no priced products.")
    return FetchResult(PLATFORM, "ok", listings, fetched_at=time.time())

"""Electronics filtering, query relevance and cross-platform product matching.

Nothing here talks to the network. It only decides, from listing titles:
  * is this an electronic product (and not an accessory)?
  * is it the product the user searched for?
  * are an Amazon listing and a Flipkart listing the same variant?
"""
import re
from dataclasses import dataclass
from typing import FrozenSet, Optional

# ----------------------------------------------------------------- vocab
BRANDS = {
    "apple", "samsung", "xiaomi", "redmi", "poco", "realme", "oppo", "vivo", "iqoo",
    "oneplus", "motorola", "nokia", "nothing", "google", "sony", "lg", "hp", "dell",
    "lenovo", "asus", "acer", "msi", "microsoft", "huawei", "honor", "tecno", "infinix",
    "lava", "jbl", "boat", "bose", "sennheiser", "boltt", "boult", "skullcandy", "anker",
    "logitech", "razer", "corsair", "hyperx", "redragon", "zebronics", "philips",
    "panasonic", "canon", "nikon", "fujifilm", "gopro", "dji", "tcl", "hisense", "mi",
    "amazfit", "garmin", "fitbit", "seagate", "sandisk", "kingston", "netgear", "epson",
    "brother", "benq", "viewsonic", "portronics", "marshall", "harman", "ptron",
    "crossbeat", "toshiba", "intex", "micromax", "itel", "gionee", "alcatel", "zte",
}
ALIASES = {  # product line -> brand (for titles that omit the brand)
    "iphone": "apple", "ipad": "apple", "macbook": "apple", "airpods": "apple",
    "imac": "apple", "galaxy": "samsung", "pixel": "google", "thinkpad": "lenovo",
    "ideapad": "lenovo", "legion": "lenovo", "pavilion": "hp", "omen": "hp",
    "inspiron": "dell", "xps": "dell", "vivobook": "asus", "zenbook": "asus",
    "rog": "asus", "predator": "acer", "aspire": "acer", "nitro": "acer",
    "bravia": "sony", "playstation": "sony", "xbox": "microsoft", "surface": "microsoft",
}
COLORS = {
    "black", "white", "blue", "red", "green", "yellow", "pink", "purple", "orange",
    "grey", "gray", "silver", "gold", "golden", "violet", "titanium", "graphite",
    "midnight", "starlight", "onyx", "cobalt", "amber", "marble", "lavender", "mint",
    "cream", "bronze", "teal", "navy", "beige", "coral", "lime", "rose", "sky", "space",
    "obsidian", "jade", "emerald", "sapphire", "ruby", "copper", "charcoal", "ivory",
    "phantom", "aurora", "ocean", "sunset", "forest", "desert", "natural",
}
NOISE = {
    "with", "and", "for", "the", "of", "in", "new", "latest", "original", "genuine",
    "brand", "smartphone", "smartphones", "phone", "mobile", "mobiles", "android", "ios",
    "ai", "dual", "sim", "unlocked", "5g", "4g", "lte", "camera", "display", "processor",
    "battery", "fast", "charging", "included", "box", "warranty", "year", "years",
    "india", "version", "model", "edition", "series", "gen", "generation", "by", "from",
    "free", "upto", "off", "combo", "pack", "pcs", "pc", "laptop", "laptops", "notebook",
    "tablet", "ram", "rom", "ssd", "hdd", "storage", "internal", "memory", "ddr4", "ddr5",
    "wireless", "bluetooth", "headset", "headphones", "headphone", "earphones", "earphone",
    "earbuds", "neckband", "true", "tws", "ear", "noise", "cancelling", "cancellation",
    "anc", "smart", "watch", "smartwatch", "tv", "television", "led", "uhd", "hd", "fhd",
    "windows", "win", "home", "office", "student", "thin", "light", "slim", "gaming",
    "full", "touch", "screen", "backlit", "wired", "usb", "type", "c", "mic", "microphone",
    "sealed", "refurbished", "renewed", "certified", "pre", "owned", "only", "upto",
    "gb", "tb", "mah", "hz", "inch", "inches", "cm", "mp", "intel", "amd", "core",
    "processor", "graphics", "nvidia", "geforce",
}
# Words that change *which product* it is. Both sides must agree exactly.
VARIANTS = {
    "pro", "max", "plus", "ultra", "fe", "mini", "lite", "se", "neo", "fold", "flip",
    "air", "edge", "gt", "turbo", "xl", "ace", "note", "prime", "power", "go", "play",
    "active", "classic", "sport", "slim", "t", "s",
}
VARIANTS -= {"slim", "t", "s", "go", "play", "active", "classic", "sport", "power"}

ACCESSORY_WORDS = {
    "case", "cases", "cover", "covers", "protector", "protectors", "tempered", "guard",
    "skin", "skins", "charger", "chargers", "cable", "cables", "adapter", "adaptor",
    "strap", "straps", "stand", "mount", "holder", "pouch", "sleeve", "film", "sticker",
    "stickers", "refill", "tripod", "gimbal", "lanyard", "ring", "grip", "bumper",
    "replacement", "wallet", "eartips", "tips", "dock", "cradle",
}
ACCESSORY_PHRASES = re.compile(
    r"\b(compatible with|suitable for|case for|cover for|fit for|designed for|"
    r"for (?:apple |samsung |xiaomi |oneplus |redmi |realme |oppo |vivo )?"
    r"(?:iphone|galaxy|ipad|macbook|pixel))\b"
)

NON_ELECTRONIC = {
    "shirt", "shirts", "tshirt", "tshirts", "jeans", "saree", "sarees", "kurta", "kurti",
    "kurtis", "dress", "dresses", "shoe", "shoes", "sandal", "sandals", "slipper",
    "slippers", "sneaker", "sneakers", "footwear", "sock", "socks", "jacket", "jackets",
    "hoodie", "hoodies", "trouser", "trousers", "lehenga", "bra", "innerwear", "lipstick",
    "perfume", "shampoo", "soap", "makeup", "moisturizer", "serum", "grocery", "groceries",
    "rice", "atta", "flour", "ghee", "biscuit", "biscuits", "snack", "snacks", "chocolate",
    "sofa", "mattress", "wardrobe", "curtain", "curtains", "bedsheet", "pillow", "toy",
    "toys", "books", "furniture", "cosmetics", "skincare", "backpack", "bag", "bags",
    "wallets", "handbag", "jewellery", "jewelry", "necklace", "earrings", "bangle",
    "bangles", "spices", "pickle", "detergent", "cushion", "carpet", "rug", "towel",
}
ELECTRONIC_HINTS = re.compile(
    r"\b(phone|smartphone|mobile|laptop|notebook|chromebook|macbook|tablet|tab|ipad|"
    r"earphones?|earbuds?|buds|headphones?|headset|neckband|airpods|smartwatch|watch|"
    r"band|camera|dslr|mirrorless|gopro|monitor|keyboard|mouse|speaker|soundbar|tv|"
    r"television|projector|printer|router|ssd|pendrive|power bank|powerbank|console|"
    r"playstation|xbox|drone|webcam|microphone|tws|gaming|controller|joystick)\b"
)
SPEC_HINTS = re.compile(
    r"\b\d+\s*(?:gb|tb|mah|hz|mp|ghz|nits|inch|inches)\b|"
    r"\b(?:bluetooth|wireless|usb|hdmi|wifi|wi-fi|oled|amoled|qled|lcd|android|ios)\b"
)


def _words(text: str):
    return re.findall(r"[a-z0-9]+", text.lower())


def query_is_allowed(query: str) -> bool:
    """False if the query is clearly about non-electronic goods."""
    return not (set(_words(query)) & NON_ELECTRONIC)


def is_electronic(title: str) -> bool:
    t = title.lower()
    if set(_words(t)) & NON_ELECTRONIC:
        return False
    toks = _words(t)
    if any(tok in BRANDS or tok in ALIASES for tok in toks):
        return True
    return bool(ELECTRONIC_HINTS.search(t) or SPEC_HINTS.search(t))


def is_accessory(title: str, query: str) -> bool:
    """True for cases/chargers/etc. unless the user searched for that accessory."""
    t = title.lower()
    qwords = set(_words(query))
    hits = (set(_words(t)) & ACCESSORY_WORDS) - qwords
    if hits:
        return True
    if ACCESSORY_PHRASES.search(t) and not ACCESSORY_PHRASES.search(query.lower()):
        return True
    return False


# ----------------------------------------------------------------- parsing
_MEM = re.compile(r"(\d+(?:\.\d+)?)\s*(gb|tb)\b")
_SPEC = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:gb|tb|mah|hz|mp|inches|inch|ghz|nits|watts|watt|w|mm|cm|"
    r"hrs|hours|hr|v|db|dpi|k)\b"
)
_WINDOWS = re.compile(r"\bwin(?:dows)?\s*(?:10|11)\b")


def _memory(t: str):
    storage = ram = None
    unlabeled = []
    for m in _MEM.finditer(t):
        v = float(m.group(1))
        gb = int(v * 1024) if m.group(2) == "tb" else int(v)
        after = t[m.end(): m.end() + 14]
        before = t[max(0, m.start() - 10): m.start()]
        after_ram = re.match(r"\s*(?:ddr\d\w*\s*)?(?:ram|memory)", after)
        after_sto = re.match(r"\s*(?:rom|ssd|hdd|storage|internal|emmc|nvme|ufs|flash)", after)
        before_ram = ram is None and re.search(r"ram\s*[:\-]?\s*$", before)
        before_sto = storage is None and re.search(r"(?:storage|ssd|rom)\s*[:\-]?\s*$", before)
        if after_ram:
            ram = ram or gb
        elif after_sto:
            storage = storage or gb
        elif before_ram:
            ram = gb
        elif before_sto:
            storage = gb
        else:
            unlabeled.append(gb)
    if unlabeled:
        if storage is None and ram is None:
            if len(unlabeled) >= 2:
                ram, storage = min(unlabeled), max(unlabeled)
            elif unlabeled[0] >= 32:
                storage = unlabeled[0]
            else:
                ram = unlabeled[0]
        elif storage is None:
            storage = max(unlabeled)
        elif ram is None:
            ram = min(unlabeled)
    return storage, ram


@dataclass(frozen=True)
class Spec:
    brand: Optional[str]
    storage: Optional[int]
    ram: Optional[int]
    variants: FrozenSet[str]
    ident: FrozenSet[str]   # tokens containing digits (model numbers)
    words: FrozenSet[str]   # remaining descriptive tokens


def parse_title(title: str) -> Spec:
    t = title.lower().replace("+", " plus ").replace("&", " and ").replace("one plus", "oneplus")
    storage, ram = _memory(t)
    inside = " ".join(re.findall(r"\(([^)]*)\)", t))
    outside = re.sub(r"\([^)]*\)", " ", t)
    outside = _SPEC.sub(" ", _WINDOWS.sub(" ", outside))
    inside = _SPEC.sub(" ", _WINDOWS.sub(" ", inside))
    toks = _words(outside) + [x for x in _words(inside) if re.search(r"\d", x) and re.search(r"[a-z]", x)]

    brand = next((x for x in toks if x in BRANDS), None)
    if brand is None:
        brand = next((ALIASES[x] for x in toks if x in ALIASES), None)

    variants, ident, words = set(), set(), set()
    for x in toks:
        if x in BRANDS or x in COLORS or x in NOISE:
            continue
        if re.fullmatch(r"(19|20)\d\d", x):          # model years
            continue
        if x in VARIANTS:
            variants.add(x)
        elif re.search(r"\d", x):
            ident.add(x)
        else:
            words.add(x)
    return Spec(brand, storage, ram, frozenset(variants), frozenset(ident), frozenset(words))


# ----------------------------------------------------------------- matching
def _jaccard(a, b) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def is_relevant(q: Spec, t: Spec) -> bool:
    """Does listing spec `t` answer the search spec `q`?"""
    if q.brand and t.brand and q.brand != t.brand:
        return False
    if q.ident:
        if not q.ident <= t.ident:
            return False
        if q.variants != t.variants:      # "S24" must not return "S24 Ultra"
            return False
    elif q.variants and not q.variants <= t.variants:
        return False
    if q.words:
        overlap = len(q.words & (t.words | t.variants)) / len(q.words)
        if overlap < 0.7:
            return False
    if q.storage and t.storage and q.storage != t.storage:
        return False
    if q.ram and t.ram and q.ram != t.ram:
        return False
    return True


def pair_score(a: Spec, b: Spec) -> float:
    """0 if not the same variant, otherwise a similarity score in (0, 1]."""
    if a.brand and b.brand and a.brand != b.brand:
        return 0.0
    if a.variants != b.variants:
        return 0.0
    if a.storage and b.storage and a.storage != b.storage:
        return 0.0
    if a.ram and b.ram and a.ram != b.ram:
        return 0.0
    wj = _jaccard(a.words, b.words)
    if a.ident or b.ident:
        ij = _jaccard(a.ident, b.ident)
        if ij < 0.6:
            return 0.0
        score, threshold = 0.6 * ij + 0.4 * wj, 0.6
    else:
        score, threshold = wj, 0.5
    if bool(a.storage) != bool(b.storage):    # one side doesn't state storage
        score *= 0.9
    return score if score >= threshold else 0.0


def memory_label(spec: Spec) -> Optional[str]:
    def fmt(gb):
        return f"{gb // 1024} TB" if gb >= 1024 and gb % 1024 == 0 else f"{gb} GB"
    parts = []
    if spec.ram:
        parts.append(f"{fmt(spec.ram)} RAM")
    if spec.storage:
        parts.append(fmt(spec.storage))
    return " + ".join(parts) or None

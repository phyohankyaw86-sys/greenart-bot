"""
GreenArt — Local NLP Parser (No API needed)
============================================
Rule-based parser for Burmese/English sales bot messages.
Falls back to keyword matching — 100% free, no latency.
"""
import re


ITEM_MAP = {
    "20g": "Beef Jerky 20g", "20": "Beef Jerky 20g",
    "50g": "Beef Jerky 50g", "50": "Beef Jerky 50g",
    "100g": "Beef Jerky 100g", "100": "Beef Jerky 100g",
    "200g": "Beef Jerky 200g", "200": "Beef Jerky 200g",
}
CHANNEL_MAP = {
    "retail": "retail", "retailer": "retail",
    "wholesale": "wholesale", "wholesaler": "wholesale",
    "distributor": "distributor", "dist": "distributor",
    "online": "online",
}
EXPENSE_CATS = {
    "marketing": "Marketing", "facebook": "Marketing", "ads": "Marketing",
    "rent": "Rent", "ငှားရမ်း": "Rent",
    "transport": "Transport/Delivery", "delivery": "Transport/Delivery",
    "fuel": "Transport/Delivery", "ဆီ": "Transport/Delivery",
    "admin": "Admin/Office", "office": "Admin/Office",
    "salary": "Labor", "labor": "Labor", "လုပ်ခ": "Labor",
    "util": "Utilities", "electric": "Utilities", "မီး": "Utilities",
    "packaging": "Packaging", "bag": "Packaging",
}


def _nums(text):
    """Extract all integers from text."""
    return [int(x.replace(",", "")) for x in re.findall(r"[\d,]+", text)]


def parse_intent(text: str) -> dict:
    t = text.strip().lower()
    nums = _nums(t)
    parts = text.strip().split()

    # ── SALE: Name size qty price [channel] ──────────────────────────
    # e.g. "MaHla 100g 10 5000 retail"
    if len(parts) >= 4:
        size_tok = parts[1].lower()
        if size_tok in ITEM_MAP and len(nums) >= 2:
            ch = CHANNEL_MAP.get(parts[4].lower() if len(parts) > 4 else "retail", "retail")
            return {
                "action": "record_sale",
                "customer": parts[0],
                "item": ITEM_MAP[size_tok],
                "quantity": nums[0],
                "unit_price": nums[1],
                "channel": ch,
                "delivery_ch": "Direct",
                "delivery_fee": 0,
            }

    # ── BATCH: batch_no raw_kg output_kg ─────────────────────────────
    # e.g. "Batch001 5kg beef 2.8kg output" | "B001 beef 5kg → 3kg"
    if any(kw in t for kw in ["batch", "beef input", "raw beef", "→", "output"]):
        batch_no = None
        for p in parts:
            if re.match(r"(batch|b)\d+", p.lower()):
                batch_no = p.upper()
        float_nums = [float(x) for x in re.findall(r"[\d]+\.?[\d]*", t)]
        raw = float_nums[0] if float_nums else 0
        dry = float_nums[1] if len(float_nums) > 1 else 0
        return {
            "action": "record_batch",
            "batch_no": batch_no or f"B{re.sub(r'[^0-9]','',t)[:6]}",
            "raw_beef_kg": raw,
            "dried_output_kg": dry,
        }

    # ── EXPENSE: keywords + amount ────────────────────────────────────
    exp_cat = None
    for kw, cat in EXPENSE_CATS.items():
        if kw in t:
            exp_cat = cat
            break
    if exp_cat and nums:
        pay = "Bank Transfer" if any(x in t for x in ["bank","transfer","kpay","wave"]) else "Cash"
        desc = " ".join(parts[:3])
        return {
            "action": "record_expense",
            "description": desc,
            "category": exp_cat,
            "amount": nums[0],
            "payment_method": pay,
        }

    # ── ADD INVENTORY: beef/packaging ဝယ်လာ ─────────────────────────
    if any(kw in t for kw in ["ဝယ်လာ", "stock ထည့်", "add stock", "beef ဝယ်", "ကြက်သား"]):
        cat = "packaging" if any(x in t for x in ["bag", "pack", "ထုပ်"]) else "raw_material"
        item_name = "Raw Beef" if cat == "raw_material" else "Packaging Bags"
        unit = "pc" if cat == "packaging" else "kg"
        float_nums = [float(x) for x in re.findall(r"[\d]+\.?[\d]*", t)]
        return {
            "action": "add_inventory",
            "item": item_name,
            "category": cat,
            "quantity": float_nums[0] if float_nums else 0,
            "unit": unit,
            "unit_cost": int(float_nums[1]) if len(float_nums) > 1 else 0,
        }

    # ── QUERIES ───────────────────────────────────────────────────────
    if any(kw in t for kw in ["ရောင်းအား", "revenue", "sales", "ရောင်း"]):
        period = "today" if any(x in t for x in ["ဒီနေ့","today","နေ့"]) else "month"
        return {"action": "query_sales", "period": period}

    if any(kw in t for kw in ["profit", "loss", "margin", "pl", "p&l", "အမြတ်", "ဝင်ငွေ"]):
        return {"action": "query_pl", "period": "month"}

    if any(kw in t for kw in ["yield", "နှုန်း", "ကျပ်ကျပ်"]):
        return {"action": "query_yield"}

    if any(kw in t for kw in ["stock", "inventory", "လက်ကျန်", "ကြက်သားကျန်"]):
        return {"action": "query_stock"}

    if any(kw in t for kw in ["kpi", "dashboard", "summary", "report"]):
        return {"action": "query_kpi"}

    return {"action": "unknown"}

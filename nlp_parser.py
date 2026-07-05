import re

ITEM_MAP = {
    "20g": "Beef Jerky 20g", "20": "Beef Jerky 20g",
    "50g": "Beef Jerky 50g", "50": "Beef Jerky 50g",
    "100g": "Beef Jerky 100g", "100": "Beef Jerky 100g",
    "200g": "Beef Jerky 200g", "200": "Beef Jerky 200g",
}
CHANNEL_MAP = {
    "retail": "retail", "wholesale": "wholesale",
    "distributor": "distributor", "online": "online",
}
EXPENSE_CATS = {
    "marketing": "Marketing", "facebook": "Marketing",
    "rent": "Rent", "transport": "Transport/Delivery",
    "fuel": "Transport/Delivery", "labor": "Labor",
    "salary": "Labor", "electric": "Utilities",
    "packaging": "Packaging", "admin": "Admin/Office",
}

def _nums(text):
    return [int(x.replace(",", "")) for x in re.findall(r"[\d,]+", text)]

def parse_intent(text: str) -> dict:
    t = text.strip().lower()
    parts = text.strip().split()
    nums = _nums(t)

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

    if any(kw in t for kw in ["batch", "output", "→"]):
        batch_no = None
        for p in parts:
            if re.match(r"(batch|b)\d+", p.lower()):
                batch_no = p.upper()
        float_nums = [float(x) for x in re.findall(r"[\d]+\.?[\d]*", t)]
        return {
            "action": "record_batch",
            "batch_no": batch_no or "B001",
            "raw_beef_kg": float_nums[0] if float_nums else 0,
            "dried_output_kg": float_nums[1] if len(float_nums) > 1 else 0,
        }

    exp_cat = None
    for kw, cat in EXPENSE_CATS.items():
        if kw in t:
            exp_cat = cat
            break
    if exp_cat and nums:
        pay = "Bank Transfer" if any(x in t for x in ["bank","transfer","kpay"]) else "Cash"
        return {
            "action": "record_expense",
            "description": " ".join(parts[:3]),
            "category": exp_cat,
            "amount": nums[0],
            "payment_method": pay,
        }

    if any(kw in t for kw in ["ရောင်းအား", "revenue", "sales"]):
        period = "today" if any(x in t for x in ["ဒီနေ့","today"]) else "month"
        return {"action": "query_sales", "period": period}

    if any(kw in t for kw in ["profit", "loss", "margin", "pl", "အမြတ်"]):
        return {"action": "query_pl", "period": "month"}

    if any(kw in t for kw in ["yield", "နှုန်း"]):
        return {"action": "query_yield"}

    if any(kw in t for kw in ["stock", "inventory", "လက်ကျန်"]):
        return {"action": "query_stock"}

    if any(kw in t for kw in ["kpi", "dashboard", "report"]):
        return {"action": "query_kpi"}

    return {"action": "unknown"}
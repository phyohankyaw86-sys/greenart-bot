"""
GreenArt — Sale Engine (11-Step Auto Flow)
==========================================
Sale တစ်ခု မှတ်လိုက်တာနဲ့ အောက်ပါ အဆင့် ၁၁ ဆင့် အလိုအလျောက် ဖြစ်သည်:

  1.  Check Product     — item name valid ဆိုတာ စစ်
  2.  Check Inventory   — Finished Goods stock ရှိမရှိ စစ်
  3.  Deduct Stock      — Finished Goods ထဲက နှုတ်
  4.  Record Revenue    — sales table ထဲ မှတ်
  5.  Update Cash       — cash_in table update
  6.  Calculate COGS    — Assumptions ထဲက cost/gram သုံးပြီး တွက်
  7.  Calculate Profit  — Revenue − COGS = Gross Profit
  8.  Update KPI        — kpi_daily table update
  9.  Update Dashboard  — dashboard_cache table update
  10. Generate Alert    — threshold စစ်ပြီး alert_log ထဲ မှတ်
  11. Return Result     — Telegram bot ကို summary ပြန်ပို့

Free: PostgreSQL only. No external API.
"""

import os
from datetime import datetime, date
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()


# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────

VALID_ITEMS = {
    "Beef Jerky 20g":  {"grams": 20,  "category": "finished_goods"},
    "Beef Jerky 50g":  {"grams": 50,  "category": "finished_goods"},
    "Beef Jerky 100g": {"grams": 100, "category": "finished_goods"},
    "Beef Jerky 200g": {"grams": 200, "category": "finished_goods"},
}

# Thresholds for alerts
ALERT_THRESHOLDS = {
    "min_stock_packs":    10,     # finished goods below this → alert
    "min_cash_balance":   500000, # cash below 500k MMK → alert
    "min_gross_margin":   0.15,   # below 15% → alert
    "min_yield_pct":      0.50,   # below 50% → alert
}

CHANNEL_MAP = {
    "retail":      "Retail",
    "wholesale":   "Wholesale",
    "distributor": "Distributor",
    "online":      "Online",
}


def get_conn():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set")
    return psycopg2.connect(url)


# ─────────────────────────────────────────────
# EXTRA TABLES (call once at startup)
# ─────────────────────────────────────────────

def init_engine_tables():
    """Create extra tables needed by the engine if they don't exist."""
    conn = get_conn()
    c = conn.cursor()

    # Daily KPI snapshot
    c.execute("""
        CREATE TABLE IF NOT EXISTS kpi_daily (
            id             SERIAL PRIMARY KEY,
            date           DATE UNIQUE,
            total_revenue  INTEGER DEFAULT 0,
            total_cogs     INTEGER DEFAULT 0,
            gross_profit   INTEGER DEFAULT 0,
            gross_margin   NUMERIC DEFAULT 0,
            units_sold     INTEGER DEFAULT 0,
            orders         INTEGER DEFAULT 0,
            updated_at     TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Dashboard cache (latest snapshot for fast reads)
    c.execute("""
        CREATE TABLE IF NOT EXISTS dashboard_cache (
            key        TEXT PRIMARY KEY,
            value      TEXT,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Alert log
    c.execute("""
        CREATE TABLE IF NOT EXISTS alert_log (
            id         SERIAL PRIMARY KEY,
            date       DATE,
            level      TEXT,   -- 'RED' | 'YELLOW' | 'GREEN'
            category   TEXT,   -- 'Stock' | 'Cash' | 'Margin' | 'Yield'
            message    TEXT,
            resolved   BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# STEP HELPERS
# ─────────────────────────────────────────────

def _get_assumption(c, key, default=0):
    c.execute("SELECT value FROM assumptions WHERE key=%s", (key,))
    row = c.fetchone()
    return float(row[0]) if row else default


def _get_stock_qty(c, item):
    c.execute("SELECT quantity FROM inventory_current WHERE item=%s", (item,))
    row = c.fetchone()
    return float(row[0]) if row else 0.0


def _get_cost_per_gram(c, item_name):
    """
    Calculate COGS per gram from Assumptions.
    Formula mirrors Cost_Per_Batch sheet.
    """
    beef_price   = _get_assumption(c, "Beef Purchase Price per kg", 15000)
    beef_per_bat = _get_assumption(c, "Raw Beef per Batch (kg)", 5)
    seasoning    = _get_assumption(c, "Seasoning & Sauce Cost per batch", 5750)
    misc_pkg     = _get_assumption(c, "Misc Packaging (per batch)", 1500)
    labor_bat    = _get_assumption(c, "Labor Cost per Batch", 47500)
    util_bat     = _get_assumption(c, "Utilities Cost per Batch", 19875)
    yield_pct    = _get_assumption(c, "Expected Yield % (ကျပ်ကျပ်သားနှုန်း)", 0.6)

    grams = item_name.replace("Beef Jerky ", "").replace("g", "")
    pkg_cost_map = {
        "20":  _get_assumption(c, "Packaging — 20g bag (per pc)", 200),
        "50":  _get_assumption(c, "Packaging — 50g bag (per pc)", 350),
        "100": _get_assumption(c, "Packaging — 100g bag (per pc)", 600),
        "200": _get_assumption(c, "Packaging — 100g bag (per pc)", 600),
    }
    label_cost = _get_assumption(c, "Label / Sticker (per pc)", 50)
    pkg_per_pack = pkg_cost_map.get(grams, 350) + label_cost

    # Total batch cost
    raw_mat     = beef_price * beef_per_bat + seasoning
    pkg_batch   = misc_pkg   # misc only; per-pack pkg charged separately
    total_batch = raw_mat + pkg_batch + labor_bat + util_bat

    # Dried output
    dried_grams = beef_per_bat * yield_pct * 1000  # kg → g
    cost_per_g  = (total_batch / dried_grams) if dried_grams > 0 else 0

    return cost_per_g, pkg_per_pack


# ─────────────────────────────────────────────
# MAIN ENGINE FUNCTION
# ─────────────────────────────────────────────

def process_sale(customer: str, item: str, quantity: int, unit_price: int,
                 channel: str = "retail", delivery_ch: str = "Direct",
                 delivery_fee: int = 0, delivery_inc: int = 0,
                 sale_date: str = None) -> dict:
    """
    Full 11-step sale processing.
    Returns a result dict with all computed values + alerts list.
    """
    today = sale_date or datetime.now().strftime("%Y-%m-%d")
    alerts = []
    result = {
        "success":       False,
        "step_reached":  0,
        "customer":      customer,
        "item":          item,
        "quantity":      quantity,
        "unit_price":    unit_price,
        "channel":       channel,
        "alerts":        [],
        "error":         None,
    }

    conn = get_conn()
    c    = conn.cursor()

    try:

        # ── STEP 1: Check Product ────────────────────────────────────────
        result["step_reached"] = 1
        if item not in VALID_ITEMS:
            # Try fuzzy match
            item_lower = item.lower()
            for valid in VALID_ITEMS:
                if valid.lower() in item_lower or item_lower in valid.lower():
                    item = valid
                    break
            else:
                result["error"] = (
                    f"❌ Product '{item}' မတွေ့ပါ။\n"
                    f"Valid: {', '.join(VALID_ITEMS.keys())}"
                )
                return result

        product_info = VALID_ITEMS[item]
        grams_per_pack = product_info["grams"]
        result["item"] = item

        # ── STEP 2: Check Inventory ──────────────────────────────────────
        result["step_reached"] = 2
        stock_qty = _get_stock_qty(c, item)

        if stock_qty < quantity:
            # Soft warning — still allow sale (might produce to order)
            alerts.append({
                "level":    "YELLOW",
                "category": "Stock",
                "message":  (
                    f"⚠️ {item} stock နည်းနေ — "
                    f"လက်ကျန်: {stock_qty:.0f} ထုပ်, "
                    f"ရောင်းချမည်: {quantity} ထုပ်"
                ),
            })

        # ── STEP 3: Deduct Finished Goods ───────────────────────────────
        result["step_reached"] = 3
        new_stock = stock_qty - quantity
        c.execute("""
            INSERT INTO inventory_current (item, category, quantity, unit, updated_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (item) DO UPDATE SET
              quantity   = inventory_current.quantity - %s,
              updated_at = NOW()
        """, (item, "finished_goods", -quantity, "pcs", quantity))

        c.execute("""
            INSERT INTO inventory_log
              (date, item, category, stock_out, unit, closing_stock)
            VALUES (CURRENT_DATE, %s, %s, %s, %s, %s)
        """, (item, "finished_goods", quantity, "pcs", new_stock))

        result["stock_after"] = float(new_stock)

        # ── STEP 4: Record Revenue ───────────────────────────────────────
        result["step_reached"] = 4
        subtotal      = quantity * unit_price
        total_revenue = subtotal + delivery_inc

        c.execute("""
            INSERT INTO sales
              (date, customer, channel, delivery_ch, delivery_fee,
               item, quantity, unit_price, subtotal, delivery_inc, total_revenue)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (today, customer, CHANNEL_MAP.get(channel, channel),
              delivery_ch, delivery_fee,
              item, quantity, unit_price,
              subtotal, delivery_inc, total_revenue))

        sale_id = c.fetchone()[0]
        result["sale_id"]      = sale_id
        result["subtotal"]     = subtotal
        result["total_revenue"]= total_revenue

        # ── STEP 5: Update Cash ──────────────────────────────────────────
        result["step_reached"] = 5
        ch_col = {
            "Retail":      "retail_mmk",
            "Wholesale":   "wholesale_mmk",
            "Distributor": "dist_mmk",
        }.get(CHANNEL_MAP.get(channel, channel), "retail_mmk")

        c.execute(f"""
            INSERT INTO cash_in (date, {ch_col}, total_in)
            VALUES (%s, %s, %s)
            ON CONFLICT (date) DO UPDATE SET
              {ch_col}  = cash_in.{ch_col} + EXCLUDED.{ch_col},
              total_in  = cash_in.total_in + EXCLUDED.total_in
        """, (today, total_revenue, total_revenue))

        # ── STEP 6: Calculate COGS ───────────────────────────────────────
        result["step_reached"] = 6
        cost_per_g, pkg_per_pack = _get_cost_per_gram(c, item)
        cogs_per_pack = (cost_per_g * grams_per_pack) + pkg_per_pack
        total_cogs    = round(cogs_per_pack * quantity)

        result["cogs_per_pack"] = round(cogs_per_pack, 1)
        result["total_cogs"]    = total_cogs

        # ── STEP 7: Calculate Profit ─────────────────────────────────────
        result["step_reached"] = 7
        gross_profit  = total_revenue - total_cogs
        gross_margin  = round(gross_profit / total_revenue, 4) if total_revenue > 0 else 0

        result["gross_profit"] = gross_profit
        result["gross_margin"] = round(gross_margin * 100, 1)

        if gross_margin < ALERT_THRESHOLDS["min_gross_margin"]:
            alerts.append({
                "level":    "RED",
                "category": "Margin",
                "message":  (
                    f"🔴 Gross Margin နည်းနေ — "
                    f"{result['gross_margin']}% "
                    f"(Threshold: {ALERT_THRESHOLDS['min_gross_margin']*100:.0f}%)"
                ),
            })

        # ── STEP 8: Update KPI ───────────────────────────────────────────
        result["step_reached"] = 8
        c.execute("""
            INSERT INTO kpi_daily
              (date, total_revenue, total_cogs, gross_profit,
               gross_margin, units_sold, orders)
            VALUES (%s,%s,%s,%s,%s,%s,1)
            ON CONFLICT (date) DO UPDATE SET
              total_revenue = kpi_daily.total_revenue + EXCLUDED.total_revenue,
              total_cogs    = kpi_daily.total_cogs    + EXCLUDED.total_cogs,
              gross_profit  = kpi_daily.gross_profit  + EXCLUDED.gross_profit,
              gross_margin  = CASE
                WHEN (kpi_daily.total_revenue + EXCLUDED.total_revenue) > 0
                THEN ROUND(
                  (kpi_daily.gross_profit + EXCLUDED.gross_profit)::NUMERIC /
                  (kpi_daily.total_revenue + EXCLUDED.total_revenue), 4)
                ELSE 0 END,
              units_sold    = kpi_daily.units_sold + EXCLUDED.units_sold,
              orders        = kpi_daily.orders + 1,
              updated_at    = NOW()
        """, (today, total_revenue, total_cogs, gross_profit,
              gross_margin, quantity))

        # ── STEP 9: Update Dashboard Cache ──────────────────────────────
        result["step_reached"] = 9

        # Get today's running totals for cache
        c.execute("""
            SELECT total_revenue, gross_profit, gross_margin, units_sold, orders
            FROM kpi_daily WHERE date = %s
        """, (today,))
        kpi_row = c.fetchone()
        if kpi_row:
            cache_data = {
                "today_revenue":  kpi_row[0],
                "today_gp":       kpi_row[1],
                "today_margin":   float(kpi_row[2]) * 100,
                "today_units":    kpi_row[3],
                "today_orders":   kpi_row[4],
                "last_updated":   datetime.now().isoformat(),
            }
            for key, val in cache_data.items():
                c.execute("""
                    INSERT INTO dashboard_cache (key, value, updated_at)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (key) DO UPDATE SET
                      value = EXCLUDED.value, updated_at = NOW()
                """, (key, str(val)))

        # ── STEP 10: Generate Alerts ─────────────────────────────────────
        result["step_reached"] = 10

        # Stock alert
        if new_stock < ALERT_THRESHOLDS["min_stock_packs"]:
            alerts.append({
                "level":    "RED",
                "category": "Stock",
                "message":  (
                    f"🔴 {item} stock အနည်းဆုံးထဲ ရောက်နေပြီ — "
                    f"လက်ကျန်: {new_stock:.0f} ထုပ်သာ ကျန်"
                ),
            })

        # Cash alert
        c.execute("""
            SELECT COALESCE(SUM(total_in),0) - COALESCE(
              (SELECT SUM(total_out) FROM cash_out
               WHERE DATE_TRUNC('month',date)=DATE_TRUNC('month',CURRENT_DATE)),0)
            FROM cash_in
            WHERE DATE_TRUNC('month',date)=DATE_TRUNC('month',CURRENT_DATE)
        """)
        cash_balance = c.fetchone()[0] or 0
        if cash_balance < ALERT_THRESHOLDS["min_cash_balance"]:
            alerts.append({
                "level":    "RED",
                "category": "Cash",
                "message":  (
                    f"🔴 Cash Balance နည်းနေ — "
                    f"{int(cash_balance):,} ကျပ် "
                    f"(Threshold: {ALERT_THRESHOLDS['min_cash_balance']:,} ကျပ်)"
                ),
            })

        # Save alerts to DB
        for alert in alerts:
            c.execute("""
                INSERT INTO alert_log (date, level, category, message)
                VALUES (%s,%s,%s,%s)
            """, (today, alert["level"], alert["category"], alert["message"]))

        result["alerts"] = alerts

        # ── STEP 11: Commit + Return Result ─────────────────────────────
        result["step_reached"] = 11
        conn.commit()
        result["success"] = True

    except Exception as e:
        conn.rollback()
        result["error"] = f"❌ Step {result['step_reached']} မှာ error: {str(e)}"

    finally:
        conn.close()

    return result


# ─────────────────────────────────────────────
# TELEGRAM REPLY FORMATTER
# ─────────────────────────────────────────────

def format_sale_reply(r: dict) -> str:
    """Format the engine result into a clean Telegram message."""
    if not r["success"]:
        return r.get("error", "❌ Unknown error")

    lines = [
        "✅ *ရောင်းအား မှတ်တမ်းတင်ပြီ!*\n",
        f"👤 ဖောက်သည်:   {r['customer']}",
        f"📦 ပစ္စည်း:     {r['item']}",
        f"🔢 အရေအတွက်:  {r['quantity']} ထုပ်",
        f"💵 Unit Price: {r['unit_price']:,} ကျပ်",
        f"💰 Revenue:    {r['total_revenue']:,} ကျပ်",
        "",
        f"📊 *Cost Analysis*",
        f"  COGS/pack:   {r['cogs_per_pack']:,.0f} ကျပ်",
        f"  Total COGS:  {r['total_cogs']:,} ကျပ်",
        f"  Gross Profit:{r['gross_profit']:,} ကျပ်",
        f"  Margin:      {r['gross_margin']}%",
        "",
        f"📦 Stock လက်ကျန်: {r.get('stock_after', '?'):.0f} ထုပ်",
    ]

    if r["alerts"]:
        lines.append("")
        lines.append("🚨 *Alerts*")
        for a in r["alerts"]:
            lines.append(f"  {a['message']}")

    return "\n".join(lines)


# ─────────────────────────────────────────────
# DASHBOARD CACHE READER
# ─────────────────────────────────────────────

def get_dashboard_cache() -> dict:
    """Fast dashboard read from cache table."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT key, value FROM dashboard_cache")
    rows = c.fetchall()
    conn.close()
    cache = {k: v for k, v in rows}
    return {
        "today_revenue": int(float(cache.get("today_revenue", 0))),
        "today_gp":      int(float(cache.get("today_gp", 0))),
        "today_margin":  float(cache.get("today_margin", 0)),
        "today_units":   int(float(cache.get("today_units", 0))),
        "today_orders":  int(float(cache.get("today_orders", 0))),
        "last_updated":  cache.get("last_updated", "-"),
    }


def get_unresolved_alerts() -> list:
    """Get all unresolved alerts for Telegram /alerts command."""
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("""
        SELECT date, level, category, message
        FROM alert_log
        WHERE resolved = FALSE
        ORDER BY created_at DESC
        LIMIT 20
    """)
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]
"""
GreenArt Beef Jerky — AI Telegram Bot + Flask Dashboard
=========================================================
Telegram: Natural Burmese/English NLP (local rule-based + optional Claude)
Flask:    Executive dashboard on PORT env var

Commands:
  ဒီနေ့ ရောင်းအား
  MaHla 100g 10 5000 retail
  Batch001 beef 5kg → 2.8kg
  Marketing 50000 cash
  beef 10kg ဝယ်လာ 15000
  /report /kpi /pl /stock /yield /alerts /help
"""

import os, asyncio, threading, json
from datetime import datetime
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from flask import Flask, render_template_string

from database import (
    init_db, get_monthly_summary, get_kpi, get_pl_summary,
    get_dashboard_kpi, save_production_batch, save_yield, save_expense,
    add_stock, use_stock, get_stock, get_low_stock, get_yield_summary,
    get_today_revenue, get_assumption,
)
from nlp_parser import parse_intent
from sale_engine import (
    process_sale, format_sale_reply,
    init_engine_tables, get_unresolved_alerts,
)

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

init_db()
init_engine_tables()


# ── BOT HANDLERS ──────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context):
    await update.message.reply_text(
        "🥩 *GreenArt Beef Jerky AI Bot*\n\n"
        "ဘာမဆို ရိုက်ပါ — AI ကပဲ နားလည်ပေးပါမည်!\n\n"
        "📝 *ဥပမာများ:*\n"
        "• `MaHla 100g 10 5000 retail` — ရောင်းအားမှတ်\n"
        "• `ဒီနေ့ ရောင်းအား` — Revenue ကြည့်\n"
        "• `ဒီလ profit` — P&L ကြည့်\n"
        "• `Batch001 5kg beef → 3kg` — Batch မှတ်\n"
        "• `Marketing 50000 cash` — Expense မှတ်\n"
        "• `beef 10kg ဝယ်လာ 15000` — Stock ထည့်\n"
        "• `yield ဘယ်လောက်ရှိလဲ` — Yield ကြည့်\n\n"
        "/report /kpi /pl /stock /yield /alerts",
        parse_mode="Markdown"
    )


async def cmd_report(update: Update, context):
    count, rev = get_monthly_summary()
    today = get_today_revenue()
    await update.message.reply_text(
        f"📊 *Monthly Report*\n\n"
        f"ဒီနေ့ Revenue:  `{today:>12,}` ကျပ်\n"
        f"ဒီလ Revenue:   `{rev:>12,}` ကျပ်\n"
        f"ရောင်းချမှု:     `{count:>12,}` ကြိမ်",
        parse_mode="Markdown"
    )


async def cmd_kpi(update: Update, context):
    items, channels, top_customers = get_kpi()
    msg = "📊 *KPI Summary*\n\n"
    msg += "🥩 *Product အလိုက်:*\n"
    for item, qty, total in items:
        msg += f"  {item}: `{qty}` ထုပ် — `{total:,}` ကျပ်\n"
    msg += "\n📦 *Channel အလိုက်:*\n"
    for ch, total in channels:
        msg += f"  {ch}: `{total:,}` ကျပ်\n"
    msg += "\n🏆 *Top Customers:*\n"
    for cust, total in top_customers:
        msg += f"  {cust}: `{total:,}` ကျပ်\n"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_pl(update: Update, context):
    d = get_pl_summary()
    await update.message.reply_text(
        f"💰 *Profit & Loss (ဒီလ)*\n\n"
        f"📈 Revenue:        `{d['revenue']:>12,}` ကျပ်\n"
        f"➖ COGS:           `({d['cogs']:>11,})` ကျပ်\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Gross Profit:   `{d['gross_profit']:>12,}` ကျပ်  ({d['gp_margin']}%)\n"
        f"➖ OpEx:           `({d['opex']:>11,})` ကျပ်\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Net Profit:     `{d['net_profit']:>12,}` ကျပ်  ({d['net_margin']}%)",
        parse_mode="Markdown"
    )


async def cmd_stock(update: Update, context):
    rows = get_stock()
    low  = get_low_stock()
    if not rows:
        await update.message.reply_text("📦 Stock data မရှိသေးပါ")
        return
    msg = "📦 *Stock Level*\n\n"
    cat_labels = {
        "raw_material":  "🥩 Raw Material",
        "packaging":     "📦 Packaging",
        "finished_goods":"✅ Finished Goods",
    }
    current = None
    for item, cat, qty, unit, cost, val in rows:
        if cat != current:
            msg += f"\n*{cat_labels.get(cat, cat)}:*\n"
            current = cat
        warn = " ⚠️" if float(qty) <= 5 else ""
        msg += f"  {item}: `{qty} {unit}`  (Value: `{int(val):,}` ကျပ်){warn}\n"
    if low:
        msg += f"\n🔴 *Low Stock Alert ({len(low)} items):*\n"
        for item, cat, qty, unit, *_ in low:
            msg += f"  ⚠️ {item}: `{qty} {unit}` — ဝယ်ဖို့ လိုပြီ!\n"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_yield(update: Update, context):
    d = get_yield_summary()
    if not d or not d.get("batches"):
        await update.message.reply_text("🌡️ Batch data မရှိသေးပါ")
        return
    target = get_assumption("Expected Yield % (ကျပ်ကျပ်သားနှုန်း)", 0.6) * 100
    avg    = float(d.get("avg_yield_pct") or 0)
    diff   = round(avg - target, 1)
    arrow  = "🟢 +" if diff >= 0 else "🔴 "
    await update.message.reply_text(
        f"🌡️ *Yield Tracking Summary*\n\n"
        f"Batches logged:    `{d['batches']}`\n"
        f"Target Yield %:    `{target}%`\n"
        f"Average Actual %:  `{avg}%`  {arrow}{diff}%\n"
        f"Best Batch:        `{d['best_yield_pct']}%`\n"
        f"Worst Batch:       `{d['worst_yield_pct']}%`\n"
        f"Total Raw (kg):    `{d['total_raw_kg']}`\n"
        f"Total Output (kg): `{d['total_output_kg']}`",
        parse_mode="Markdown"
    )


async def cmd_alerts(update: Update, context):
    rows = get_unresolved_alerts()
    if not rows:
        await update.message.reply_text(
            "✅ *Alerts မရှိပါ — ပုံမှန် လည်ပတ်နေသည်*",
            parse_mode="Markdown"
        )
        return
    msg = f"🚨 *Alerts ({len(rows)} ခု)*\n\n"
    for a in rows:
        msg += f"{a['message']}\n"
        msg += f"  _({a['date']} · {a['category']})_\n\n"
    await update.message.reply_text(msg, parse_mode="Markdown")


# ── NLP MESSAGE HANDLER ───────────────────────────────────────────────────────

async def handle_message(update: Update, context):
    text = update.message.text.strip()
    if not text:
        return

    # Fast-path: "Name size qty price [channel]"
    parts = text.split()
    if (len(parts) >= 4
            and any(g in parts[1].lower() for g in ["20g","50g","100g","200g"])
            and parts[2].isdigit() and parts[3].isdigit()):
        r = process_sale(
            customer   = parts[0],
            item       = f"Beef Jerky {parts[1].upper()}",
            quantity   = int(parts[2]),
            unit_price = int(parts[3]),
            channel    = parts[4] if len(parts) > 4 else "retail",
        )
        await update.message.reply_text(format_sale_reply(r), parse_mode="Markdown")
        return

    intent = parse_intent(text)
    action = intent.get("action", "unknown")

    try:
        date = datetime.now().strftime("%Y-%m-%d")

        if action == "record_sale":
            r = process_sale(
                customer    = intent.get("customer", "Unknown"),
                item        = intent.get("item", "Beef Jerky 100g"),
                quantity    = int(intent.get("quantity", 1)),
                unit_price  = int(intent.get("unit_price", 0)),
                channel     = intent.get("channel", "retail"),
                delivery_ch = intent.get("delivery_ch", "Direct"),
                delivery_fee= int(intent.get("delivery_fee", 0)),
                sale_date   = date,
            )
            await update.message.reply_text(format_sale_reply(r), parse_mode="Markdown")

        elif action == "record_batch":
            bn  = intent.get("batch_no") or f"B{datetime.now().strftime('%Y%m%d%H%M')}"
            raw = float(intent.get("raw_beef_kg", 0))
            dry = float(intent.get("dried_output_kg", 0))
            labor   = get_assumption("Labor Cost per Batch",              47500)
            util    = get_assumption("Utilities Cost per Batch",          19875)
            beef_p  = get_assumption("Beef Purchase Price per kg",        15000)
            season  = get_assumption("Seasoning & Sauce Cost per batch",   5750)
            pkg     = get_assumption("Misc Packaging (per batch)",          1500)
            raw_mat = int(raw * beef_p + season)
            total, cpg = save_production_batch(
                date, bn, raw, dry, raw_mat, int(pkg), int(labor), int(util)
            )
            actual_y = save_yield(date, bn, raw, dry,
                                  get_assumption("Expected Yield % (ကျပ်ကျပ်သားနှုန်း)", 0.6))
            await update.message.reply_text(
                f"✅ *Batch မှတ်တမ်းတင်ပြီ!*\n\n"
                f"Batch No:        `{bn}`\n"
                f"Raw Beef Input:  `{raw} kg`\n"
                f"Dried Output:    `{dry} kg`\n"
                f"Actual Yield:    `{round(actual_y*100,1)}%`\n"
                f"Total Cost:      `{total:,}` ကျပ်\n"
                f"Cost per Gram:   `{cpg:.2f}` ကျပ်/g",
                parse_mode="Markdown"
            )

        elif action == "record_expense":
            save_expense(
                date,
                intent.get("description", ""),
                intent.get("category", "Other"),
                int(intent.get("amount", 0)),
                intent.get("payment_method", "Cash"),
            )
            await update.message.reply_text(
                f"✅ *Expense မှတ်ပြီ!*\n"
                f"{intent.get('description')} — {intent.get('category')}\n"
                f"Amount: `{int(intent.get('amount',0)):,}` ကျပ်",
                parse_mode="Markdown"
            )

        elif action == "add_inventory":
            add_stock(
                intent.get("item", "Unknown"),
                intent.get("category", "raw_material"),
                float(intent.get("quantity", 0)),
                intent.get("unit", "kg"),
                int(intent.get("unit_cost", 0)),
            )
            await update.message.reply_text(
                f"✅ *Stock ထည့်ပြီ!*\n"
                f"{intent.get('item')} — `{intent.get('quantity')} {intent.get('unit')}`\n"
                f"Unit Cost: `{int(intent.get('unit_cost',0)):,}` ကျပ်",
                parse_mode="Markdown"
            )

        elif action == "use_inventory":
            remaining = use_stock(
                intent.get("item", "Unknown"),
                intent.get("category", "raw_material"),
                float(intent.get("quantity", 0)),
                intent.get("unit", "kg"),
            )
            warn = "\n⚠️ Low stock — ဝယ်ဖို့ လိုပြီ!" if float(remaining) < 5 else ""
            await update.message.reply_text(
                f"✅ Stock သုံးမှတ်ပြီ!\n"
                f"လက်ကျန်: `{remaining} {intent.get('unit','')}`{warn}",
                parse_mode="Markdown"
            )

        elif action == "query_sales":
            if intent.get("period") == "today":
                rev = get_today_revenue()
                await update.message.reply_text(
                    f"📊 *ဒီနေ့ Revenue*\n\n`{rev:,}` ကျပ်",
                    parse_mode="Markdown"
                )
            else:
                count, rev = get_monthly_summary()
                await update.message.reply_text(
                    f"📊 *ဒီလ Revenue*\n\n"
                    f"Revenue: `{rev:,}` ကျပ်\n"
                    f"Orders:  `{count}` ကြိမ်",
                    parse_mode="Markdown"
                )

        elif action == "query_pl":
            await cmd_pl(update, context)
        elif action == "query_yield":
            await cmd_yield(update, context)
        elif action == "query_stock":
            await cmd_stock(update, context)
        elif action == "query_kpi":
            await cmd_kpi(update, context)
        else:
            await update.message.reply_text(
                "❓ နားမလည်ပါ။ ဥပမာများ:\n"
                "• `MaHla 100g 5 4500 retail`\n"
                "• `ဒီနေ့ ရောင်းအား`\n"
                "• `Batch001 5kg beef 2.8kg output`\n"
                "• `Marketing 50000 cash`\n"
                "/help နှိပ်ပါ",
                parse_mode="Markdown"
            )

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


# ── FLASK DASHBOARD ───────────────────────────────────────────────────────────

flask_app = Flask(__name__)

DASH_HTML = """<!DOCTYPE html>
<html lang="my">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GreenArt Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Arial,sans-serif;background:#f0f4f0;color:#222}
.topbar{background:#1a5c38;color:#fff;padding:14px 24px;display:flex;align-items:center;gap:12px}
.topbar h1{font-size:18px;font-weight:700}
.topbar .ts{font-size:13px;opacity:.8;margin-left:auto}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;padding:20px}
.card{background:#fff;border-radius:12px;padding:16px;box-shadow:0 2px 8px rgba(0,0,0,.07)}
.card .label{font-size:11px;color:#666;margin-bottom:6px;text-transform:uppercase;letter-spacing:.5px}
.card .value{font-size:22px;font-weight:700;color:#1a5c38}
.card .value.red{color:#c62828}
.card .value.blue{color:#1565c0}
.section{margin:0 20px 20px;background:#fff;border-radius:12px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,.07)}
.section h2{font-size:15px;font-weight:700;color:#1a5c38;margin-bottom:14px;border-bottom:2px solid #e8f5e9;padding-bottom:8px}
.pl-row{display:flex;justify-content:space-between;padding:8px 0;font-size:14px;border-bottom:1px solid #f5f5f5}
.pl-row.total{font-weight:700;font-size:16px;color:#1a5c38;border-top:2px solid #1a5c38;border-bottom:none;margin-top:4px;padding-top:10px}
.pl-row.minus{color:#c62828}
.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;margin:0 20px 20px}
.chart-card{background:#fff;border-radius:12px;padding:16px;box-shadow:0 2px 8px rgba(0,0,0,.07)}
.alert-item{background:#fff3f3;border-left:4px solid #c62828;border-radius:6px;padding:10px 14px;margin-bottom:8px;font-size:13px}
.alert-ok{background:#f1f8f1;border-left-color:#1a5c38}
.footer{text-align:center;font-size:12px;color:#999;padding:16px}
</style>
</head>
<body>
<div class="topbar">
  <div>🥩</div>
  <h1>GreenArt Beef Jerky — Executive Dashboard</h1>
  <span class="ts">Live · {{ts}}</span>
</div>

<div class="grid">
  <div class="card"><div class="label">ဒီနေ့ Revenue</div><div class="value">{{today_rev}}</div></div>
  <div class="card"><div class="label">ဒီလ Revenue</div><div class="value">{{month_rev}}</div></div>
  <div class="card"><div class="label">Gross Profit</div><div class="value">{{gp}}</div></div>
  <div class="card"><div class="label">Net Profit</div><div class="value {{net_cls}}">{{net}}</div></div>
  <div class="card"><div class="label">Net Margin</div><div class="value blue">{{margin}}%</div></div>
  <div class="card"><div class="label">Avg Yield %</div><div class="value {{yield_cls}}">{{yield_pct}}%</div></div>
  <div class="card"><div class="label">Inventory Value</div><div class="value blue">{{inv_val}}</div></div>
  <div class="card"><div class="label">Batches (ဒီလ)</div><div class="value">{{batches}}</div></div>
</div>

<div class="section">
  <h2>💰 Profit &amp; Loss Statement (ဒီလ)</h2>
  <div class="pl-row"><span>📈 Revenue</span><span>{{revenue}} ကျပ်</span></div>
  <div class="pl-row minus"><span>➖ COGS (Production)</span><span>({{cogs}}) ကျပ်</span></div>
  <div class="pl-row"><span>✅ Gross Profit</span><span>{{gp_val}} ကျပ্  ({{gp_margin}}%)</span></div>
  <div class="pl-row minus"><span>➖ Operating Expenses</span><span>({{opex}}) ကျပ်</span></div>
  <div class="pl-row total"><span>🏆 Net Profit</span><span>{{net_val}} ကျပ်  ({{net_margin}}%)</span></div>
</div>

<div class="charts">
  <div class="chart-card"><canvas id="cProduct"></canvas></div>
  <div class="chart-card"><canvas id="cChannel"></canvas></div>
  <div class="chart-card" style="grid-column:span 2"><canvas id="cDaily"></canvas></div>
</div>

<div class="section" style="margin:0 20px 20px">
  <h2>🚨 Alerts</h2>
  {{alerts_html}}
</div>

<div class="footer">GreenArt Beef Jerky · AI Dashboard · {{ts}}</div>

<script>
const G=['#1a5c38','#2e7d4f','#4caf76','#81c995','#c8e6c9'];
new Chart(document.getElementById('cProduct'),{type:'bar',data:{
  labels:{{product_labels}},
  datasets:[{label:'Revenue (ကျပ်)',data:{{product_data}},backgroundColor:'#1a5c38'}]
},options:{plugins:{title:{display:true,text:'Product အလိုက် Revenue'}},responsive:true}});

new Chart(document.getElementById('cChannel'),{type:'doughnut',data:{
  labels:{{channel_labels}},
  datasets:[{data:{{channel_data}},backgroundColor:G}]
},options:{plugins:{title:{display:true,text:'Channel Share'}},responsive:true}});

new Chart(document.getElementById('cDaily'),{type:'line',data:{
  labels:{{daily_labels}},
  datasets:[{label:'Daily Revenue',data:{{daily_data}},
    borderColor:'#1a5c38',tension:.3,fill:true,backgroundColor:'rgba(26,92,56,.1)'}]
},options:{plugins:{title:{display:true,text:'နေ့စဉ် Revenue Trend'}},responsive:true}});
</script>
</body>
</html>"""


@flask_app.route("/")
def dashboard():
    try:
        kpi   = get_dashboard_kpi()
        pl    = get_pl_summary()
        items, channels, _ = get_kpi()

        # Daily trend from sales table
        try:
            from database import get_conn as _gc
            conn = _gc(); c = conn.cursor()
            c.execute("SELECT date, SUM(total_revenue) FROM sales GROUP BY date ORDER BY date DESC LIMIT 30")
            daily_raw = list(reversed(c.fetchall())); conn.close()
        except Exception:
            daily_raw = []

        def fmt(n): return f"{int(n):,}"
        net_cls   = "red" if pl["net_profit"] < 0 else ""
        yield_cls = "red" if kpi["avg_yield_pct"] < 55 else ""

        alerts = []
        if kpi["cash_balance"] < 1_000_000:
            alerts.append(("❌", f"Cash Balance နည်းနေ: {fmt(kpi['cash_balance'])} ကျပ်"))
        if kpi["avg_yield_pct"] and kpi["avg_yield_pct"] < 55:
            alerts.append(("❌", f"Yield ကျနေ: {kpi['avg_yield_pct']}% (Target: 60%)"))
        if pl["net_margin"] < 0:
            alerts.append(("❌", f"Loss ဖြစ်နေ: Net Margin {pl['net_margin']}%"))
        for item, cat, qty, unit, *_ in get_low_stock(3):
            alerts.append(("⚠️", f"Low Stock: {item} — {qty} {unit}"))
        if not alerts:
            alerts.append(("✅", "ပြဿနာ မတွေ့ — ပုံမှန် လည်ပတ်နေ"))

        alerts_html = "\n".join(
            f'<div class="alert-item {"alert-ok" if e=="✅" else ""}">{e} {msg}</div>'
            for e, msg in alerts
        )

        html = DASH_HTML
        for k, v in {
            "{{ts}}":             datetime.now().strftime("%Y-%m-%d %H:%M"),
            "{{today_rev}}":      fmt(kpi["today_revenue"]),
            "{{month_rev}}":      fmt(kpi["month_revenue"]),
            "{{gp}}":             fmt(pl["gross_profit"]),
            "{{net}}":            fmt(pl["net_profit"]),
            "{{net_cls}}":        net_cls,
            "{{yield_cls}}":      yield_cls,
            "{{yield_pct}}":      str(kpi["avg_yield_pct"]),
            "{{inv_val}}":        fmt(kpi["inventory_value"]),
            "{{batches}}":        str(kpi["month_batches"]),
            "{{revenue}}":        fmt(pl["revenue"]),
            "{{cogs}}":           fmt(pl["cogs"]),
            "{{gp_val}}":         fmt(pl["gross_profit"]),
            "{{gp_margin}}":      str(pl["gp_margin"]),
            "{{opex}}":           fmt(pl["opex"]),
            "{{net_val}}":        fmt(pl["net_profit"]),
            "{{net_margin}}":     str(pl["net_margin"]),
            "{{alerts_html}}":    alerts_html,
            "{{product_labels}}": str([r[0] for r in items]),
            "{{product_data}}":   str([r[2] for r in items]),
            "{{channel_labels}}": str([r[0] for r in channels]),
            "{{channel_data}}":   str([r[1] for r in channels]),
            "{{daily_labels}}":   str([str(r[0]) for r in daily_raw]),
            "{{daily_data}}":     str([r[1] for r in daily_raw]),
        }.items():
            html = html.replace(k, str(v))
        return html

    except Exception as e:
        return (f"<h2 style='color:red;padding:20px'>Dashboard Error: {e}</h2>"
                f"<p style='padding:20px'>DATABASE_URL စစ်ပါ / init_db() ပြေးပါ</p>")


def run_flask():
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port, use_reloader=False)


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

async def run_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_start))
    app.add_handler(CommandHandler("report",  cmd_report))
    app.add_handler(CommandHandler("kpi",     cmd_kpi))
    app.add_handler(CommandHandler("pl",      cmd_pl))
    app.add_handler(CommandHandler("stock",   cmd_stock))
    app.add_handler(CommandHandler("yield",   cmd_yield))
    app.add_handler(CommandHandler("alerts",  cmd_alerts))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 Bot running...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()


if __name__ == "__main__":
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    print(f"🌐 Dashboard: http://localhost:{os.environ.get('PORT', 5000)}")
    asyncio.run(run_bot())

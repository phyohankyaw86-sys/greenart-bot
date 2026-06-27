import os
import asyncio
import threading
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from database import init_db, save_sale, get_monthly_summary, get_kpi, get_pl_summary
from datetime import datetime
from flask import Flask, render_template_string
import sqlite3

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
init_db()

flask_app = Flask(__name__)

def get_data():
    try:
        conn = sqlite3.connect("greenart.db")
        c = conn.cursor()
        c.execute("SELECT SUM(total), COUNT(*) FROM sales")
        revenue, count = c.fetchone()
        c.execute("SELECT item, SUM(total) FROM sales GROUP BY item")
        items = c.fetchall()
        c.execute("SELECT channel, SUM(total) FROM sales GROUP BY channel")
        channels = c.fetchall()
        c.execute("SELECT SUM(total_cost) FROM production")
        prod_cost = c.fetchone()[0] or 0
        c.execute("SELECT value FROM assumptions WHERE key='Monthly Labor Cost (Total)'")
        row = c.fetchone()
        labor = row[0] if row else 0
        c.execute("SELECT value FROM assumptions WHERE key='Utilities Cost per Month'")
        row = c.fetchone()
        utilities = row[0] if row else 0
        conn.close()
        revenue = revenue or 0
        net_profit = revenue - prod_cost - labor - utilities
        margin = round((net_profit / revenue * 100), 1) if revenue > 0 else 0
        return {
            "revenue": int(revenue), "count": count or 0,
            "prod_cost": int(prod_cost), "labor": int(labor),
            "utilities": int(utilities),
            "gross_profit": int(revenue - prod_cost),
            "net_profit": int(net_profit),
            "margin": margin, "items": items, "channels": channels
        }
    except:
        return {
            "revenue": 0, "count": 0, "prod_cost": 0, "labor": 0,
            "utilities": 0, "gross_profit": 0, "net_profit": 0,
            "margin": 0, "items": [], "channels": []
        }

HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>GreenArt</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>body{font-family:Arial;background:#f0f2f5;padding:16px}h1{color:#2d7a2d;text-align:center}
.cards{display:flex;flex-wrap:wrap;gap:12px;justify-content:center;margin:20px 0}
.card{background:white;border-radius:12px;padding:16px 20px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,.08);flex:1;min-width:140px}
.card h2{font-size:22px;color:#2d7a2d;margin-bottom:4px}.card p{color:#888;font-size:13px}
.pl{background:white;border-radius:12px;padding:20px;margin-bottom:20px;box-shadow:0 2px 8px rgba(0,0,0,.08)}
.pl h3{color:#2d7a2d;margin-bottom:12px}
.row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #f0f0f0;font-size:14px}
.row.total{font-weight:bold;border-top:2px solid #2d7a2d;border-bottom:none;color:#2d7a2d}
.row.minus{color:#e53935}
.charts{display:flex;flex-wrap:wrap;gap:16px;justify-content:center}
.chart{background:white;border-radius:12px;padding:16px;box-shadow:0 2px 8px rgba(0,0,0,.08);width:100%;max-width:420px}
</style></head><body>
<h1>🥩 GreenArt Beef Jerky Dashboard</h1>
<div class="cards">
<div class="card"><h2>{{revenue}}</h2><p>Revenue (ကျပ်)</p></div>
<div class="card"><h2>{{count}}</h2><p>ရောင်းချမှု</p></div>
<div class="card"><h2>{{net_profit}}</h2><p>Net Profit (ကျပ်)</p></div>
<div class="card"><h2>{{margin}}%</h2><p>Net Margin</p></div>
</div>
<div class="pl"><h3>💰 Profit & Loss</h3>
<div class="row"><span>📈 Revenue</span><span>{{revenue}} ကျပ်</span></div>
<div class="row minus"><span>➖ Production</span><span>({{prod_cost}}) ကျပ်</span></div>
<div class="row"><span>✅ Gross Profit</span><span>{{gross_profit}} ကျပ်</span></div>
<div class="row minus"><span>➖ Labor</span><span>({{labor}}) ကျပ်</span></div>
<div class="row minus"><span>➖ Utilities</span><span>({{utilities}}) ကျပ်</span></div>
<div class="row total"><span>🏆 Net Profit</span><span>{{net_profit}} ကျပ်</span></div>
</div>
<div class="charts">
<div class="chart"><canvas id="i"></canvas></div>
<div class="chart"><canvas id="c"></canvas></div>
</div>
<script>
new Chart(document.getElementById('i'),{type:'bar',data:{labels:{{il}},datasets:[{label:'Revenue',data:{{id}},backgroundColor:'#2d7a2d'}]}});
new Chart(document.getElementById('c'),{type:'pie',data:{labels:{{cl}},datasets:[{data:{{cd}},backgroundColor:['#2d7a2d','#5ab85a','#a8d8a8','#d4edda']}]}});
</script></body></html>"""

@flask_app.route("/")
def dashboard():
    d = get_data()
    html = HTML
    for k, v in d.items():
        if k not in ['items', 'channels']:
            html = html.replace('{{'+k+'}}', f"{v:,}" if isinstance(v, int) else str(v))
    html = html.replace('{{il}}', str([i[0] for i in d['items']]))
    html = html.replace('{{id}}', str([i[1] for i in d['items']]))
    html = html.replace('{{cl}}', str([c[0] for c in d['channels']]))
    html = html.replace('{{cd}}', str([c[1] for c in d['channels']]))
    return html

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port, use_reloader=False)

async def run_bot():
    async def start(update, context):
        await update.message.reply_text(
            "🥩 GreenArt Beef Jerky Bot\n\n"
            "ဥပမာ: MaHla 100g 10 5000 retail\n\n"
            "/report /kpi /pl"
        )

    async def report(update, context):
        count, revenue = get_monthly_summary()
        await update.message.reply_text(f"📊 ဒီလ\nရောင်း: {count}ကြိမ်\nRevenue: {revenue:,}ကျပ်")

    async def kpi(update, context):
        items, channels = get_kpi()
        msg = "📊 KPI\n\n🥩 Product:\n"
        for item, qty, total in items:
            msg += f"  {item}: {qty}ထုပ် — {total:,}ကျပ်\n"
        msg += "\n📦 Channel:\n"
        for channel, total in channels:
            msg += f"  {channel}: {total:,}ကျပ်\n"
        await update.message.reply_text(msg)

    async def pl(update, context):
        d = get_pl_summary()
        await update.message.reply_text(
            f"💰 P&L\nRevenue: {d['revenue']:,}ကျပ်\n"
            f"Net Profit: {d['net_profit']:,}ကျပ်\n"
            f"Margin: {d['margin']}%"
        )

    async def handle_message(update, context):
        parts = update.message.text.strip().split()
        if len(parts) >= 4:
            try:
                customer, size = parts[0], parts[1]
                qty, price = int(parts[2]), int(parts[3])
                channel = parts[4] if len(parts) > 4 else "retail"
                date = datetime.now().strftime("%Y-%m-%d")
                total = save_sale(date, customer, channel, f"Beef Jerky {size}", qty, price)
                await update.message.reply_text(f"✅ မှတ်တမ်းတင်ပြီ!\nစုစုပေါင်း: {total:,}ကျပ်")
            except Exception as e:
                await update.message.reply_text(f"❌ Error: {e}")
        else:
            await update.message.reply_text("ဥပမာ: MaHla 100g 10 5000 retail")

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("kpi", kpi))
    app.add_handler(CommandHandler("pl", pl))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot စတင်နေပြီ...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    asyncio.run(run_bot())
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from database import init_db, save_sale, get_monthly_summary, get_kpi, get_pl_summary
from datetime import datetime

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

init_db()

async def start(update: Update, context):
    await update.message.reply_text(
        "🥩 GreenArt Beef Jerky Bot မှ ကြိုဆိုပါတယ်!\n\n"
        "ရောင်းအား မှတ်ဖို့:\n"
        "ဥပမာ: MaHla 100g 10 5000 retail\n\n"
        "/report - ဒီလ ရလဒ်\n"
        "/kpi - အရောင်းစာရင်း\n"
        "/help - အကူအညီ"
    )

async def report(update: Update, context):
    count, revenue = get_monthly_summary()
    await update.message.reply_text(
        f"📊 ဒီလ ရလဒ်\n"
        f"ရောင်းအရေအတွက်: {count} ကြိမ်\n"
        f"စုစုပေါင်း Revenue: {revenue:,} ကျပ်"
    )

async def kpi(update: Update, context):
    items, channels = get_kpi()
    msg = "📊 KPI Summary\n\n"
    msg += "🥩 Product အလိုက်:\n"
    for item, qty, total in items:
        msg += f"  {item}: {qty}ထုပ် — {total:,}ကျပ်\n"
    msg += "\n📦 Channel အလိုက်:\n"
    for channel, total in channels:
        msg += f"  {channel}: {total:,}ကျပ်\n"
    await update.message.reply_text(msg)
async def pl(update: Update, context):
    d = get_pl_summary()
    await update.message.reply_text(
        f"💰 Profit & Loss Summary\n\n"
        f"📈 Revenue:        {d['revenue']:>12,} ကျပ်\n"
        f"➖ Production:     {d['prod_cost']:>12,} ကျပ်\n"
        f"➖ Labor:          {d['labor']:>12,} ကျပ်\n"
        f"➖ Utilities:      {d['utilities']:>12,} ကျပ်\n"
        f"──────────────────────\n"
        f"✅ Gross Profit:   {d['gross_profit']:>12,} ကျပ်\n"
        f"✅ Net Profit:     {d['net_profit']:>12,} ကျပ်\n"
        f"📊 Net Margin:     {d['margin']:>11}%"
    )

async def handle_message(update: Update, context):
    text = update.message.text.strip()
    parts = text.split()
    if len(parts) >= 4:
        try:
            customer = parts[0]
            item = f"Beef Jerky {parts[1]}"
            quantity = int(parts[2])
            unit_price = int(parts[3])
            channel = parts[4] if len(parts) > 4 else "retail"
            date = datetime.now().strftime("%Y-%m-%d")
            total = save_sale(date, customer, channel, item, quantity, unit_price)
            await update.message.reply_text(
                f"✅ မှတ်တမ်းတင်ပြီ!\n"
                f"ဖောက်သည်: {customer}\n"
                f"ပစ္စည်း: {item}\n"
                f"အရေအတွက်: {quantity}\n"
                f"စုစုပေါင်း: {total:,} ကျပ်"
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}\nဥပမာ: MaHla 100g 10 5000 retail")
    else:
        await update.message.reply_text("ဥပမာ: MaHla 100g 10 5000 retail")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("report", report))
app.add_handler(CommandHandler("kpi", kpi))
app.add_handler(CommandHandler("pl", pl))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("Bot စတင်နေပြီ...")
app.run_polling()
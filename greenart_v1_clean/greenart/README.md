# 🥩 GreenArt Beef Jerky — AI Business OS v1

## Stack
- **Telegram Bot** — Natural language data entry (Burmese/English)
- **Supabase PostgreSQL** — Database
- **Railway** — Hosting (Bot + Dashboard)
- **Flask** — Web Dashboard

## Project Structure
```
greenart/
├── main.py          ← Entry point (Bot + Dashboard combined)
├── database.py      ← All DB functions + table init
├── sale_engine.py   ← 11-step sale processing engine
├── nlp_parser.py    ← Local NLP (no API needed)
├── requirements.txt
├── Procfile         ← Railway deploy config
└── .env             ← Secrets (never commit!)
```

## Setup

### 1. Supabase
```
python database.py   # creates all 13 tables
```

### 2. .env
```
TELEGRAM_TOKEN=your_token
DATABASE_URL=postgresql://...supabase...
```

### 3. Deploy to Railway
```bash
git add .
git commit -m "GreenArt AI OS v1"
git push
```

## Telegram Commands
| Command | ဘာလုပ်လဲ |
|---|---|
| `MaHla 100g 10 5000 retail` | ရောင်းအား မှတ် |
| `Batch001 5kg beef → 3kg` | Production Batch မှတ် |
| `Marketing 50000 cash` | Expense မှတ် |
| `beef 10kg ဝယ်လာ 15000` | Stock ထည့် |
| `/report` | Monthly Revenue |
| `/kpi` | Product + Channel KPI |
| `/pl` | Profit & Loss |
| `/stock` | Inventory levels |
| `/yield` | Yield % summary |
| `/alerts` | Active alerts |

## Dashboard KPIs
ဒီနေ့ Revenue · ဒီလ Revenue · Gross Profit · Net Profit · Net Margin · Yield % · Inventory Value · Batches

## Import Excel Data
```bash
python import_master.py          # fresh import
python import_master.py --clear  # wipe + re-import
```

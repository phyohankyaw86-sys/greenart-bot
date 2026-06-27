import pandas as pd
import sqlite3
from datetime import datetime

conn = sqlite3.connect("greenart.db")
c = conn.cursor()

# Sales table ပြင်ဆင်
c.executescript("""
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT, customer TEXT, channel TEXT,
    item TEXT, quantity INTEGER, unit_price INTEGER,
    total INTEGER, created_at TEXT
);
CREATE TABLE IF NOT EXISTS production (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT, item TEXT, qty_used REAL,
    unit TEXT, unit_cost INTEGER, total_cost INTEGER
);
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT, category TEXT,
    description TEXT, amount INTEGER
);
CREATE TABLE IF NOT EXISTS assumptions (
    key TEXT PRIMARY KEY, value REAL
);
""")
conn.commit()

FILE = "GreenArt_BeefJerky_MASTER_Workbook.xlsx"

# Sales import
try:
    df = pd.read_excel(FILE, sheet_name="Sales_Data", header=None)
    header_row = None
    for i, row in df.iterrows():
        if "Date" in str(row.values) and "Customer" in str(row.values):
            header_row = i
            break
    if header_row is not None:
        df.columns = df.iloc[header_row]
        df = df.iloc[header_row+1:].reset_index(drop=True)
        df = df.dropna(subset=["Date"])
        count = 0
        for _, row in df.iterrows():
            try:
                c.execute("""
                    INSERT INTO sales (date, customer, channel, item, quantity, unit_price, total, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(row.get("Date", ""))[:10],
                    str(row.get("Customer Name", "")),
                    str(row.get("Sale Channel", "")),
                    str(row.get("Items", "")),
                    int(float(str(row.get("Quantity (pcs)", 0) or 0))),
                    int(float(str(row.get("Unit Price (MMK)", 0) or 0))),
                    int(float(str(row.get("Total Revenue (MMK)", 0) or 0))),
                    datetime.now().isoformat()
                ))
                count += 1
            except:
                pass
        conn.commit()
        print(f"✅ Sales: {count} rows import ပြီး")
except Exception as e:
    print(f"❌ Sales error: {e}")

# Production import
try:
    df = pd.read_excel(FILE, sheet_name="Production_Cost", header=None)
    header_row = None
    for i, row in df.iterrows():
        if "Date" in str(row.values) and "Item" in str(row.values):
            header_row = i
            break
    if header_row is not None:
        df.columns = df.iloc[header_row]
        df = df.iloc[header_row+1:].reset_index(drop=True)
        df = df.dropna(subset=["Date"])
        count = 0
        for _, row in df.iterrows():
            try:
                c.execute("""
                    INSERT INTO production (date, item, qty_used, unit, unit_cost, total_cost)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    str(row.get("Date", ""))[:10],
                    str(row.get("Item", "")),
                    float(str(row.get("Qty Used", 0) or 0)),
                    str(row.get("Unit", "")),
                    int(float(str(row.get("Unit Cost (MMK)", 0) or 0))),
                    int(float(str(row.get("Total Cost (MMK)", 0) or 0)))
                ))
                count += 1
            except:
                pass
        conn.commit()
        print(f"✅ Production: {count} rows import ပြီး")
except Exception as e:
    print(f"❌ Production error: {e}")

# Assumptions import
try:
    df = pd.read_excel(FILE, sheet_name="Assumptions", header=None)
    count = 0
    for _, row in df.iterrows():
        try:
            key = str(row.iloc[0]).strip()
            val = row.iloc[1]
            if key and val and key != "nan":
                c.execute("INSERT OR REPLACE INTO assumptions (key, value) VALUES (?, ?)",
                         (key, float(str(val))))
                count += 1
        except:
            pass
    conn.commit()
    print(f"✅ Assumptions: {count} rows import ပြီး")
except Exception as e:
    print(f"❌ Assumptions error: {e}")

conn.close()
print("\n🎉 Import အကုန်ပြီးပြီ!")
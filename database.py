import os
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def get_conn():
    url = os.environ.get("DATABASE_URL")
    return psycopg2.connect(url)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id SERIAL PRIMARY KEY,
            date TEXT, customer TEXT, channel TEXT,
            item TEXT, quantity INTEGER, unit_price INTEGER,
            total INTEGER, created_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS production (
            id SERIAL PRIMARY KEY,
            date TEXT, item TEXT, qty_used REAL,
            unit TEXT, unit_cost INTEGER, total_cost INTEGER
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id SERIAL PRIMARY KEY,
            date TEXT, category TEXT,
            description TEXT, amount INTEGER
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS assumptions (
            key TEXT PRIMARY KEY, value REAL
        )
    """)
    conn.commit()
    conn.close()

def save_sale(date, customer, channel, item, quantity, unit_price):
    conn = get_conn()
    c = conn.cursor()
    total = quantity * unit_price
    c.execute("""
        INSERT INTO sales (date, customer, channel, item, quantity, unit_price, total, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (date, customer, channel, item, quantity, unit_price, total, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return total

def get_monthly_summary():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT COUNT(*), SUM(total) FROM sales
        WHERE date >= date_trunc('month', CURRENT_DATE)::text
    """)
    count, revenue = c.fetchone()
    conn.close()
    return count or 0, revenue or 0

def get_kpi():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT item, SUM(quantity), SUM(total) FROM sales GROUP BY item ORDER BY SUM(total) DESC")
    items = c.fetchall()
    c.execute("SELECT channel, SUM(total) FROM sales GROUP BY channel ORDER BY SUM(total) DESC")
    channels = c.fetchall()
    conn.close()
    return items, channels

def get_pl_summary():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT SUM(total) FROM sales")
    revenue = c.fetchone()[0] or 0
    c.execute("SELECT SUM(total_cost) FROM production")
    prod_cost = c.fetchone()[0] or 0
    c.execute("SELECT value FROM assumptions WHERE key='Monthly Labor Cost (Total)'")
    row = c.fetchone()
    labor = row[0] if row else 0
    c.execute("SELECT value FROM assumptions WHERE key='Utilities Cost per Month'")
    row = c.fetchone()
    utilities = row[0] if row else 0
    conn.close()
    total_cost = prod_cost + labor + utilities
    gross_profit = revenue - prod_cost
    net_profit = revenue - total_cost
    margin = round((net_profit / revenue * 100), 1) if revenue > 0 else 0
    return {
        "revenue": int(revenue), "prod_cost": int(prod_cost),
        "labor": int(labor), "utilities": int(utilities),
        "total_cost": int(total_cost), "gross_profit": int(gross_profit),
        "net_profit": int(net_profit), "margin": margin
    }
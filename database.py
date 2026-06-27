import sqlite3
from datetime import datetime

def init_db():
    conn = sqlite3.connect("greenart.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            customer TEXT,
            channel TEXT,
            item TEXT,
            quantity INTEGER,
            unit_price INTEGER,
            total INTEGER,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_sale(date, customer, channel, item, quantity, unit_price):
    conn = sqlite3.connect("greenart.db")
    c = conn.cursor()
    total = quantity * unit_price
    c.execute("""
        INSERT INTO sales (date, customer, channel, item, quantity, unit_price, total, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (date, customer, channel, item, quantity, unit_price, total, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return total

def get_monthly_summary():
    conn = sqlite3.connect("greenart.db")
    c = conn.cursor()
    c.execute("""
        SELECT COUNT(*), SUM(total) FROM sales
        WHERE strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
    """)
    count, revenue = c.fetchone()
    conn.close()
    return count or 0, revenue or 0

def get_kpi():
    conn = sqlite3.connect("greenart.db")
    c = conn.cursor()
    c.execute("SELECT item, SUM(quantity), SUM(total) FROM sales GROUP BY item ORDER BY SUM(total) DESC")
    items = c.fetchall()
    c.execute("SELECT channel, SUM(total) FROM sales GROUP BY channel ORDER BY SUM(total) DESC")
    channels = c.fetchall()
    conn.close()
    return items, channels
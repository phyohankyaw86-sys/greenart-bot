"""
GreenArt Beef Jerky — Full Database Layer
Matches all 18 sheets of GreenArt_BeefJerky_MASTER_Workbook.xlsx
PostgreSQL via Supabase / Railway
"""
import os
from datetime import datetime
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()

def get_conn():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set")
    return psycopg2.connect(url)

# ─────────────────────────────────────────────
# INIT — CREATE ALL TABLES
# ─────────────────────────────────────────────
def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Sheet: Assumptions
    c.execute("""
        CREATE TABLE IF NOT EXISTS assumptions (
            key        TEXT PRIMARY KEY,
            value      NUMERIC,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Sheet: Sales_Data
    c.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id            SERIAL PRIMARY KEY,
            date          DATE NOT NULL,
            customer      TEXT,
            channel       TEXT,
            delivery_ch   TEXT DEFAULT 'Direct',
            delivery_fee  INTEGER DEFAULT 0,
            item          TEXT,
            quantity      INTEGER DEFAULT 0,
            unit_price    INTEGER DEFAULT 0,
            subtotal      INTEGER DEFAULT 0,
            delivery_inc  INTEGER DEFAULT 0,
            total_revenue INTEGER DEFAULT 0,
            created_at    TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Sheet: Production_Cost — Raw Material block
    c.execute("""
        CREATE TABLE IF NOT EXISTS production_raw_material (
            id         SERIAL PRIMARY KEY,
            date       DATE,
            item       TEXT,
            qty_used   NUMERIC DEFAULT 0,
            unit       TEXT,
            unit_cost  INTEGER DEFAULT 0,
            total_cost INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Sheet: Production_Cost — Packaging block
    c.execute("""
        CREATE TABLE IF NOT EXISTS production_packaging (
            id         SERIAL PRIMARY KEY,
            date       DATE,
            item       TEXT,
            qty_used   NUMERIC DEFAULT 0,
            unit       TEXT,
            unit_cost  INTEGER DEFAULT 0,
            total_cost INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Sheet: Production_Cost — Labor block
    c.execute("""
        CREATE TABLE IF NOT EXISTS production_labor (
            id              SERIAL PRIMARY KEY,
            date            DATE,
            employee        TEXT,
            base_salary     INTEGER DEFAULT 0,
            allocation_pct  NUMERIC DEFAULT 0,
            cost_allocated  INTEGER DEFAULT 0,
            remark          TEXT,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Sheet: Production_Cost — Utilities block
    c.execute("""
        CREATE TABLE IF NOT EXISTS production_utilities (
            id             SERIAL PRIMARY KEY,
            date           DATE,
            item           TEXT,
            monthly_cost   INTEGER DEFAULT 0,
            allocation_pct NUMERIC DEFAULT 0,
            prod_cost      INTEGER DEFAULT 0,
            remark         TEXT,
            created_at     TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Sheet: Cost_Per_Batch — batch summary
    c.execute("""
        CREATE TABLE IF NOT EXISTS production_batches (
            id                SERIAL PRIMARY KEY,
            date              DATE,
            batch_no          TEXT UNIQUE,
            raw_beef_kg       NUMERIC DEFAULT 0,
            raw_material_cost INTEGER DEFAULT 0,
            packaging_cost    INTEGER DEFAULT 0,
            labor_cost        INTEGER DEFAULT 0,
            utilities_cost    INTEGER DEFAULT 0,
            total_batch_cost  INTEGER DEFAULT 0,
            dried_output_kg   NUMERIC DEFAULT 0,
            cost_per_gram     NUMERIC DEFAULT 0,
            notes             TEXT,
            created_at        TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Sheet: Yield_Tracking
    c.execute("""
        CREATE TABLE IF NOT EXISTS yield_tracking (
            id               SERIAL PRIMARY KEY,
            date             DATE,
            batch_no         TEXT,
            raw_beef_kg      NUMERIC DEFAULT 0,
            dried_output_kg  NUMERIC DEFAULT 0,
            actual_yield_pct NUMERIC DEFAULT 0,
            target_yield_pct NUMERIC DEFAULT 0.6,
            remark           TEXT,
            created_at       TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Sheet: Inventory — current snapshot (fast lookup)
    c.execute("""
        CREATE TABLE IF NOT EXISTS inventory_current (
            item       TEXT PRIMARY KEY,
            category   TEXT,
            quantity   NUMERIC DEFAULT 0,
            unit       TEXT,
            unit_cost  INTEGER DEFAULT 0,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Sheet: Inventory — movement ledger
    c.execute("""
        CREATE TABLE IF NOT EXISTS inventory_log (
            id            SERIAL PRIMARY KEY,
            date          DATE,
            item          TEXT,
            category      TEXT,
            batch_ref     TEXT,
            opening_stock NUMERIC DEFAULT 0,
            stock_in      NUMERIC DEFAULT 0,
            stock_out     NUMERIC DEFAULT 0,
            closing_stock NUMERIC DEFAULT 0,
            unit          TEXT,
            unit_cost     INTEGER DEFAULT 0,
            closing_value INTEGER DEFAULT 0,
            created_at    TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Sheet: Expense_Ledger
    c.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id             SERIAL PRIMARY KEY,
            date           DATE,
            description    TEXT,
            category       TEXT,
            amount         INTEGER DEFAULT 0,
            payment_method TEXT DEFAULT 'Cash',
            remark         TEXT,
            created_at     TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Sheet: Cash_In
    c.execute("""
        CREATE TABLE IF NOT EXISTS cash_in (
            id            SERIAL PRIMARY KEY,
            date          DATE UNIQUE,
            retail_mmk    INTEGER DEFAULT 0,
            wholesale_mmk INTEGER DEFAULT 0,
            dist_mmk      INTEGER DEFAULT 0,
            total_in      INTEGER DEFAULT 0,
            created_at    TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Sheet: Cash_Out
    c.execute("""
        CREATE TABLE IF NOT EXISTS cash_out (
            id               SERIAL PRIMARY KEY,
            date             DATE UNIQUE,
            opex_mmk         INTEGER DEFAULT 0,
            raw_material_mmk INTEGER DEFAULT 0,
            packaging_mmk    INTEGER DEFAULT 0,
            labor_mmk        INTEGER DEFAULT 0,
            utilities_mmk    INTEGER DEFAULT 0,
            total_out        INTEGER DEFAULT 0,
            created_at       TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    conn.commit()
    conn.close()
    print("✅ All 13 tables created/verified")

# ─────────────────────────────────────────────
# SALES
# ─────────────────────────────────────────────
def save_sale(date, customer, channel, item, quantity, unit_price,
              delivery_ch="Direct", delivery_fee=0, delivery_inc=0):
    conn = get_conn()
    c = conn.cursor()
    subtotal = quantity * unit_price
    total = subtotal + delivery_inc
    c.execute("""
        INSERT INTO sales
          (date,customer,channel,delivery_ch,delivery_fee,
           item,quantity,unit_price,subtotal,delivery_inc,total_revenue)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING total_revenue
    """, (date,customer,channel,delivery_ch,delivery_fee,
          item,quantity,unit_price,subtotal,delivery_inc,total))
    result = c.fetchone()[0]
    conn.commit(); conn.close()
    return result

def get_today_revenue():
    conn = get_conn(); c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(total_revenue),0) FROM sales WHERE date=CURRENT_DATE")
    v = c.fetchone()[0]; conn.close(); return int(v)

def get_monthly_summary():
    conn = get_conn(); c = conn.cursor()
    c.execute("""
        SELECT COUNT(*), COALESCE(SUM(total_revenue),0) FROM sales
        WHERE DATE_TRUNC('month',date)=DATE_TRUNC('month',CURRENT_DATE)
    """)
    row = c.fetchone(); conn.close()
    return row[0] or 0, row[1] or 0

def get_kpi():
    conn = get_conn(); c = conn.cursor()
    c.execute("SELECT item,SUM(quantity),SUM(total_revenue) FROM sales GROUP BY item ORDER BY 3 DESC")
    items = c.fetchall()
    c.execute("SELECT channel,SUM(total_revenue) FROM sales GROUP BY channel ORDER BY 2 DESC")
    channels = c.fetchall()
    c.execute("SELECT customer,SUM(total_revenue) FROM sales GROUP BY customer ORDER BY 2 DESC LIMIT 5")
    top = c.fetchall()
    conn.close(); return items, channels, top

# ─────────────────────────────────────────────
# PRODUCTION BATCHES
# ─────────────────────────────────────────────
def save_production_batch(date, batch_no, raw_beef_kg, dried_output_kg,
                           raw_mat, pkg, labor, util, notes=""):
    conn = get_conn(); c = conn.cursor()
    total = raw_mat + pkg + labor + util
    cpg = round(total / (dried_output_kg * 1000), 4) if dried_output_kg > 0 else 0
    c.execute("""
        INSERT INTO production_batches
          (date,batch_no,raw_beef_kg,raw_material_cost,packaging_cost,
           labor_cost,utilities_cost,total_batch_cost,dried_output_kg,cost_per_gram,notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (batch_no) DO UPDATE SET
          total_batch_cost=EXCLUDED.total_batch_cost,
          dried_output_kg=EXCLUDED.dried_output_kg,
          cost_per_gram=EXCLUDED.cost_per_gram
    """, (date,batch_no,raw_beef_kg,raw_mat,pkg,labor,util,total,dried_output_kg,cpg,notes))
    conn.commit(); conn.close()
    return total, cpg

# ─────────────────────────────────────────────
# YIELD TRACKING
# ─────────────────────────────────────────────
def save_yield(date, batch_no, raw_beef_kg, dried_output_kg, target=0.6, remark=""):
    actual = round(dried_output_kg / raw_beef_kg, 4) if raw_beef_kg > 0 else 0
    conn = get_conn(); c = conn.cursor()
    c.execute("""
        INSERT INTO yield_tracking
          (date,batch_no,raw_beef_kg,dried_output_kg,
           actual_yield_pct,target_yield_pct,remark)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
    """, (date,batch_no,raw_beef_kg,dried_output_kg,actual,target,remark))
    conn.commit(); conn.close()
    return actual

def get_yield_summary():
    conn = get_conn()
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("""
        SELECT COUNT(*) AS batches,
               ROUND(AVG(actual_yield_pct)*100,1) AS avg_yield_pct,
               ROUND(MAX(actual_yield_pct)*100,1) AS best_yield_pct,
               ROUND(MIN(actual_yield_pct)*100,1) AS worst_yield_pct,
               SUM(raw_beef_kg)                   AS total_raw_kg,
               SUM(dried_output_kg)               AS total_output_kg
        FROM yield_tracking WHERE raw_beef_kg > 0
    """)
    row = c.fetchone(); conn.close()
    return dict(row) if row else {}

# ─────────────────────────────────────────────
# INVENTORY
# ─────────────────────────────────────────────
def add_stock(item, category, quantity, unit, unit_cost=0, note=""):
    conn = get_conn(); c = conn.cursor()
    now = datetime.now()
    c.execute("""
        INSERT INTO inventory_current (item,category,quantity,unit,unit_cost,updated_at)
        VALUES (%s,%s,%s,%s,%s,%s)
        ON CONFLICT (item) DO UPDATE SET
          quantity=inventory_current.quantity+EXCLUDED.quantity,
          unit_cost=EXCLUDED.unit_cost, updated_at=EXCLUDED.updated_at
    """, (item,category,quantity,unit,unit_cost,now))
    c.execute("""
        INSERT INTO inventory_log
          (date,item,category,stock_in,unit,unit_cost,closing_stock,closing_value)
        SELECT CURRENT_DATE,%s,%s,%s,%s,%s,quantity,quantity*%s
        FROM inventory_current WHERE item=%s
    """, (item,category,quantity,unit,unit_cost,unit_cost,item))
    conn.commit(); conn.close()

def use_stock(item, category, quantity, unit, note=""):
    conn = get_conn(); c = conn.cursor()
    now = datetime.now()
    c.execute("""
        INSERT INTO inventory_current (item,category,quantity,unit,updated_at)
        VALUES (%s,%s,%s,%s,%s)
        ON CONFLICT (item) DO UPDATE SET
          quantity=inventory_current.quantity-EXCLUDED.quantity,
          updated_at=EXCLUDED.updated_at
    """, (item,category,-quantity,unit,now))
    c.execute("SELECT quantity,unit_cost FROM inventory_current WHERE item=%s",(item,))
    row = c.fetchone()
    remaining = row[0] if row else 0
    unit_cost  = row[1] if row else 0
    c.execute("""
        INSERT INTO inventory_log
          (date,item,category,stock_out,unit,unit_cost,closing_stock,closing_value)
        VALUES (CURRENT_DATE,%s,%s,%s,%s,%s,%s,%s)
    """, (item,category,quantity,unit,unit_cost,remaining,remaining*unit_cost))
    conn.commit(); conn.close()
    return remaining

def get_stock():
    conn = get_conn(); c = conn.cursor()
    c.execute("""
        SELECT item,category,quantity,unit,unit_cost,quantity*unit_cost
        FROM inventory_current ORDER BY category,item
    """)
    rows = c.fetchall(); conn.close(); return rows

def get_low_stock(days=3):
    conn = get_conn(); c = conn.cursor()
    c.execute("""
        SELECT ic.item,ic.category,ic.quantity,ic.unit,ic.unit_cost,
               COALESCE(u.avg_out,0),
               CASE WHEN COALESCE(u.avg_out,0)>0
                    THEN ROUND(ic.quantity/u.avg_out,1) ELSE NULL END
        FROM inventory_current ic
        LEFT JOIN (
            SELECT item,SUM(stock_out)/NULLIF(COUNT(DISTINCT date),0) AS avg_out
            FROM inventory_log
            WHERE date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY item
        ) u ON u.item=ic.item
        WHERE ic.quantity <= COALESCE(u.avg_out,0)*%s OR ic.quantity <= 0
        ORDER BY ic.quantity
    """, (days,))
    rows = c.fetchall(); conn.close(); return rows

# ─────────────────────────────────────────────
# EXPENSES
# ─────────────────────────────────────────────
def save_expense(date, description, category, amount, payment_method="Cash", remark=""):
    conn = get_conn(); c = conn.cursor()
    c.execute("""
        INSERT INTO expenses (date,description,category,amount,payment_method,remark)
        VALUES (%s,%s,%s,%s,%s,%s)
    """, (date,description,category,amount,payment_method,remark))
    conn.commit(); conn.close()

# ─────────────────────────────────────────────
# ASSUMPTIONS
# ─────────────────────────────────────────────
def get_assumption(key, default=0):
    conn = get_conn(); c = conn.cursor()
    c.execute("SELECT value FROM assumptions WHERE key=%s",(key,))
    row = c.fetchone(); conn.close()
    return float(row[0]) if row else default

def set_assumption(key, value):
    conn = get_conn(); c = conn.cursor()
    c.execute("""
        INSERT INTO assumptions (key,value) VALUES (%s,%s)
        ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value,updated_at=NOW()
    """, (key,value))
    conn.commit(); conn.close()

# ─────────────────────────────────────────────
# P&L
# ─────────────────────────────────────────────
def get_pl_summary():
    conn = get_conn(); c = conn.cursor()
    c.execute("""
        SELECT COALESCE(SUM(total_revenue),0),
               COALESCE(SUM(subtotal),0),
               COALESCE(SUM(delivery_inc),0)
        FROM sales
        WHERE DATE_TRUNC('month',date)=DATE_TRUNC('month',CURRENT_DATE)
    """)
    revenue, prod_rev, del_rev = c.fetchone()
    c.execute("""
        SELECT COALESCE(SUM(total_batch_cost),0) FROM production_batches
        WHERE DATE_TRUNC('month',date)=DATE_TRUNC('month',CURRENT_DATE)
    """)
    cogs = c.fetchone()[0]
    c.execute("""
        SELECT COALESCE(SUM(amount),0) FROM expenses
        WHERE DATE_TRUNC('month',date)=DATE_TRUNC('month',CURRENT_DATE)
    """)
    opex = c.fetchone()[0]
    conn.close()
    gp  = revenue - cogs
    net = gp - opex
    return {
        "revenue": int(revenue), "product_rev": int(prod_rev),
        "delivery_rev": int(del_rev), "cogs": int(cogs),
        "gross_profit": int(gp),
        "gp_margin":  round(gp/revenue*100,1)  if revenue>0 else 0,
        "opex": int(opex), "net_profit": int(net),
        "net_margin": round(net/revenue*100,1) if revenue>0 else 0,
    }

# ─────────────────────────────────────────────
# DASHBOARD KPI (all-in-one)
# ─────────────────────────────────────────────
def get_dashboard_kpi():
    conn = get_conn(); c = conn.cursor()
    c.execute("""
        SELECT
          COALESCE(SUM(CASE WHEN date=CURRENT_DATE THEN total_revenue END),0),
          COALESCE(SUM(CASE WHEN DATE_TRUNC('month',date)=DATE_TRUNC('month',CURRENT_DATE)
                            THEN total_revenue END),0)
        FROM sales
    """)
    today_rev, month_rev = c.fetchone()
    c.execute("""
        SELECT COUNT(*),COALESCE(SUM(dried_output_kg),0),COALESCE(SUM(total_batch_cost),0)
        FROM production_batches
        WHERE DATE_TRUNC('month',date)=DATE_TRUNC('month',CURRENT_DATE)
    """)
    batches, output_kg, prod_cost = c.fetchone()
    c.execute("SELECT ROUND(AVG(actual_yield_pct)*100,1) FROM yield_tracking WHERE raw_beef_kg>0")
    yield_avg = c.fetchone()[0] or 0
    c.execute("SELECT COALESCE(SUM(quantity*unit_cost),0) FROM inventory_current")
    inv_value = c.fetchone()[0]
    c.execute("""
        SELECT COALESCE(SUM(total_in),0) FROM cash_in
        WHERE DATE_TRUNC('month',date)=DATE_TRUNC('month',CURRENT_DATE)
    """)
    cash_in_v = c.fetchone()[0]
    c.execute("""
        SELECT COALESCE(SUM(total_out),0) FROM cash_out
        WHERE DATE_TRUNC('month',date)=DATE_TRUNC('month',CURRENT_DATE)
    """)
    cash_out_v = c.fetchone()[0]
    conn.close()
    pl = get_pl_summary()
    yd = get_yield_summary()
    return {
        "today_revenue":    int(today_rev),
        "month_revenue":    int(month_rev),
        "month_batches":    int(batches),
        "month_output_kg":  float(output_kg),
        "month_prod_cost":  int(prod_cost),
        "avg_yield_pct":    float(yield_avg),
        "inventory_value":  int(inv_value),
        "cash_in":          int(cash_in_v),
        "cash_out":         int(cash_out_v),
        "cash_balance":     int(cash_in_v - cash_out_v),
        "yield_batches":    int(yd.get("batches") or 0),
        **pl,
    }

if __name__ == "__main__":
    init_db()
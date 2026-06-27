from flask import Flask, render_template_string
import sqlite3
import os

app = Flask(__name__)

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
        c.execute("SELECT date, SUM(total) FROM sales GROUP BY date ORDER BY date")
        daily = c.fetchall()
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
        total_cost = prod_cost + labor + utilities
        gross_profit = revenue - prod_cost
        net_profit = revenue - total_cost
        margin = round((net_profit / revenue * 100), 1) if revenue > 0 else 0
        return {
            "revenue": int(revenue), "count": count or 0,
            "prod_cost": int(prod_cost), "labor": int(labor),
            "utilities": int(utilities), "total_cost": int(total_cost),
            "gross_profit": int(gross_profit), "net_profit": int(net_profit),
            "margin": margin,
            "items": items, "channels": channels, "daily": daily
        }
    except:
        return {
            "revenue": 0, "count": 0, "prod_cost": 0, "labor": 0,
            "utilities": 0, "total_cost": 0, "gross_profit": 0,
            "net_profit": 0, "margin": 0,
            "items": [], "channels": [], "daily": []
        }

HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GreenArt Beef Jerky Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: Arial; background: #f0f2f5; padding: 16px; }
h1 { color: #2d7a2d; text-align: center; margin-bottom: 20px; font-size: 22px; }
.cards { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; margin-bottom: 20px; }
.card { background: white; border-radius: 12px; padding: 16px 20px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.08); min-width: 140px; flex: 1; }
.card h2 { font-size: 22px; color: #2d7a2d; margin-bottom: 4px; }
.card p { color: #888; font-size: 13px; }
.card.red h2 { color: #e53935; }
.card.blue h2 { color: #1565c0; }
.pl-box { background: white; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
.pl-box h3 { color: #2d7a2d; margin-bottom: 12px; }
.pl-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
.pl-row.total { font-weight: bold; border-top: 2px solid #2d7a2d; border-bottom: none; color: #2d7a2d; font-size: 16px; }
.pl-row.minus { color: #e53935; }
.charts { display: flex; flex-wrap: wrap; gap: 16px; justify-content: center; }
.chart-box { background: white; border-radius: 12px; padding: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); width: 100%; max-width: 420px; }
</style>
</head>
<body>
<h1>🥩 GreenArt Beef Jerky Dashboard</h1>

<div class="cards">
  <div class="card">
    <h2>{{ "{:,}".format(d.revenue) }}</h2>
    <p>Revenue (ကျပ်)</p>
  </div>
  <div class="card">
    <h2>{{ d.count }}</h2>
    <p>ရောင်းချမှု</p>
  </div>
  <div class="card">
    <h2>{{ "{:,}".format(d.net_profit) }}</h2>
    <p>Net Profit (ကျပ်)</p>
  </div>
  <div class="card blue">
    <h2>{{ d.margin }}%</h2>
    <p>Net Margin</p>
  </div>
</div>

<div class="pl-box">
  <h3>💰 Profit & Loss Statement</h3>
  <div class="pl-row">
    <span>📈 Revenue</span>
    <span>{{ "{:,}".format(d.revenue) }} ကျပ်</span>
  </div>
  <div class="pl-row minus">
    <span>➖ Production Cost</span>
    <span>({{ "{:,}".format(d.prod_cost) }}) ကျပ်</span>
  </div>
  <div class="pl-row">
    <span>✅ Gross Profit</span>
    <span>{{ "{:,}".format(d.gross_profit) }} ကျပ်</span>
  </div>
  <div class="pl-row minus">
    <span>➖ Labor</span>
    <span>({{ "{:,}".format(d.labor) }}) ကျပ်</span>
  </div>
  <div class="pl-row minus">
    <span>➖ Utilities</span>
    <span>({{ "{:,}".format(d.utilities) }}) ကျပ်</span>
  </div>
  <div class="pl-row total">
    <span>🏆 Net Profit</span>
    <span>{{ "{:,}".format(d.net_profit) }} ကျပ်</span>
  </div>
</div>

<div class="charts">
  <div class="chart-box"><canvas id="itemChart"></canvas></div>
  <div class="chart-box"><canvas id="channelChart"></canvas></div>
  <div class="chart-box" style="max-width:860px"><canvas id="dailyChart"></canvas></div>
</div>

<script>
new Chart(document.getElementById('itemChart'), {
  type: 'bar',
  data: {
    labels: {{ item_labels | safe }},
    datasets: [{ label: 'Revenue (ကျပ်)', data: {{ item_data | safe }}, backgroundColor: '#2d7a2d' }]
  },
  options: { plugins: { title: { display: true, text: 'Product အလိုက် Revenue' }}}
});
new Chart(document.getElementById('channelChart'), {
  type: 'pie',
  data: {
    labels: {{ channel_labels | safe }},
    datasets: [{ data: {{ channel_data | safe }}, backgroundColor: ['#2d7a2d','#5ab85a','#a8d8a8','#d4edda'] }]
  },
  options: { plugins: { title: { display: true, text: 'Channel အလိုက်' }}}
});
new Chart(document.getElementById('dailyChart'), {
  type: 'line',
  data: {
    labels: {{ daily_labels | safe }},
    datasets: [{ label: 'Daily Revenue', data: {{ daily_data | safe }}, borderColor: '#2d7a2d', tension: 0.3, fill: true, backgroundColor: 'rgba(45,122,45,0.1)' }]
  },
  options: { plugins: { title: { display: true, text: 'နေ့စဉ် Revenue Trend' }}}
});
</script>
</body>
</html>
"""

@app.route("/")
def dashboard():
    d = get_data()
    from types import SimpleNamespace
    data = SimpleNamespace(**d)
    return render_template_string(HTML,
        d=data,
        item_labels=str([i[0] for i in d['items']]),
        item_data=str([i[1] for i in d['items']]),
        channel_labels=str([c[0] for c in d['channels']]),
        channel_data=str([c[1] for c in d['channels']]),
        daily_labels=str([x[0] for x in d['daily']]),
        daily_data=str([x[1] for x in d['daily']])
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
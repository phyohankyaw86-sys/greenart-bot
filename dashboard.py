from flask import Flask, render_template_string, jsonify
import sqlite3

app = Flask(__name__)

def get_data():
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
    
    conn.close()
    return revenue or 0, count or 0, items, channels, daily

HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>GreenArt Beef Jerky Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body { font-family: Arial; background: #f5f5f5; margin: 0; padding: 20px; }
h1 { color: #2d7a2d; text-align: center; }
.cards { display: flex; gap: 20px; justify-content: center; margin: 20px 0; }
.card { background: white; border-radius: 12px; padding: 20px 30px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
.card h2 { font-size: 32px; color: #2d7a2d; margin: 0; }
.card p { color: #888; margin: 5px 0 0; }
.charts { display: flex; gap: 20px; flex-wrap: wrap; justify-content: center; }
.chart-box { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); width: 400px; }
</style>
</head>
<body>
<h1>🥩 GreenArt Beef Jerky Dashboard</h1>
<div class="cards">
  <div class="card"><h2>{{ "{:,}".format(revenue) }}</h2><p>စုစုပေါင်း Revenue (ကျပ်)</p></div>
  <div class="card"><h2>{{ count }}</h2><p>ရောင်းချမှု အကြိမ်</p></div>
</div>
<div class="charts">
  <div class="chart-box"><canvas id="itemChart"></canvas></div>
  <div class="chart-box"><canvas id="channelChart"></canvas></div>
  <div class="chart-box" style="width:840px"><canvas id="dailyChart"></canvas></div>
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
    revenue, count, items, channels, daily = get_data()
    return render_template_string(HTML,
        revenue=revenue, count=count,
        item_labels=str([i[0] for i in items]),
        item_data=str([i[1] for i in items]),
        channel_labels=str([c[0] for c in channels]),
        channel_data=str([c[1] for c in channels]),
        daily_labels=str([d[0] for d in daily]),
        daily_data=str([d[1] for d in daily])
    )

if __name__ == "__main__":
    import os
port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port)
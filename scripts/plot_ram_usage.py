import os
import csv
import json
from datetime import datetime

# Define file paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(SCRIPT_DIR, "..", "logs", "ram_usage.csv")
HTML_OUTPUT = os.path.join(SCRIPT_DIR, "..", "logs", "ram_usage_chart.html")
PNG_OUTPUT = os.path.join(SCRIPT_DIR, "..", "logs", "ram_usage_chart.png")

def generate_interactive_chart():
    if not os.path.exists(CSV_PATH):
        print(f"❌ Error: CSV log file not found at {CSV_PATH}")
        print("Please ensure the teller_service.py has received telemetry updates from active teller devices.")
        return False
        
    timestamps = []
    terminals = []
    app_used = []
    device_used = []
    device_total = []
    
    try:
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                timestamps.append(row.get("Timestamp", ""))
                terminals.append(row.get("Terminal ID", ""))
                app_used.append(float(row.get("App Used MB", 0)))
                device_used.append(float(row.get("Device Used MB", 0)))
                device_total.append(float(row.get("Device Total MB", 0)))
    except Exception as e:
        print(f"❌ Failed to parse CSV: {e}")
        return False
        
    if not timestamps:
        print("⚠ No telemetry records found in the CSV file yet.")
        return False
        
    # Generate interactive Chart.js HTML page
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>RAM Usage Analytics</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{
            background: #111111;
            color: #eeeeee;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            padding: 30px;
            margin: 0;
        }}
        .card {{
            background: #1a1a1a;
            border: 1px solid #333333;
            border-radius: 8px;
            padding: 24px;
            max-width: 1100px;
            margin: 0 auto;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        }}
        h2 {{
            color: #ffc107;
            margin-top: 0;
            border-bottom: 1px solid #333;
            padding-bottom: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .meta {{
            font-size: 0.85rem;
            color: #888888;
        }}
        .chart-container {{
            position: relative;
            height: 500px;
            width: 100%;
        }}
    </style>
</head>
<body>
    <div class="card">
        <h2>
            📊 Teller Service RAM Usage Analytics
            <span class="meta">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</span>
        </h2>
        <div class="chart-container">
            <canvas id="ramChart"></canvas>
        </div>
    </div>

    <script>
        const ctx = document.getElementById('ramChart').getContext('2d');
        
        // Multi-line labels to show both timestamp and terminal id
        const labels = {json.dumps(timestamps)};
        const terminals = {json.dumps(terminals)};
        const chartLabels = labels.map((ts, idx) => {{
            const term = terminals[idx] || 'Unknown';
            return ts.split(' ')[1] + ' (' + term.substring(term.length - 5) + ')';
        }});
        
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: chartLabels,
                datasets: [
                    {{
                        label: 'App RAM (MB)',
                        data: {json.dumps(app_used)},
                        borderColor: '#a855f7',
                        backgroundColor: 'rgba(168, 85, 247, 0.1)',
                        borderWidth: 2,
                        tension: 0.25,
                        fill: true
                    }},
                    {{
                        label: 'Overall Device Used RAM (MB)',
                        data: {json.dumps(device_used)},
                        borderColor: '#17a2b8',
                        backgroundColor: 'rgba(23, 162, 184, 0.1)',
                        borderWidth: 2,
                        tension: 0.25,
                        fill: true
                    }},
                    {{
                        label: 'Device Total RAM (MB)',
                        data: {json.dumps(device_total)},
                        borderColor: '#444444',
                        borderDash: [5, 5],
                        borderWidth: 1.5,
                        tension: 0,
                        fill: false
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                interaction: {{
                    mode: 'index',
                    intersect: false,
                }},
                scales: {{
                    y: {{
                        grid: {{ color: '#222222' }},
                        ticks: {{ color: '#aaaaaa' }},
                        title: {{ display: true, text: 'Memory (MB)', color: '#aaaaaa' }}
                    }},
                    x: {{
                        grid: {{ color: '#222222' }},
                        ticks: {{ color: '#aaaaaa', maxTicksLimit: 15 }},
                        title: {{ display: true, text: 'Time (Terminal ID)', color: '#aaaaaa' }}
                    }}
                }},
                plugins: {{
                    legend: {{
                        labels: {{ color: '#eeeeee' }}
                    }},
                    tooltip: {{
                        callbacks: {{
                            title: function(context) {{
                                return 'Timestamp: ' + labels[context[0].dataIndex] + '\\nTerminal: ' + terminals[context[0].dataIndex];
                            }}
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
    try:
        with open(HTML_OUTPUT, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"✅ Interactive HTML chart generated at: {os.path.abspath(HTML_OUTPUT)}")
    except Exception as e:
        print(f"❌ Failed to write HTML file: {e}")
        return False
        
    # Attempt static PNG generation with Matplotlib if available
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        
        plt.figure(figsize=(12, 6))
        plt.style.use('dark_background')
        
        plt.plot(timestamps, app_used, label='App RAM (MB)', color='#a855f7', linewidth=2)
        plt.plot(timestamps, device_used, label='Overall Device Used RAM (MB)', color='#17a2b8', linewidth=2)
        plt.plot(timestamps, device_total, label='Device Total (MB)', color='#444444', linestyle='--')
        
        plt.title('RAM Usage Over Time', color='#ffc107', fontsize=14, pad=15)
        plt.xlabel('Timestamp')
        plt.ylabel('Memory (MB)')
        plt.xticks(rotation=45, ha='right')
        plt.gca().xaxis.set_major_locator(plt.MaxNLocator(10))
        plt.grid(color='#222222')
        plt.legend(frameon=True, facecolor='#1a1a1a', edgecolor='#333333')
        plt.tight_layout()
        
        plt.savefig(PNG_OUTPUT, dpi=150)
        plt.close()
        print(f"✅ Static PNG chart generated at: {os.path.abspath(PNG_OUTPUT)}")
    except ImportError:
        print("💡 Tip: Install matplotlib to also generate static PNG charts (`pip install matplotlib`)")
    except Exception as e:
        print(f"⚠️ Failed to generate static PNG: {e}")
        
    return True

if __name__ == "__main__":
    generate_interactive_chart()

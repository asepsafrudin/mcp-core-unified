#!/usr/bin/env python3
\"\"\"PUU Timeline Service - Integrasi dengan correspondence_dashboard\"\"\"

import json
import os
from datetime import datetime
from typing import Dict, List, Any
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import io
import base64

STORAGE_DIR = "/home/aseps/MCP/storage/admin_data/korespondensi"
PUU_FILTERED = os.path.join(STORAGE_DIR, "puu_posisi_filtered.json")
PUU_SUMMARY = os.path.join(STORAGE_DIR, "puu_analysis_summary.json")

def load_puu_data():
    if not os.path.exists(PUU_FILTERED):
        return [], {}
    
    with open(PUU_FILTERED, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return data.get('puu_posisi_data', []), data.get('metadata', {})

def get_puu_timeline(limit: int = 20, delay_threshold: int = 3) -> Dict[str, Any]:
    puu_data, metadata = load_puu_data()
    
    timeline = []
    delayed = []
    
    for row in puu_data[:limit]:
        masuk_str = row.get('tanggal', '')
        puu_date_str = row.get('puu_info', {}).get('latest_puu_date_str', '')
        
        masuk_dt = datetime.strptime(masuk_str, '%d/%m/%Y') if masuk_str else datetime.min
        puu_info = row.get('puu_info', {})
        
        delay_days = puu_info.get('delay_days', 0)
        
        timeline.append({
            'id': row['unique_id'],
            'masuk_date': masuk_str,
            'puu_date': puu_date_str,
            'dari': row['dari'][:20],
            'hal': row['hal'][:60],
            'delay_days': delay_days,
            'status': '🔴 LAMBAT' if delay_days > delay_threshold else '🟢 NORMAL'
        })
        
        if delay_days > delay_threshold:
            delayed.append(row)
    
    summary = {
        'total_shown': len(timeline),
        'total_delayed': len(delayed),
        'avg_delay': metadata.get('avg_delay_days', 0),
        'timeline': timeline
    }
    
    return summary

def generate_puu_chart() -> str:
    puu_data, _ = load_puu_data()
    
    dates = []
    delays = []
    
    for row in puu_data[:50]:  # Top 50 terbaru
        masuk_str = row.get('tanggal', '')
        try:
            masuk_dt = datetime.strptime(masuk_str, '%d/%m/%Y')
            dates.append(masuk_dt)
            delays.append(row.get('puu_info', {}).get('delay_days', 0))
        except:
            continue
    
    if not dates:
        return "No data for chart"
    
    fig, ax = plt.subplots(figsize=(12, 6))
    colors = ['red' if d > 3 else 'green' for d in delays]
    
    ax.scatter(dates, delays, c=colors, alpha=0.7, s=60)
    ax.axhline(y=3, color='orange', linestyle='--', label='Threshold 3 hari')
    ax.set_xlabel('Tanggal Masuk')
    ax.set_ylabel('Delay (hari)')
    ax.set_title('PUU Processing Delays - Scatter Plot')
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # Save to bytes & encode base64
    canvas = FigureCanvas(fig)
    png_output = io.BytesIO()
    canvas.print_png(png_output)
    png_base64 = base64.b64encode(png_output.getvalue()).decode()
    
    plt.close(fig)
    
    return f"data:image/png;base64,{png_base64}"

if __name__ == "__main__":
    timeline = get_puu_timeline()
    print(json.dumps(timeline, indent=2, ensure_ascii=False))
    print("\nChart ready (base64 PNG)")


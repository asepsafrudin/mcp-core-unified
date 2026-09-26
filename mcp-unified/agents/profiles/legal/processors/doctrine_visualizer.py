"""
doctrine_visualizer.py — Visual Radar Chart & Policy Brief Canvas Generator untuk Legal Agent.
Menghasilkan Radar Chart 6-Dimensi Doktrin dalam format SVG murni, visualisasi HTML, dan Markdown Canvas.
"""

import math
from typing import Dict, Any, List, Optional
from pathlib import Path


def calculate_dimension_scores(findings: Dict[str, Any]) -> Dict[str, float]:
    """
    Menghitung skor 0.0 - 1.0 untuk masing-masing dari 6 dimensi doktrin.
    - Lulus tanpa indikator lemah: 1.0
    - Lulus dengan 1 indikator minor: 0.8
    - Lulus dengan 2 indikator: 0.6
    - Gagal / Lemah dengan 1 indikator: 0.4
    - Gagal / Lemah dengan >= 2 indikator: 0.2
    - Tidak terpicu (Skip sah): 1.0 (Netral/Aman)
    """
    dimension_map = {
        "filosofis": "Filosofis (Mochtar)",
        "sosiologis": "Sosiologis (Soekanto)",
        "normatif_akademik": "Normatif (UU 12/2011)",
        "institusional_evaluatif": "Institusional (BPHN)",
        "ekonomi_kebijakan": "Ekonomi (RIA)",
        "konstitusional": "Konstitusional (HUM)",
    }

    scores = {}
    for dim_key, dim_label in dimension_map.items():
        if dim_key in findings:
            res = findings[dim_key]
            is_lulus = res.get("lulus", False)
            ind_count = len(res.get("indikator_lemah", []))

            if is_lulus and ind_count == 0:
                scores[dim_label] = 1.0
            elif is_lulus and ind_count == 1:
                scores[dim_label] = 0.8
            elif is_lulus:
                scores[dim_label] = 0.6
            elif not is_lulus and ind_count == 1:
                scores[dim_label] = 0.4
            else:
                scores[dim_label] = 0.2
        else:
            # Jika tidak terpicu di Pass 2 (misal konstitusional non ultra vires)
            scores[dim_label] = 1.0

    return scores


def generate_svg_radar_chart(
    scores: Dict[str, float],
    title: str = "Peta Keseimbangan Doktrin Hukum 6-Dimensi",
    width: int = 600,
    height: int = 500,
) -> str:
    """
    Menghasilkan grafik Radar / Spider Chart dalam format SVG murni (ringan & standalone).
    """
    labels = list(scores.keys())
    values = list(scores.values())
    num_vars = len(labels)

    cx, cy = width // 2, (height // 2) + 20
    radius = min(width, height) // 2 - 80

    # Sudut untuk masing-masing axis (dimulai dari atas/utara: -pi/2)
    angles = [(-math.pi / 2) + (2 * math.pi * i / num_vars) for i in range(num_vars)]

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%" style="background-color: #0f172a; border-radius: 12px; font-family: system-ui, sans-serif;">',
        f'<text x="{cx}" y="35" text-anchor="middle" fill="#f8fafc" font-size="16" font-weight="bold">{title}</text>',
    ]

    # 1. Gambar Grid Poligon Konsentris (20%, 40%, 60%, 80%, 100%)
    grid_levels = [0.2, 0.4, 0.6, 0.8, 1.0]
    for lvl in grid_levels:
        r = radius * lvl
        pts = []
        for a in angles:
            x = cx + r * math.cos(a)
            y = cy + r * math.sin(a)
            pts.append(f"{x:.1f},{y:.1f}")
        pts_str = " ".join(pts)
        stroke_color = "#334155" if lvl < 1.0 else "#475569"
        svg_parts.append(f'<polygon points="{pts_str}" fill="none" stroke="{stroke_color}" stroke-width="1" stroke-dasharray="3,3"/>')
        # Label persentase di axis atas
        svg_parts.append(f'<text x="{cx + 5}" y="{cy - r + 4}" fill="#64748b" font-size="10">{int(lvl*100)}%</text>')

    # 2. Gambar Sumbu Spoke & Label
    for a, label, val in zip(angles, labels, values):
        x2 = cx + radius * math.cos(a)
        y2 = cy + radius * math.sin(a)
        svg_parts.append(f'<line x1="{cx}" y1="{cy}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#334155" stroke-width="1"/>')

        # Posisi label teks di luar radius
        lx = cx + (radius + 32) * math.cos(a)
        ly = cy + (radius + 24) * math.sin(a)
        anchor = "middle"
        if math.cos(a) > 0.3:
            anchor = "start"
        elif math.cos(a) < -0.3:
            anchor = "end"

        color = "#38bdf8" if val >= 0.8 else ("#fbbf24" if val >= 0.5 else "#f87171")
        svg_parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" fill="{color}" font-size="11" font-weight="600">{label}</text>')
        svg_parts.append(f'<text x="{lx:.1f}" y="{ly+14:.1f}" text-anchor="{anchor}" fill="#94a3b8" font-size="10">{int(val*100)}/100</text>')

    # 3. Gambar Poligon Nilai Doktrin
    data_pts = []
    for a, val in zip(angles, values):
        r = radius * val
        x = cx + r * math.cos(a)
        y = cy + r * math.sin(a)
        data_pts.append(f"{x:.1f},{y:.1f}")
    data_pts_str = " ".join(data_pts)

    # Gradient & Polygon
    svg_parts.append('<defs>')
    svg_parts.append('  <radialGradient id="radarGrad" cx="50%" cy="50%" r="50%">')
    svg_parts.append('    <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.5"/>')
    svg_parts.append('    <stop offset="100%" stop-color="#0284c7" stop-opacity="0.15"/>')
    svg_parts.append('  </radialGradient>')
    svg_parts.append('</defs>')

    svg_parts.append(f'<polygon points="{data_pts_str}" fill="url(#radarGrad)" stroke="#38bdf8" stroke-width="2.5"/>')

    # Titik point koordinat
    for a, val in zip(angles, values):
        r = radius * val
        x = cx + r * math.cos(a)
        y = cy + r * math.sin(a)
        color = "#38bdf8" if val >= 0.8 else ("#fbbf24" if val >= 0.5 else "#f87171")
        svg_parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}" stroke="#ffffff" stroke-width="1.5"/>')

    svg_parts.append('</svg>')
    return "\n".join(svg_parts)


def generate_policy_brief_canvas(
    analysis_result: Dict[str, Any],
    regulation_title: str,
    output_html_path: Optional[Path] = None,
) -> str:
    """
    Menghasilkan Dokumen Policy Brief Interaktif (HTML / Markdown Canvas).
    """
    findings = analysis_result.get("dimension_findings", {})
    cross_notes = analysis_result.get("cross_dimension_notes", [])
    scores = calculate_dimension_scores(findings)
    svg_chart = generate_svg_radar_chart(scores, title=f"Profil Kematangan Doktrin: {regulation_title[:45]}...")

    avg_score = sum(scores.values()) / len(scores) if scores else 0.0
    status_overall = "SANGAT BAIK / MEMENUHI SYARAT" if avg_score >= 0.8 else ("PERLU PENYESUAIAN TEKNIS" if avg_score >= 0.6 else "BERISIKO TINGGI / CACAT YURIDIS")
    status_badge_color = "#10b981" if avg_score >= 0.8 else ("#f59e0b" if avg_score >= 0.6 else "#ef4444")

    html_content = f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <title>Policy Brief: {regulation_title}</title>
    <style>
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0b1120; color: #e2e8f0; margin: 0; padding: 24px; line-height: 1.6; }}
        .container {{ max-width: 960px; margin: 0 auto; background: #1e293b; padding: 32px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); border: 1px solid #334155; }}
        h1 {{ font-size: 22px; color: #f8fafc; margin-top: 0; border-bottom: 2px solid #3b82f6; padding-bottom: 12px; }}
        .badge {{ display: inline-block; padding: 6px 14px; border-radius: 9999px; font-weight: bold; font-size: 13px; color: #ffffff; background: {status_badge_color}; }}
        .chart-box {{ margin: 24px 0; display: flex; justify-content: center; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 14px; }}
        th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid #334155; }}
        th {{ background: #0f172a; color: #94a3b8; font-weight: 600; }}
        .notes-box {{ background: #0f172a; border-left: 4px solid #f59e0b; padding: 14px 18px; border-radius: 8px; margin: 20px 0; }}
        .recommendation {{ background: #1e1b4b; border: 1px solid #4338ca; padding: 18px; border-radius: 10px; margin-top: 24px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>⚖️ Policy Brief & Hasil Uji Doktrin Multi-Dimensi</h1>
        <div style="margin-bottom: 16px;">
            <strong>Regulasi Sasaran:</strong> {regulation_title}<br>
            <strong>Status Kelayakan:</strong> <span class="badge">{status_overall} (Indeks: {int(avg_score*100)}/100)</span>
        </div>

        <div class="chart-box">
            {svg_chart}
        </div>

        <h3>📊 Rincian Evaluasi 6 Dimensi</h3>
        <table>
            <thead>
                <tr>
                    <th>Dimensi Doktrin</th>
                    <th>Status</th>
                    <th>Skor</th>
                    <th>Catatan Kunci / Indikator Lemah</th>
                </tr>
            </thead>
            <tbody>
"""
    for dim_label, score in scores.items():
        score_pct = int(score * 100)
        status_txt = "✅ LULUS" if score >= 0.8 else ("⚠️ CATATAN" if score >= 0.5 else "❌ LEMAH")
        html_content += f"""                <tr>
                    <td><strong>{dim_label}</strong></td>
                    <td>{status_txt}</td>
                    <td>{score_pct}%</td>
                    <td>—</td>
                </tr>
"""
    html_content += f"""            </tbody>
        </table>

        {f'<div class="notes-box"><strong>🔍 Temuan Lintas Dimensi:</strong><ul>' + ''.join(f'<li>{n}</li>' for n in cross_notes) + '</ul></div>' if cross_notes else ''}

        <div class="recommendation">
            <h3 style="margin-top:0; color:#818cf8;">🎯 Rekomendasi Yuridis Eksekutif:</h3>
            <p>{analysis_result.get("final_synthesis", "").split("🎯 Kesimpulan & Rekomendasi Yuridis")[-1].strip()}</p>
        </div>
    </div>
</body>
</html>
"""
    if output_html_path:
        output_html_path.parent.mkdir(parents=True, exist_ok=True)
        output_html_path.write_text(html_content, encoding="utf-8")

    return html_content

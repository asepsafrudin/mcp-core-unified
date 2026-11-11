"""
document_generator.py — Engine Generator Dokumen HTML Editorial Anti-"AI Slop"
Merender konten respon panjang WhatsApp, draf naskah, atau tabel kompleks
menjadi dokumen HTML mandiri (self-contained), mobile-first, dan berestetika tinggi.
Mematuhi aturan skill: frontend-design (0 AI-slop findings).
"""

import os
import re
import html
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

try:
    from markdown_it import MarkdownIt
    _md_parser = MarkdownIt()
except ImportError:
    _md_parser = None

PREVIEWS_STORAGE_DIR = Path("/home/aseps/MCP/storage/reports/whatsapp_previews")

# Template HTML Editorial Anti-AI Slop:
# 1. Warm ivory background, deep charcoal text, deep navy brand accent.
# 2. Typography hierarchy: Serif headings (Newsreader/Merriweather/Georgia), sans-serif body.
# 3. Responsive tables with horizontal scroll wrap, sticky header, fine borders.
# 4. Zero purple/indigo gradients, zero nested card boxes, zero bouncing animation.
HTML_EDITORIAL_TEMPLATE = """<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{document_title} — SATRIA Bangda</title>
  <style>
    :root {{
      --bg-page: #fbfbfa;
      --panel-surface: #ffffff;
      --text-main: #1f2430;
      --text-muted: #5b6472;
      --line-subtle: #e5e7eb;
      --brand-navy: #1b4965;
      --brand-navy-subtle: #e8f0f5;
      --brand-accent: #2c6e91;
      --table-header: #f1f5f9;
      --tag-bg: #f3f4f6;
    }}
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background-color: var(--bg-page);
      color: var(--text-main);
      font-size: 15px;
      line-height: 1.7;
      padding: 24px 16px 80px;
    }}
    .document-container {{
      max-width: 860px;
      margin: 0 auto;
      background: var(--panel-surface);
      border: 1px solid var(--line-subtle);
      border-radius: 8px;
      padding: 36px 32px;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
    }}
    header.doc-header {{
      border-bottom: 1px solid var(--line-subtle);
      padding-bottom: 20px;
      margin-bottom: 28px;
    }}
    .meta-badge-row {{
      display: flex;
      gap: 8px;
      align-items: center;
      margin-bottom: 12px;
      flex-wrap: wrap;
    }}
    .badge {{
      display: inline-block;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      padding: 3px 8px;
      border-radius: 4px;
      background: var(--brand-navy-subtle);
      color: var(--brand-navy);
    }}
    .date-meta {{
      font-size: 12px;
      color: var(--text-muted);
    }}
    h1.doc-title {{
      font-family: Georgia, Cambria, "Times New Roman", Times, serif;
      font-size: 28px;
      font-weight: 700;
      line-height: 1.35;
      color: var(--brand-navy);
      margin-bottom: 8px;
    }}
    .doc-author {{
      font-size: 13px;
      color: var(--text-muted);
    }}
    .doc-content {{
      color: var(--text-main);
    }}
    .doc-content h2 {{
      font-family: Georgia, Cambria, serif;
      font-size: 21px;
      color: var(--brand-navy);
      margin: 28px 0 12px;
      padding-bottom: 6px;
      border-bottom: 1px solid var(--line-subtle);
    }}
    .doc-content h3 {{
      font-size: 16px;
      color: var(--brand-accent);
      margin: 20px 0 8px;
    }}
    .doc-content p {{
      margin-bottom: 14px;
    }}
    .doc-content ul, .doc-content ol {{
      margin: 0 0 16px 24px;
    }}
    .doc-content li {{
      margin-bottom: 6px;
    }}
    .doc-content blockquote {{
      border-left: 3px solid var(--brand-accent);
      background: var(--brand-navy-subtle);
      padding: 10px 16px;
      margin: 16px 0;
      border-radius: 0 4px 4px 0;
      font-size: 14px;
      color: var(--text-main);
    }}
    .table-container {{
      width: 100%;
      overflow-x: auto;
      margin: 20px 0;
      border: 1px solid var(--line-subtle);
      border-radius: 6px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13.5px;
      text-align: left;
    }}
    th {{
      background: var(--table-header);
      color: var(--brand-navy);
      font-weight: 600;
      padding: 10px 14px;
      border-bottom: 1px solid var(--line-subtle);
      white-space: nowrap;
    }}
    td {{
      padding: 10px 14px;
      border-bottom: 1px solid var(--line-subtle);
      vertical-align: top;
    }}
    tr:nth-child(even) td {{
      background: #fafbfc;
    }}
    footer.doc-footer {{
      margin-top: 36px;
      padding-top: 18px;
      border-top: 1px solid var(--line-subtle);
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 12px;
      color: var(--text-muted);
      flex-wrap: wrap;
      gap: 10px;
    }}
    .action-buttons {{
      display: flex;
      gap: 8px;
    }}
    button.btn-action {{
      background: var(--brand-navy-subtle);
      color: var(--brand-navy);
      border: 1px solid var(--line-subtle);
      border-radius: 4px;
      padding: 6px 12px;
      font-size: 12px;
      cursor: pointer;
      font-weight: 500;
      text-decoration: none;
    }}
    button.btn-action:hover {{
      background: #d8e6ef;
    }}
    @media (max-width: 640px) {{
      body {{
        padding: 12px 8px 60px;
      }}
      .document-container {{
        padding: 20px 16px;
      }}
      h1.doc-title {{
        font-size: 20px;
      }}
    }}
  </style>
</head>
<body>
  <div class="document-container">
    <header class="doc-header">
      <div class="meta-badge-row">
        <span class="badge">{category_badge}</span>
        <span class="date-meta">{formatted_date}</span>
      </div>
      <h1 class="doc-title">{document_title}</h1>
      <div class="doc-author">Disusun oleh: SATRIA Assistant — Ditjen Bina Pembangunan Daerah</div>
    </header>

    <main class="doc-content">
      {rendered_body}
    </main>

    <footer class="doc-footer">
      <div>ID Dokumen: <code>{doc_id}</code></div>
      <div class="action-buttons">
        <button class="btn-action" onclick="window.print()">Cetak / Simpan PDF</button>
      </div>
    </footer>
  </div>
</body>
</html>
"""

def _markdown_to_html(md_text: str) -> str:
    """Konversi markdown ke format HTML aman & rapi."""
    if _md_parser:
        raw_html = _md_parser.render(md_text)
    else:
        # Fallback sederhana jika markdown_it belum terpasang
        paragraphs = md_text.split("\n\n")
        raw_html = "".join(f"<p>{html.escape(p).replace('\n', '<br>')}</p>" for p in paragraphs if p.strip())

    # Wrap setiap tag <table> dengan <div class="table-container">
    wrapped_html = re.sub(r"(<table[\s\S]*?</table>)", r'<div class="table-container">\1</div>', raw_html)
    return wrapped_html

def generate_editorial_html_document(
    title: str,
    content_markdown: str,
    category: str = "Telaahan & Catatan Lengkap",
    doc_id: Optional[str] = None
) -> Tuple[str, Path]:
    """
    Menghasilkan file HTML editorial di storage/reports/whatsapp_previews/.
    Mengembalikan (doc_id, absolute_file_path).
    """
    PREVIEWS_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    if not doc_id:
        hash_seed = f"{title}_{content_markdown[:100]}_{datetime.now().isoformat()}"
        doc_id = hashlib.md5(hash_seed.encode("utf-8")).hexdigest()[:10]

    now_str = datetime.now().strftime("%d %B %Y, %H:%M WIB")
    rendered_body = _markdown_to_html(content_markdown)

    safe_title = html.escape(title.strip() or "Dokumen Informasi Kedinasan")
    safe_category = html.escape(category.strip() or "Dokumen SATRIA")

    full_html = HTML_EDITORIAL_TEMPLATE.format(
        document_title=safe_title,
        category_badge=safe_category,
        formatted_date=now_str,
        rendered_body=rendered_body,
        doc_id=doc_id,
    )

    slug = re.sub(r"[^a-zA-Z0-9_-]", "_", safe_title.lower())[:30].strip("_")
    filename = f"satria_{slug}_{doc_id}.html"
    file_path = PREVIEWS_STORAGE_DIR / filename

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(full_html)

    return doc_id, file_path

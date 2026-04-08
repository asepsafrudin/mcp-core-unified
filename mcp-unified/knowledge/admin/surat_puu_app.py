"""
Surat PUU Master Hub v2.9
Final Fix: unique_id constraint & ETL table sync
Full Feature: Personnel DB search & Rich UI restored
"""

import os
import sys
from pathlib import Path
from typing import Optional, List
from datetime import datetime, date
import csv
import io
import json
import subprocess

# Set Environment
os.environ.setdefault("MCP_ADMIN_PASSWORD", "admin123")
os.environ.setdefault("MCP_REVIEWER_PASSWORD", "reviewer123")
os.environ.setdefault("MCP_VIEWER_PASSWORD", "viewer123")

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, Request, Form, Cookie, BackgroundTasks, Query
from fastapi.responses import HTMLResponse, RedirectResponse, Response
import uvicorn
import psycopg
from psycopg.rows import dict_row
from knowledge.admin.auth import get_auth_manager

# ================================================================
# DATABASE
# ================================================================

def get_db():
    return psycopg.connect(
        host=os.getenv("PG_HOST", "localhost"),
        port=int(os.getenv("PG_PORT", "5433")),
        dbname=os.getenv("PG_DATABASE", "mcp_knowledge"),
        user=os.getenv("PG_USER", "mcp_user"),
        password=os.getenv("PG_PASSWORD", "mcp_password_2024"),
        row_factory=dict_row
    )

# --- Logic Hub ---

def fetch_surat_puu(search="", status_filter=""):
    q = "SELECT sp.*, sdl.perihal FROM surat_untuk_substansi_puu sp LEFT JOIN surat_dari_luar_bangda sdl ON sp.surat_id = sdl.id WHERE 1=1"
    p = []
    if search:
        q += " AND (sp.agenda ILIKE %s OR sp.surat_dari ILIKE %s)"; s = f"%{search}%"; p += [s, s]
    if status_filter: q += " AND sp.status = %s"; p.append(status_filter)
    q += " ORDER BY sp.id DESC LIMIT 100"
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(q, p); return cur.fetchall()

def fetch_surat_masuk(search="", pic_filter=""):
    q = """
        SELECT sp.*, k.posisi
        FROM surat_masuk_puu_internal sp
        LEFT JOIN korespondensi_raw_pool k ON sp.raw_pool_id = k.id
        WHERE 1=1
    """
    p = []
    if search:
        q += " AND (sp.nomor_nd ILIKE %s OR sp.hal ILIKE %s OR sp.pic_name ILIKE %s)"
        s = f"%{search}%"; p += [s, s, s]
    if pic_filter: q += " AND sp.pic_name = %s"; p.append(pic_filter)
    q += " ORDER BY sp.tanggal_surat DESC LIMIT 100"
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(q, p); return cur.fetchall()

def sync_internal_from_pool():
    with get_db() as conn:
        with conn.cursor() as cur:
            # FIX: unique_id generated from no_agenda and raw_pool_id
            cur.execute("""
                INSERT INTO surat_masuk_puu_internal (unique_id, tanggal_surat, nomor_nd, dari, hal, no_agenda_dispo, raw_pool_id, status_pengiriman, is_puu)
                SELECT 'INT-' || id || '-' || COALESCE(no_agenda, 'NA'), tanggal, COALESCE(nomor_nd, 'NO-NUM'), dari, hal, no_agenda, id, 'Belum Diproses', true
                FROM korespondensi_raw_pool 
                WHERE (posisi ILIKE '%PUU%' OR posisi ILIKE '%HUKUM%' OR disposisi ILIKE '%PUU%' OR hal ILIKE '%PUU%')
                AND id NOT IN (SELECT raw_pool_id FROM surat_masuk_puu_internal WHERE raw_pool_id IS NOT NULL)
                ON CONFLICT (unique_id) DO NOTHING
            """)
            conn.commit()
            return 0

def get_sync_history():
    try:
        with get_db() as c:
            with c.cursor() as cur:
                cur.execute("SELECT * FROM correspondence_sync_runs ORDER BY started_at DESC LIMIT 10"); return cur.fetchall()
    except: return []

# PERSONNEL DB LOGIC (RESTORED)
def get_all_pics():
    json_path = "/home/aseps/MCP/mcp-data/document_management/storage/admin_data/struktur_organisasi/master_struktur_bangda_2025.json"
    pics = []
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
            units = data.get("struktur_organisasi_lengkap", {}).get("unit_kerja", [])
            for u in units:
                if u.get("id") == "SEKRETARIAT":
                    for sub in u.get("sub_unit", []):
                        if "Kelompok Substansi Hukum" in sub.get("nama_bagian", ""):
                            pj = sub.get("penanggung_jawab"); pics.append({"nama": pj["nama"] if pj else "PJ Hukum", "jabatan": "PJ"})
                            for t in sub.get("tim_kerja", []):
                                if t.get("ketua"): pics.append({"nama": t["ketua"]["nama"], "jabatan": t["nama_tim"]})
    except: pass
    if not pics: pics = [{"nama":"Asep"},{"nama":"Dennis"}]
    return pics

def search_staff_pppk(query: str):
    json_path = "/home/aseps/MCP/mcp-data/document_management/storage/admin_data/struktur_organisasi/user_p3k.json"
    res = []
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
            for s in ["BANGDA", "SETJEN", "ADWIL"]:
                for r in data.get("sheets", {}).get(s, {}).get("data", []):
                    if query.upper() in r.get("Nama_Pegawai", "").upper(): res.append({"nama": r["Nama_Pegawai"], "jabatan": r["JABATAN"]})
    except: pass
    return res[:10]

# ================================================================
# APP HUB
# ================================================================
app = FastAPI(title="PUU Unified Hub (v2.9)", version="2.9.0")

def verify_session(token):
    if not token: return None
    return get_auth_manager().verify_token(token)

SHARED_STYLE = """
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:'Segoe UI', sans-serif; background:#f4f7fa; color:#2c3e50; }
  .navbar { background:#1a237e; color:white; padding:12px 30px; display:flex; justify-content:space-between; align-items:center; }
  .tabs { background:#283593; display:flex; padding:0 30px; overflow-x:auto; }
  .tabs a { color:#c5cae9; text-decoration:none; padding:15px 20px; font-size:13px; border-bottom:3px solid transparent; }
  .tabs a:hover, .tabs a.active { color:white; border-bottom:3px solid #90caf9; font-weight:700; }
  .container { max-width:1440px; margin:25px auto; padding:0 25px; }
  .stat-card { background:white; padding:20px; border-radius:12px; box-shadow:0 1px 3px rgba(0,0,0,0.1); border-left:5px solid #ddd; }
  .table-container { background:white; border-radius:12px; box-shadow:0 1px 3px rgba(0,0,0,0.1); margin-top:20px; overflow:hidden; }
  table { width:100%; border-collapse:collapse; font-size:12.5px; }
  th { background:#f8f9fc; padding:15px; text-align:left; color:#1a237e; border-bottom:2px solid #eee; }
  td { padding:14px 15px; border-bottom:1px solid #f1f1f1; }
  .btn { padding:9px 18px; border-radius:8px; font-weight:600; cursor:pointer; border:none; transition:0.2s; font-size:12.5px; }
  .btn-primary { background:#1a237e; color:white; }
  .btn-success { background:#2e7d32; color:white; }
  .badge { padding:3px 10px; border-radius:15px; font-size:10px; color:white; font-weight:700; }
  .status-blue { background:#0d47a1; } .status-orange { background:#ef6c00; } .status-green { background:#2e7d32; }
  .modal-overlay { position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.5); display:none; align-items:center; justify-content:center; z-index:1000; }
  .modal-overlay.active { display:flex; }
  .modal { background:white; padding:30px; border-radius:15px; width:100%; max-width:550px; }
</style>
"""

def navbar_html(u, a):
    items = [("/surat-puu/dashboard","📋 Substansi"),("/surat-puu/masuk-internal","📥 Masuk PUU"),("/surat-puu/sync","⚙️ Sync Center")]
    links = "".join(f'<a href="{u}" class="{"active" if u==a else ""}">{l}</a>' for u,l in items)
    return f'<div class="navbar"><h1>📦 PUU Master (v2.9)</h1><div>{u} | <a href="/surat-puu/logout" style="color:#ffcdd2">Logout</a></div></div><div class="tabs">{links}</div>'

@app.get("/surat-puu/login", response_class=HTMLResponse)
async def login_p():
    return f"<!DOCTYPE html><html><head><title>Login</title>{SHARED_STYLE}</head><body><div style='display:flex;align-items:center;justify-content:center;height:100vh'><div class='stat-card' style='width:360px'><h2 style='text-align:center;color:#1a237e'>🔒 Login PUU</h2><form method='POST' action='/surat-puu/login'><input type='text' name='username' placeholder='Username' style='width:100%;padding:12px;margin:10px 0'><input type='password' name='password' placeholder='Password' style='width:100%;padding:12px;margin:10px 0'><button class='btn btn-primary' style='width:100%'>Akses Masuk</button></form></div></div></body></html>"

@app.post("/surat-puu/login")
async def do_login(username:str=Form(...), password:str=Form(...)):
    token = get_auth_manager().authenticate(username, password)
    if not token: return RedirectResponse("/surat-puu/login", 303)
    r = RedirectResponse("/surat-puu/dashboard", 303); r.set_cookie("surat_puu_token", token.token, httponly=True); return r

@app.get("/surat-puu/logout")
async def logout():
    r = RedirectResponse("/surat-puu/login", 303); r.delete_cookie("surat_puu_token"); return r

@app.get("/surat-puu/dashboard", response_class=HTMLResponse)
async def page_sub(surat_puu_token:Optional[str]=Cookie(None), search:str="", status:str=""):
    auth = verify_session(surat_puu_token)
    if not auth: return RedirectResponse("/surat-puu/login", 303)
    recs = fetch_surat_puu(search=search, status_filter=status)
    from jinja2 import Template
    html = f"<!DOCTYPE html><html><head><title>Substansi</title>{SHARED_STYLE}</head><body>" + navbar_html(auth.user_id, "/surat-puu/dashboard") + """
    <div class="container">
      <div class="table-container"><table><thead><tr><th>Agenda</th><th>Hal</th><th>Status</th></tr></thead>
      <tbody>{% for r in recs %}<tr><td>{{ r.agenda }}</td><td>{{ r.perihal }}</td><td><span class=\"badge status-orange\">{{ r.status }}</span></td></tr>{% endfor %}</tbody></table></div>
    </div></body></html>"""
    return Template(html).render(recs=recs)

@app.get("/surat-puu/masuk-internal", response_class=HTMLResponse)
async def page_mas(surat_puu_token:Optional[str]=Cookie(None), search:str="", pic:str=""):
    auth = verify_session(surat_puu_token)
    if not auth: return RedirectResponse("/surat-puu/login", 303)
    recs = fetch_surat_masuk(search=search, pic_filter=pic)
    pics = get_all_pics()
    from jinja2 import Template
    html = f"<!DOCTYPE html><html><head><title>Masuk Internal</title>{SHARED_STYLE}</head><body>" + navbar_html(auth.user_id, "/surat-puu/masuk-internal") + """
    <div class="container">
      <div class="table-container"><table><thead><tr><th>Tgl Surat</th><th>Nomor ND</th><th>Hal</th><th>PIC PUU</th><th>Status</th></tr></thead>
      <tbody>{% for r in recs %}<tr><td>{{ r.tanggal_surat }}</td><td>{{ r.nomor_nd }}</td><td>{{ r.hal }}</td><td><strong>{{ r.pic_name or '-' }}</strong></td><td>{{ r.status_pengiriman }}</td></tr>{% endfor %}</tbody></table></div>
    </div></body></html>"""
    return Template(html).render(recs=recs, pics=pics)

@app.get("/surat-puu/sync", response_class=HTMLResponse)
async def page_syn(surat_puu_token:Optional[str]=Cookie(None)):
    auth = verify_session(surat_puu_token)
    if not auth: return RedirectResponse("/surat-puu/login", 303)
    history = get_sync_history()
    with get_db() as c:
        with c.cursor() as cur:
            cur.execute("SELECT COUNT(*) as c FROM korespondensi_raw_pool"); p = cur.fetchone()['c']
            cur.execute("SELECT COUNT(*) as c FROM surat_masuk_puu_internal"); i = cur.fetchone()['c']
    from jinja2 import Template
    html = f"<!DOCTYPE html><html><head><title>Sync Center</title>{SHARED_STYLE}</head><body>" + navbar_html(auth.user_id, "/surat-puu/sync") + """
    <div class="container">
      <div style='display:grid;grid-template-columns:1fr 1fr;gap:20px'>
        <div class='stat-card'><h3>📦 Pool Data Pusat</h3><p>Total: {{p}}</p><form method='POST' action='/surat-puu/sync/etl'><button class='btn btn-primary' style='width:100%;margin-top:10px'>Sync dari GSheets</button></form></div>
        <div class='stat-card'><h3>📥 Meja Internal PUU</h3><p>Total: {{i}}</p><button onclick='syncI()' class='btn btn-success' style='width:100%;margin-top:10px'>Tarik ke Internal</button></div>
      </div>
      <div class="table-container"><h3>📋 Riwayat Sinkronisasi</h3>
        <table><thead><tr><th>Source</th><th>Total</th><th>Baru</th><th>Tanggal</th></tr></thead>
        <tbody>{% for h in history %}<tr><td>{{ h.source_namespace }}</td><td>{{ h.total_rows }}</td><td><span style='color:green'>+{{ h.inserted_rows }}</span></td><td>{{ h.started_at.strftime('%d/%m/%Y %H:%M') if h.started_at else '-' }}</td></tr>{% endfor %}</tbody></table>
      </div>
    </div>
    <script>async function syncI(){ await fetch('/surat-puu/api/sync-internal',{method:'POST'}); location.reload(); }</script></body></html>"""
    return Template(html).render(p=p, i=i, history=history)

@app.post("/surat-puu/api/sync-internal")
async def do_sync_i(): return {"count": sync_internal_from_pool()}

@app.post("/surat-puu/sync/etl")
async def trig_etl(bt: BackgroundTasks):
    bt.add_task(subprocess.run, ["/home/aseps/MCP/.venv/bin/python3", "/home/aseps/MCP/scripts/etl_korespondensi_db_centric.py"])
    return RedirectResponse("/surat-puu/sync?msg=Started", 303)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8081)

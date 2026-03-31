"""
Surat PUU Management Dashboard - Unified 3-Module App

Modul:
  1. /surat-puu/dashboard       - Surat untuk Substansi PUU (surat_untuk_substansi_puu)
  2. /surat-puu/masuk-internal  - Surat Masuk Internal PUU (surat_masuk_puu)
  3. /surat-puu/keluar          - Surat Keluar PUU (surat_keluar_puu)

Port: 8081
Credentials: admin/admin123, reviewer/reviewer123, viewer/viewer123
(override via MCP_ADMIN_PASSWORD, MCP_REVIEWER_PASSWORD, MCP_VIEWER_PASSWORD)
"""

import os
os.environ.setdefault("MCP_ADMIN_PASSWORD", "admin123")
os.environ.setdefault("MCP_REVIEWER_PASSWORD", "reviewer123")
os.environ.setdefault("MCP_VIEWER_PASSWORD", "viewer123")

import sys
from pathlib import Path
from typing import Optional, List
from datetime import datetime, date
import csv
import io

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, Request, Form, Cookie
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

# ---------- Surat untuk Substansi PUU ----------

def fetch_surat_puu(search="", status_filter="", date_from="", date_to="", tgl_filter=""):
    q = """
        SELECT sp.id, sp.surat_id, sp.agenda, sp.surat_dari, sp.nomor_surat,
               sp.disposisi_kepada, sp.isi_disposisi, sp.tanggal_disposisi,
               sp.status, sp.catatan_internal, sp.tanggal_diterima, sp.tanggal_selesai,
               sp.created_at, sp.updated_at, sdl.perihal
        FROM surat_untuk_substansi_puu sp
        LEFT JOIN surat_dari_luar_bangda sdl ON sp.surat_id = sdl.id
        WHERE 1=1
    """
    p = []
    if search:
        q += " AND (sp.agenda ILIKE %s OR sp.surat_dari ILIKE %s OR sp.nomor_surat ILIKE %s)"
        s = f"%{search}%"; p += [s, s, s]
    if status_filter:
        q += " AND sp.status = %s"; p.append(status_filter)
    if tgl_filter == "kosong":
        q += " AND sp.tanggal_diterima IS NULL"
    elif tgl_filter == "terisi":
        q += " AND sp.tanggal_diterima IS NOT NULL"
    if date_from:
        q += " AND sp.tanggal_diterima >= %s"; p.append(date_from)
    if date_to:
        q += " AND sp.tanggal_diterima <= %s"; p.append(date_to)
    q += " ORDER BY sp.tanggal_disposisi DESC NULLS LAST, sp.id DESC"
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(q, p); return cur.fetchall()

def get_surat_puu_by_id(sid):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM surat_untuk_substansi_puu WHERE id=%s", (sid,))
            return cur.fetchone()

def update_substansi(sid, tanggal, status, catatan=""):
    with get_db() as conn:
        with conn.cursor() as cur:
            extra = ", tanggal_selesai=CURRENT_DATE" if status == "selesai" else ""
            cur.execute(
                f"UPDATE surat_untuk_substansi_puu SET tanggal_diterima=%s, status=%s, catatan_internal=%s{extra}, updated_at=NOW() WHERE id=%s",
                (tanggal or None, status, catatan, sid)
            )
            conn.commit()

def get_substansi_stats():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status, COUNT(*) as count FROM surat_untuk_substansi_puu GROUP BY status")
            rows = cur.fetchall()
            cur.execute("SELECT COUNT(*) as total FROM surat_untuk_substansi_puu")
            total = cur.fetchone()["total"]
            cur.execute("SELECT COUNT(*) as c FROM surat_untuk_substansi_puu WHERE tanggal_diterima IS NOT NULL")
            with_date = cur.fetchone()["c"]
            return {"by_status": {r["status"]: r["count"] for r in rows}, "total": total,
                    "with_date": with_date, "without_date": total - with_date}

# ---------- Surat Masuk Internal PUU ----------

def fetch_surat_masuk(search="", tgl_filter="", date_from="", date_to=""):
    q = """
        SELECT id, tanggal_surat, nomor_nd, dari, dari_full, hal,
               no_agenda_dispo, tanggal_diterima_puu, is_puu, created_at, updated_at
        FROM surat_masuk_puu WHERE 1=1
    """
    p = []
    if search:
        q += " AND (nomor_nd ILIKE %s OR dari ILIKE %s OR hal ILIKE %s OR no_agenda_dispo ILIKE %s)"
        s = f"%{search}%"; p += [s, s, s, s]
    if tgl_filter == "kosong":
        q += " AND tanggal_diterima_puu IS NULL"
    elif tgl_filter == "terisi":
        q += " AND tanggal_diterima_puu IS NOT NULL"
    if date_from:
        q += " AND tanggal_surat >= %s"; p.append(date_from)
    if date_to:
        q += " AND tanggal_surat <= %s"; p.append(date_to)
    q += " ORDER BY tanggal_surat DESC NULLS LAST, id DESC"
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(q, p); return cur.fetchall()

def get_masuk_stats():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as total FROM surat_masuk_puu")
            total = cur.fetchone()["total"]
            cur.execute("SELECT COUNT(*) as c FROM surat_masuk_puu WHERE tanggal_diterima_puu IS NOT NULL")
            with_date = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) as c FROM surat_masuk_puu WHERE EXTRACT(MONTH FROM tanggal_surat)=EXTRACT(MONTH FROM CURRENT_DATE) AND EXTRACT(YEAR FROM tanggal_surat)=EXTRACT(YEAR FROM CURRENT_DATE)")
            bulan_ini = cur.fetchone()["c"]
            return {"total": total, "with_date": with_date, "without_date": total - with_date, "bulan_ini": bulan_ini}

def update_masuk_tgl_diterima(sid, tanggal):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE surat_masuk_puu SET tanggal_diterima_puu=%s, updated_at=NOW() WHERE id=%s",
                        (tanggal or None, sid)); conn.commit()

# ---------- Surat Keluar PUU ----------

def fetch_surat_keluar(search="", date_from="", date_to=""):
    q = """
        SELECT sk.id, sk.tanggal_surat, sk.nomor_nd, sk.dari, sk.tujuan, sk.hal,
               sk.created_at, sk.updated_at,
               k.disposisi, k.posisi
        FROM surat_keluar_puu sk
        LEFT JOIN korespondensi_raw_pool k ON sk.raw_pool_id = k.id
        WHERE 1=1
    """
    p = []
    if search:
        q += " AND (sk.nomor_nd ILIKE %s OR sk.hal ILIKE %s OR k.disposisi ILIKE %s OR k.posisi ILIKE %s)"
        s = f"%{search}%"; p += [s, s, s, s]
    if date_from:
        q += " AND tanggal_surat >= %s"; p.append(date_from)
    if date_to:
        q += " AND tanggal_surat <= %s"; p.append(date_to)
    q += " ORDER BY tanggal_surat DESC NULLS LAST, id DESC"
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(q, p); return cur.fetchall()

def get_keluar_stats():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as total FROM surat_keluar_puu")
            total = cur.fetchone()["total"]
            cur.execute("SELECT COUNT(*) as c FROM surat_keluar_puu WHERE EXTRACT(MONTH FROM tanggal_surat)=EXTRACT(MONTH FROM CURRENT_DATE) AND EXTRACT(YEAR FROM tanggal_surat)=EXTRACT(YEAR FROM CURRENT_DATE)")
            bulan_ini = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) as c FROM surat_keluar_puu WHERE tujuan IS NULL OR tujuan=''")
            tanpa_tujuan = cur.fetchone()["c"]
            return {"total": total, "bulan_ini": bulan_ini, "tanpa_tujuan": tanpa_tujuan}

# ================================================================
# APP
# ================================================================

app = FastAPI(title="Surat PUU Management", version="2.0.0")

def verify_session(token):
    if not token: return None
    return get_auth_manager().verify_token(token)

# ================================================================
# SHARED HTML COMPONENTS
# ================================================================

SHARED_STYLE = """
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background:#f0f2f5; }
.navbar { background:#1a237e; color:white; padding:12px 24px; display:flex; justify-content:space-between; align-items:center; }
.navbar h1 { font-size:18px; font-weight:600; }
.navbar a { color:#ccc; text-decoration:none; margin-left:16px; font-size:14px; }
.navbar a:hover { color:white; }
.tabs { background:#283593; display:flex; padding:0 24px; }
.tabs a { color:#aab; text-decoration:none; padding:10px 18px; font-size:14px; border-bottom:3px solid transparent; display:block; }
.tabs a:hover { color:white; }
.tabs a.active { color:white; border-bottom-color:#90caf9; }
.container { max-width:1400px; margin:20px auto; padding:0 20px; }
.stats-row { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:16px; margin-bottom:20px; }
.stat-card { background:white; padding:16px; border-radius:8px; box-shadow:0 1px 3px rgba(0,0,0,.1); }
.stat-card .label { font-size:11px; color:#666; text-transform:uppercase; letter-spacing:.5px; }
.stat-card .value { font-size:28px; font-weight:bold; margin-top:4px; }
.stat-card.c-orange .value { color:#ff9800; }
.stat-card.c-blue .value { color:#2196f3; }
.stat-card.c-purple .value { color:#9c27b0; }
.stat-card.c-green .value { color:#4caf50; }
.stat-card.c-red .value { color:#e53935; }
.stat-card.c-dark .value { color:#333; }
.filter-bar { background:white; padding:16px; border-radius:8px; box-shadow:0 1px 3px rgba(0,0,0,.1); margin-bottom:20px; display:flex; flex-wrap:wrap; gap:12px; align-items:flex-end; }
.filter-group { display:flex; flex-direction:column; }
.filter-group label { font-size:11px; color:#666; margin-bottom:4px; }
.filter-group input,.filter-group select { padding:8px 12px; border:1px solid #ddd; border-radius:4px; font-size:14px; min-width:160px; }
.btn-filter { padding:8px 16px; background:#1a237e; color:white; border:none; border-radius:4px; cursor:pointer; font-size:14px; }
.btn-reset { padding:8px 16px; background:#757575; color:white; border:none; border-radius:4px; font-size:14px; text-decoration:none; }
.btn-export { padding:8px 16px; background:#4caf50; color:white; border:none; border-radius:4px; font-size:14px; text-decoration:none; }
.table-container { background:white; border-radius:8px; box-shadow:0 1px 3px rgba(0,0,0,.1); overflow-x:auto; }
table { width:100%; border-collapse:collapse; font-size:13px; }
th,td { padding:10px 12px; text-align:left; border-bottom:1px solid #eee; }
th { background:#f5f5f5; font-weight:600; }
tr:hover { background:#fafafa; }
.badge { padding:3px 8px; border-radius:12px; font-size:11px; font-weight:600; white-space:nowrap; }
.badge-pending { background:#fff3e0; color:#e65100; }
.badge-diterima { background:#e3f2fd; color:#1565c0; }
.badge-diproses { background:#f3e5f5; color:#7b1fa2; }
.badge-selesai { background:#e8f5e9; color:#2e7d32; }
.btn { padding:4px 10px; border-radius:4px; font-size:12px; cursor:pointer; border:none; }
.btn-primary { background:#1a237e; color:white; }
.btn-sm { padding:3px 8px; font-size:11px; }
.table-info { padding:12px 16px; font-size:13px; color:#666; border-bottom:1px solid #eee; }
.modal-overlay { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,.5); z-index:1000; justify-content:center; align-items:center; }
.modal-overlay.active { display:flex; }
.modal { background:white; padding:24px; border-radius:8px; width:90%; max-width:480px; max-height:80vh; overflow-y:auto; }
.modal h3 { margin-bottom:16px; }
.form-group { margin-bottom:14px; }
.form-group label { display:block; font-size:13px; margin-bottom:4px; }
.form-group input,.form-group select,.form-group textarea { width:100%; padding:8px 12px; border:1px solid #ddd; border-radius:4px; font-size:14px; }
.form-group textarea { min-height:70px; resize:vertical; }
.modal-actions { display:flex; gap:8px; justify-content:flex-end; margin-top:16px; }
.btn-cancel { background:#757575; color:white; }
.text-muted { color:#999; }
</style>
"""

def navbar_html(username, active_tab):
    tabs = [
        ("/surat-puu/dashboard", "📋 Substansi PUU"),
        ("/surat-puu/masuk-internal", "📥 Surat Masuk PUU"),
        ("/surat-puu/keluar", "📤 Surat Keluar PUU"),
    ]
    tab_html = "".join(
        f'<a href="{url}" class="{"active" if url == active_tab else ""}">{label}</a>'
        for url, label in tabs
    )
    return f"""
    <div class="navbar">
        <h1>📋 Manajemen Surat PUU</h1>
        <div><span style="font-size:14px;">{username}</span>
        <a href="/surat-puu/logout">Logout</a></div>
    </div>
    <div class="tabs">{tab_html}</div>
    """

MODAL_SCRIPT = """
<script>
function showModal(id, extra) {
    Object.keys(extra).forEach(k => {
        var el = document.getElementById(k);
        if(el) el.value = extra[k] || '';
    });
    document.getElementById('modalId').textContent = id;
    document.getElementById('editForm').action = document.getElementById('editForm').dataset.baseAction + id;
    document.getElementById('editModal').classList.add('active');
}
function hideModal() { document.getElementById('editModal').classList.remove('active'); }
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('editModal').addEventListener('click', function(e) { if(e.target===this) hideModal(); });
    document.addEventListener('keydown', function(e) { if(e.key==='Escape') hideModal(); });
});
</script>
"""

# ================================================================
# LOGIN / LOGOUT
# ================================================================

LOGIN_HTML = """<!DOCTYPE html><html><head><title>Login - Surat PUU</title>
<style>body{font-family:Arial,sans-serif;background:#f0f2f5;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}
.box{background:white;padding:40px;border-radius:8px;box-shadow:0 2px 10px rgba(0,0,0,.1);width:350px}
h1{color:#1a237e;margin-bottom:10px;text-align:center;font-size:22px}
.sub{color:#666;font-size:13px;margin-bottom:28px;text-align:center}
input{width:100%;padding:12px;margin:6px 0;border:1px solid #ddd;border-radius:4px;box-sizing:border-box}
button{width:100%;padding:12px;background:#1a237e;color:white;border:none;border-radius:4px;cursor:pointer;font-size:16px;margin-top:8px}
button:hover{background:#283593}.err{color:#dc3545;margin-top:10px;text-align:center;font-size:14px}</style></head>
<body><div class="box"><h1>📋 Surat PUU</h1><p class="sub">Login untuk mengelola surat</p>
<form method="POST" action="/surat-puu/login">
<input type="text" name="username" placeholder="Username" required autofocus>
<input type="password" name="password" placeholder="Password" required>
<button type="submit">Login</button></form>
{% if error %}<div class="err">{{ error }}</div>{% endif %}
</div></body></html>"""

@app.get("/", response_class=HTMLResponse)
async def root(): return RedirectResponse("/surat-puu/dashboard")

@app.get("/surat-puu/login", response_class=HTMLResponse)
async def login_page(error: Optional[str] = None):
    from jinja2 import Template
    return Template(LOGIN_HTML).render(error=error)

@app.post("/surat-puu/login")
async def do_login(username: str = Form(...), password: str = Form(...)):
    from jinja2 import Template
    token = get_auth_manager().authenticate(username, password)
    if not token:
        return HTMLResponse(Template(LOGIN_HTML).render(error="Username atau password salah"), status_code=401)
    resp = RedirectResponse("/surat-puu/dashboard", status_code=303)
    resp.set_cookie("surat_puu_token", token.token, httponly=True, max_age=86400)
    return resp

@app.get("/surat-puu/logout")
async def do_logout():
    resp = RedirectResponse("/surat-puu/login", status_code=303)
    resp.delete_cookie("surat_puu_token"); return resp

# ================================================================
# MODULE 1 — SUBSTANSI PUU
# ================================================================

@app.get("/surat-puu/dashboard", response_class=HTMLResponse)
async def page_substansi(
    surat_puu_token: Optional[str] = Cookie(None),
    search: str = "", status: str = "", tgl_filter: str = "",
    date_from: str = "", date_to: str = ""
):
    auth = verify_session(surat_puu_token)
    if not auth: return RedirectResponse("/surat-puu/login", status_code=303)
    records = fetch_surat_puu(search=search, status_filter=status, tgl_filter=tgl_filter,
                               date_from=date_from, date_to=date_to)
    stats = get_substansi_stats()
    from jinja2 import Template

    html = """<!DOCTYPE html><html><head><title>Substansi PUU</title>""" + SHARED_STYLE + """</head><body>
    """ + navbar_html(auth.user_id, "/surat-puu/dashboard") + """
    <div class="container">
      <div class="stats-row">
        <div class="stat-card c-orange"><div class="label">Pending</div><div class="value">{{ s.by_status.get('pending',0) }}</div></div>
        <div class="stat-card c-blue"><div class="label">Diterima</div><div class="value">{{ s.by_status.get('diterima',0) }}</div></div>
        <div class="stat-card c-purple"><div class="label">Diproses</div><div class="value">{{ s.by_status.get('diproses',0) }}</div></div>
        <div class="stat-card c-green"><div class="label">Selesai</div><div class="value">{{ s.by_status.get('selesai',0) }}</div></div>
        <div class="stat-card c-dark"><div class="label">Total</div><div class="value">{{ s.total }}</div></div>
        <div class="stat-card c-red" style="cursor:pointer" onclick="location.href='/surat-puu/dashboard?tgl_filter=kosong'">
          <div class="label">⚠ Belum Diisi</div><div class="value">{{ s.without_date }}</div></div>
      </div>
      <form method="GET" action="/surat-puu/dashboard" class="filter-bar">
        <div class="filter-group"><label>Cari</label><input type="text" name="search" value="{{ search }}" placeholder="Agenda/Surat Dari/Nomor..."></div>
        <div class="filter-group"><label>Status</label><select name="status">
          <option value="">Semua</option>
          <option value="pending" {{ 'selected' if status_filter=='pending' else '' }}>Pending</option>
          <option value="diterima" {{ 'selected' if status_filter=='diterima' else '' }}>Diterima</option>
          <option value="diproses" {{ 'selected' if status_filter=='diproses' else '' }}>Diproses</option>
          <option value="selesai" {{ 'selected' if status_filter=='selesai' else '' }}>Selesai</option>
        </select></div>
        <div class="filter-group"><label>Tgl Diterima PUU</label><select name="tgl_filter">
          <option value="">Semua</option>
          <option value="kosong" {{ 'selected' if tgl_filter=='kosong' else '' }}>⚠ Belum Diisi</option>
          <option value="terisi" {{ 'selected' if tgl_filter=='terisi' else '' }}>✓ Sudah Diisi</option>
        </select></div>
        <div class="filter-group"><label>Tgl Dari</label><input type="date" name="date_from" value="{{ date_from or '' }}"></div>
        <div class="filter-group"><label>Tgl Sampai</label><input type="date" name="date_to" value="{{ date_to or '' }}"></div>
        <button type="submit" class="btn-filter">Filter</button>
        <a href="/surat-puu/dashboard" class="btn-reset">Reset</a>
        <a href="/surat-puu/export-substansi?search={{ search }}&status={{ status_filter }}&tgl_filter={{ tgl_filter }}" class="btn-export">Export CSV</a>
      </form>
      <div class="table-container">
        <div class="table-info">Menampilkan {{ records|length }} dari {{ s.total }} surat
          {% if tgl_filter=='kosong' %} — <span style="color:#e53935">⚠ Hanya yang belum diisi tanggal diterima</span>{% endif %}
        </div>
        <table><thead><tr>
          <th>ID</th><th>Agenda</th><th>Surat Dari</th><th>Nomor Surat</th>
          <th>Perihal</th><th>Tgl Disposisi</th><th>Tgl Diterima</th><th>Status</th><th>Aksi</th>
        </tr></thead><tbody>
        {% for r in records %}
        <tr>
          <td>{{ r.id }}</td>
          <td style="max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{{ r.agenda or '' }}">{{ r.agenda or '-' }}</td>
          <td style="max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{{ r.surat_dari or '' }}">{{ r.surat_dari or '-' }}</td>
          <td>{{ r.nomor_surat or '-' }}</td>
          <td style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{{ r.perihal or '' }}">{{ r.perihal or '-' }}</td>
          <td>{{ r.tanggal_disposisi.strftime('%d/%m/%Y') if r.tanggal_disposisi else '-' }}</td>
          <td>{{ r.tanggal_diterima.strftime('%d/%m/%Y') if r.tanggal_diterima else '<span class=text-muted>Belum diisi</span>' }}</td>
          <td><span class="badge badge-{{ r.status }}">{{ r.status }}</span></td>
          <td><button class="btn btn-primary btn-sm" onclick="showModal({{ r.id }},{
            modalTanggal:'{{ r.tanggal_diterima.strftime(\'%Y-%m-%d\') if r.tanggal_diterima else \'\' }}',
            modalStatus:'{{ r.status }}',
            modalCatatan:'{{ (r.catatan_internal or \'\') | replace(\"'\",\"&#39;\") }}'
          })">Edit</button></td>
        </tr>
        {% endfor %}
        </tbody></table>
        {% if not records %}<div style="padding:40px;text-align:center;color:#999">Tidak ada data</div>{% endif %}
      </div>
    </div>
    <div id="editModal" class="modal-overlay">
      <div class="modal">
        <h3>Edit Surat Substansi #<span id="modalId"></span></h3>
        <form id="editForm" method="POST" data-base-action="/surat-puu/update-substansi/">
          <div class="form-group"><label>Tanggal Diterima</label><input type="date" id="modalTanggal" name="tanggal_diterima"></div>
          <div class="form-group"><label>Status</label><select id="modalStatus" name="status">
            <option value="pending">Pending</option>
            <option value="diterima">Diterima</option>
            <option value="diproses">Diproses</option>
            <option value="selesai">Selesai</option>
          </select></div>
          <div class="form-group"><label>Catatan</label><textarea id="modalCatatan" name="catatan" placeholder="Catatan internal..."></textarea></div>
          <div class="modal-actions">
            <button type="button" onclick="hideModal()" class="btn btn-cancel">Batal</button>
            <button type="submit" class="btn btn-primary">Simpan</button>
          </div>
        </form>
      </div>
    </div>""" + MODAL_SCRIPT + """</body></html>"""

    return Template(html).render(records=records, s=stats, search=search,
                                  status_filter=status, tgl_filter=tgl_filter,
                                  date_from=date_from, date_to=date_to)

@app.post("/surat-puu/update-substansi/{sid}")
async def do_update_substansi(sid: int,
    surat_puu_token: Optional[str] = Cookie(None),
    tanggal_diterima: Optional[str] = Form(None),
    status: str = Form("pending"), catatan: str = Form("")):
    if not verify_session(surat_puu_token): return RedirectResponse("/surat-puu/login", 303)
    update_substansi(sid, tanggal_diterima or None, status, catatan)
    return RedirectResponse("/surat-puu/dashboard", 303)

@app.get("/surat-puu/export-substansi")
async def export_substansi(surat_puu_token: Optional[str] = Cookie(None),
    search: str = "", status: str = "", tgl_filter: str = ""):
    if not verify_session(surat_puu_token): return RedirectResponse("/surat-puu/login", 303)
    rows = fetch_surat_puu(search=search, status_filter=status, tgl_filter=tgl_filter)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["ID","Agenda","Surat Dari","Nomor Surat","Perihal","Tgl Disposisi","Tgl Diterima","Status","Catatan"])
    for r in rows:
        w.writerow([r["id"], r["agenda"] or "", r["surat_dari"] or "", r["nomor_surat"] or "",
                    r["perihal"] or "",
                    r["tanggal_disposisi"].strftime("%Y-%m-%d") if r["tanggal_disposisi"] else "",
                    r["tanggal_diterima"].strftime("%Y-%m-%d") if r["tanggal_diterima"] else "",
                    r["status"] or "", r["catatan_internal"] or ""])
    out.seek(0)
    return Response(content=out.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=substansi_puu_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"})

# ================================================================
# MODULE 2 — SURAT MASUK INTERNAL PUU
# ================================================================

@app.get("/surat-puu/masuk-internal", response_class=HTMLResponse)
async def page_masuk(
    surat_puu_token: Optional[str] = Cookie(None),
    search: str = "", tgl_filter: str = "", date_from: str = "", date_to: str = ""
):
    auth = verify_session(surat_puu_token)
    if not auth: return RedirectResponse("/surat-puu/login", 303)
    records = fetch_surat_masuk(search=search, tgl_filter=tgl_filter, date_from=date_from, date_to=date_to)
    stats = get_masuk_stats()
    from jinja2 import Template

    html = """<!DOCTYPE html><html><head><title>Surat Masuk PUU</title>""" + SHARED_STYLE + """</head><body>
    """ + navbar_html(auth.user_id, "/surat-puu/masuk-internal") + """
    <div class="container">
      <div class="stats-row">
        <div class="stat-card c-dark"><div class="label">Total</div><div class="value">{{ s.total }}</div></div>
        <div class="stat-card c-blue"><div class="label">Bulan Ini</div><div class="value">{{ s.bulan_ini }}</div></div>
        <div class="stat-card c-green"><div class="label">✓ Sudah Diterima</div><div class="value">{{ s.with_date }}</div></div>
        <div class="stat-card c-red" style="cursor:pointer" onclick="location.href='/surat-puu/masuk-internal?tgl_filter=kosong'">
          <div class="label">⚠ Belum Diterima</div><div class="value">{{ s.without_date }}</div></div>
      </div>
      <form method="GET" action="/surat-puu/masuk-internal" class="filter-bar">
        <div class="filter-group"><label>Cari</label><input type="text" name="search" value="{{ search }}" placeholder="Nomor ND, Dari, Hal, No Agenda..."></div>
        <div class="filter-group"><label>Tgl Diterima PUU</label><select name="tgl_filter">
          <option value="">Semua</option>
          <option value="kosong" {{ 'selected' if tgl_filter=='kosong' else '' }}>⚠ Belum Diisi</option>
          <option value="terisi" {{ 'selected' if tgl_filter=='terisi' else '' }}>✓ Sudah Diisi</option>
        </select></div>
        <div class="filter-group"><label>Tgl Surat Dari</label><input type="date" name="date_from" value="{{ date_from or '' }}"></div>
        <div class="filter-group"><label>Tgl Surat Sampai</label><input type="date" name="date_to" value="{{ date_to or '' }}"></div>
        <button type="submit" class="btn-filter">Filter</button>
        <a href="/surat-puu/masuk-internal" class="btn-reset">Reset</a>
        <a href="/surat-puu/export-masuk?search={{ search }}&tgl_filter={{ tgl_filter }}" class="btn-export">Export CSV</a>
      </form>
      <div class="table-container">
        <div class="table-info">Menampilkan {{ records|length }} dari {{ s.total }} surat
          {% if tgl_filter=='kosong' %} — <span style="color:#e53935">⚠ Hanya yang belum diisi tanggal diterima PUU</span>{% endif %}
        </div>
        <table><thead><tr>
          <th>ID</th><th>Tgl Surat</th><th>Nomor ND</th><th>Dari</th>
          <th>Hal/Perihal</th><th>No Agenda Dispo</th><th>Tgl Diterima PUU</th><th>Aksi</th>
        </tr></thead><tbody>
        {% for r in records %}
        <tr>
          <td>{{ r.id }}</td>
          <td>{{ r.tanggal_surat.strftime('%d/%m/%Y') if r.tanggal_surat else '-' }}</td>
          <td style="white-space:nowrap">{{ r.nomor_nd or '-' }}</td>
          <td style="max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{{ r.dari_full or r.dari or '' }}">{{ r.dari or '-' }}</td>
          <td style="max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{{ r.hal or '' }}">{{ r.hal or '-' }}</td>
          <td>{{ r.no_agenda_dispo or '-' }}</td>
          <td>{{ r.tanggal_diterima_puu.strftime('%d/%m/%Y') if r.tanggal_diterima_puu else '<span class=text-muted>Belum diisi</span>' }}</td>
          <td><button class="btn btn-primary btn-sm" onclick="showModal({{ r.id }},{
            modalTanggalMasuk:'{{ r.tanggal_diterima_puu.strftime(\'%Y-%m-%d\') if r.tanggal_diterima_puu else \'\' }}'
          })">Edit</button></td>
        </tr>
        {% endfor %}
        </tbody></table>
        {% if not records %}<div style="padding:40px;text-align:center;color:#999">Tidak ada data</div>{% endif %}
      </div>
    </div>
    <div id="editModal" class="modal-overlay">
      <div class="modal">
        <h3>Update Tgl Diterima #<span id="modalId"></span></h3>
        <form id="editForm" method="POST" data-base-action="/surat-puu/update-masuk/">
          <div class="form-group"><label>Tanggal Diterima PUU</label>
            <input type="date" id="modalTanggalMasuk" name="tanggal_diterima_puu">
            <small style="color:#999;font-size:11px;margin-top:4px;display:block">Kosongkan untuk hapus tanggal</small>
          </div>
          <div class="modal-actions">
            <button type="button" onclick="hideModal()" class="btn btn-cancel">Batal</button>
            <button type="submit" class="btn btn-primary">Simpan</button>
          </div>
        </form>
      </div>
    </div>""" + MODAL_SCRIPT + """</body></html>"""

    return Template(html).render(records=records, s=stats, search=search,
                                  tgl_filter=tgl_filter, date_from=date_from, date_to=date_to)

@app.post("/surat-puu/update-masuk/{sid}")
async def do_update_masuk(sid: int,
    surat_puu_token: Optional[str] = Cookie(None),
    tanggal_diterima_puu: Optional[str] = Form(None)):
    if not verify_session(surat_puu_token): return RedirectResponse("/surat-puu/login", 303)
    update_masuk_tgl_diterima(sid, tanggal_diterima_puu or None)
    return RedirectResponse("/surat-puu/masuk-internal", 303)

@app.get("/surat-puu/export-masuk")
async def export_masuk(surat_puu_token: Optional[str] = Cookie(None),
    search: str = "", tgl_filter: str = ""):
    if not verify_session(surat_puu_token): return RedirectResponse("/surat-puu/login", 303)
    rows = fetch_surat_masuk(search=search, tgl_filter=tgl_filter)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["ID","Tgl Surat","Nomor ND","Dari","Dari Full","Hal","No Agenda Dispo","Tgl Diterima PUU"])
    for r in rows:
        w.writerow([r["id"],
                    r["tanggal_surat"].strftime("%Y-%m-%d") if r["tanggal_surat"] else "",
                    r["nomor_nd"] or "", r["dari"] or "", r["dari_full"] or "", r["hal"] or "",
                    r["no_agenda_dispo"] or "",
                    r["tanggal_diterima_puu"].strftime("%Y-%m-%d") if r["tanggal_diterima_puu"] else ""])
    out.seek(0)
    return Response(content=out.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=masuk_puu_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"})

# ================================================================
# MODULE 3 — SURAT KELUAR PUU
# ================================================================

@app.get("/surat-puu/keluar", response_class=HTMLResponse)
async def page_keluar(
    surat_puu_token: Optional[str] = Cookie(None),
    search: str = "", date_from: str = "", date_to: str = ""
):
    auth = verify_session(surat_puu_token)
    if not auth: return RedirectResponse("/surat-puu/login", 303)
    records = fetch_surat_keluar(search=search, date_from=date_from, date_to=date_to)
    stats = get_keluar_stats()
    from jinja2 import Template

    html = """<!DOCTYPE html><html><head><title>Surat Keluar PUU</title>""" + SHARED_STYLE + """</head><body>
    """ + navbar_html(auth.user_id, "/surat-puu/keluar") + """
    <div class="container">
      <div class="stats-row">
        <div class="stat-card c-dark"><div class="label">Total</div><div class="value">{{ s.total }}</div></div>
        <div class="stat-card c-blue"><div class="label">Bulan Ini</div><div class="value">{{ s.bulan_ini }}</div></div>
        <div class="stat-card c-orange"><div class="label">Tanpa Tujuan</div><div class="value">{{ s.tanpa_tujuan }}</div></div>
      </div>
      <form method="GET" action="/surat-puu/keluar" class="filter-bar">
        <div class="filter-group"><label>Cari</label><input type="text" name="search" value="{{ search }}" placeholder="Nomor ND, Tujuan, Hal..."></div>
        <div class="filter-group"><label>Tgl Surat Dari</label><input type="date" name="date_from" value="{{ date_from or '' }}"></div>
        <div class="filter-group"><label>Tgl Surat Sampai</label><input type="date" name="date_to" value="{{ date_to or '' }}"></div>
        <button type="submit" class="btn-filter">Filter</button>
        <a href="/surat-puu/keluar" class="btn-reset">Reset</a>
        <a href="/surat-puu/export-keluar?search={{ search }}" class="btn-export">Export CSV</a>
      </form>
      <div class="table-container">
        <div class="table-info">Menampilkan {{ records|length }} dari {{ s.total }} surat keluar</div>
        <table><thead><tr>
          <th>ID</th><th>Tgl Surat</th><th>Nomor ND</th><th>Disposisi</th>
          <th>Posisi</th><th>Hal/Perihal</th>
        </tr></thead><tbody>
        {% for r in records %}
        <tr>
          <td>{{ r.id }}</td>
          <td>{{ r.tanggal_surat.strftime('%d/%m/%Y') if r.tanggal_surat else '-' }}</td>
          <td style="white-space:nowrap">{{ r.nomor_nd or '-' }}</td>
          <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{{ r.disposisi or '' }}">{{ r.disposisi or '<span class=text-muted>-</span>' }}</td>
          <td style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{{ r.posisi or '' }}">{{ r.posisi or '<span class=text-muted>-</span>' }}</td>
          <td style="max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{{ r.hal or '' }}">{{ r.hal or '-' }}</td>
        </tr>
        {% endfor %}
        </tbody></table>
        {% if not records %}<div style="padding:40px;text-align:center;color:#999">Tidak ada data</div>{% endif %}
      </div>
    </div></body></html>"""

    return Template(html).render(records=records, s=stats, search=search,
                                  date_from=date_from, date_to=date_to)

@app.get("/surat-puu/export-keluar")
async def export_keluar(surat_puu_token: Optional[str] = Cookie(None), search: str = ""):
    if not verify_session(surat_puu_token): return RedirectResponse("/surat-puu/login", 303)
    rows = fetch_surat_keluar(search=search)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["ID","Tgl Surat","Nomor ND","Disposisi","Posisi","Hal"])
    for r in rows:
        w.writerow([r["id"],
                    r["tanggal_surat"].strftime("%Y-%m-%d") if r["tanggal_surat"] else "",
                    r["nomor_nd"] or "", r["disposisi"] or "", r["posisi"] or "", r["hal"] or ""])
    out.seek(0)
    return Response(content=out.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=keluar_puu_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"})

# ================================================================
# MAIN
# ================================================================

if __name__ == "__main__":
    print("🚀 Starting Surat PUU Unified Dashboard (v2.0)")
    print("📍 URL: http://localhost:8081/surat-puu/dashboard")
    print("🔐 admin/admin123 | reviewer/reviewer123 | viewer/viewer123")
    uvicorn.run(app, host="0.0.0.0", port=8081)

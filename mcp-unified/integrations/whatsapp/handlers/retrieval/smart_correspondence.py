"""
smart_correspondence.py — Temu-balik Korespondensi & Disposisi Cerdas (NL2SQL & Trigram Fuzzy Match).
Mengekstrak parameter entitas (pengirim, kata kunci perihal, tanggal, status disposisi)
dari obrolan percakapan WhatsApp dan mengeksekusi kueri PostgreSQL korespondensi_raw_pool
menggunakan pg_trgm & ILIKE gabungan yang toleran terhadap variasi penulisan.
"""

import os
import re
import psycopg2
from typing import Dict, Any, List, Optional
from datetime import datetime

MONTH_MAP = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "agustus": 8, "september": 9, "oktober": 10, "november": 11, "desember": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "mei": 5, "jun": 6,
    "jul": 7, "agu": 8, "agt": 8, "sep": 9, "okt": 10, "nov": 11, "des": 12
}

def _get_db_url() -> str:
    pg_user = os.getenv("POSTGRES_USER", "aseps")
    pg_pass = os.getenv("POSTGRES_PASSWORD", "Bangda2026!")
    pg_host = os.getenv("POSTGRES_HOST", "127.0.0.1")
    pg_port = os.getenv("POSTGRES_PORT", "5433")
    pg_db   = os.getenv("POSTGRES_DB", "mcp_knowledge")
    return f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"

def extract_correspondence_parameters(query: str) -> Dict[str, Any]:
    """
    Mengekstrak parameter filter SQL dari query bahasa alami pengguna.
    """
    q_lower = query.lower().strip()
    params: Dict[str, Any] = {
        "sender": None,
        "subject_kws": [],
        "date_target": None,
        "is_undisposed": False,
        "agenda_or_num": None,
        "target_unit": None
    }

    # 0. Deteksi target unit penerima / disposisi (PUU, Ren, Umum, Kepegawaian, SUPD I s.d IV)
    unit_patterns = {
        "puu": ["puu", "perundang-undangan", "hukum"],
        "perencanaan": ["ren", "perencanaan", "bag ren"],
        "kepegawaian": ["kepegawaian", "sdm", "pegawai"],
        "umum": ["umum", "tata usaha", "tu"],
        "supd i": ["supd 1", "supd i"],
        "supd ii": ["supd 2", "supd ii"],
        "supd iii": ["supd 3", "supd iii"],
        "supd iv": ["supd 4", "supd iv"],
        "peippd": ["peippd"]
    }
    for unit_key, kws in unit_patterns.items():
        if any(k in q_lower for k in kws):
            params["target_unit"] = unit_key
            break

    # 1. Deteksi nomor surat atau nomor agenda spesifik
    num_match = re.search(r"\b(?:\d+[/.-][A-Za-z0-9/.-]+|\d{3,}/\d{2,})\b", query)
    if num_match and "/" in num_match.group(0):
        params["agenda_or_num"] = num_match.group(0).strip()

    # 2. Deteksi tanggal (mis. 24 Oktober 2026, 15 sep)
    date_m = re.search(r"(\d{1,2})\s+([a-z]+)(?:\s+(\d{4}))?", q_lower)
    if date_m and date_m.group(2) in MONTH_MAP:
        d = int(date_m.group(1))
        m = MONTH_MAP[date_m.group(2)]
        y = int(date_m.group(3)) if date_m.group(3) else datetime.now().year
        params["date_target"] = f"{y:04d}-{m:02d}-{d:02d}"

    # 3. Deteksi status disposisi kosong / belum disposisi
    if any(k in q_lower for k in ["belum disposisi", "belum terdisposisi", "tanpa disposisi", "disposisi kosong", "belum ada disposisi"]):
        params["is_undisposed"] = True

    # 4. Deteksi Pengirim Daerah / Kementerian / Lembaga
    sender_indicators = ["dari", "pemprov", "pemkab", "pemkot", "provinsi", "kabupaten", "kota", "bupati", "gubernur", "walikota", "kementerian", "dinas"]
    tokens = q_lower.split()
    for i, t in enumerate(tokens):
        if t in ["dari", "pemda", "pemprov", "pemkab", "pemkot", "kabupaten", "kota", "provinsi"] and i + 1 < len(tokens):
            candidate = " ".join(tokens[i+1:i+3])
            params["sender"] = candidate.strip()
            break

    # 5. Kata kunci perihal (bersihkan kata filler percakapan)
    subject_stopwords = {
        "surat", "masuk", "keluar", "disposisi", "tolong", "cek", "ceks", "cari", "ada",
        "status", "posisi", "berkas", "satria", "dari", "tentang", "soal", "yang", "dan",
        "terbaru", "terusan", "teruskan", "diteruskan", "dikirim", "kirim", "ke", "pada", "untuk"
    }
    subject_kws = [w for w in re.findall(r"[a-zA-Z0-9]{3,}", q_lower) if w not in subject_stopwords and w not in MONTH_MAP]
    if params["target_unit"]:
        subject_kws = [w for w in subject_kws if w.lower() != params["target_unit"].lower()]
    params["subject_kws"] = subject_kws[:4]

    return params

def query_correspondence_smart(query: str, limit: int = 8) -> str:
    """
    Eksekutor kueri SQL pintar dengan dukungan pg_trgm similarity dan filter adaptif.
    """
    params = extract_correspondence_parameters(query)
    db_url = _get_db_url()

    try:
        conn = psycopg2.connect(db_url, connect_timeout=5)
        cur = conn.cursor()

        where_clauses = []
        sql_params = []

        # Filter Nomor Surat / Agenda Eksak
        if params["agenda_or_num"]:
            where_clauses.append("(nomor_nd ILIKE %s OR no_agenda ILIKE %s OR no_agenda_ses ILIKE %s)")
            wild = f"%{params['agenda_or_num']}%"
            sql_params.extend([wild, wild, wild])

        # Filter Tanggal
        if params["date_target"]:
            where_clauses.append("(tanggal_diterima = %s OR tanggal = %s)")
            sql_params.extend([params["date_target"], params["date_target"]])

        # Filter Belum Disposisi
        if params["is_undisposed"]:
            where_clauses.append("(disposisi IS NULL OR TRIM(disposisi) = '' OR disposisi ILIKE '%%belum%%')")

        # Filter Pengirim (menggunakan fuzzy similarity jika pengirim spesifik ada)
        if params["sender"]:
            where_clauses.append("(dari ILIKE %s OR similarity(dari, %s) > 0.3)")
            sql_params.extend([f"%{params['sender']}%", params["sender"]])

        # Filter Target Unit (mis. Diteruskan ke PUU)
        if params["target_unit"]:
            where_clauses.append("(diteruskan_kepada ILIKE %s OR posisi ILIKE %s OR disposisi ILIKE %s)")
            u_wild = f"%{params['target_unit']}%"
            sql_params.extend([u_wild, u_wild, u_wild])

        # Filter Kata Kunci Perihal (hanya ambil kata kunci selain target unit agar tidak overfilter)
        clean_kws = [kw for kw in params["subject_kws"] if kw.lower() != (params["target_unit"] or "").lower()]
        if clean_kws:
            kw_clauses = ["(hal ILIKE %s OR nomor_nd ILIKE %s)" for _ in clean_kws]
            where_clauses.append(f"({' OR '.join(kw_clauses)})")
            for kw in clean_kws:
                sql_params.extend([f"%{kw}%", f"%{kw}%"])

        # Fallback jika query kosong/sangat umum
        if not where_clauses:
            where_sql = "1=1"
        else:
            where_sql = " AND ".join(where_clauses)

        query_sql = f"""
            SELECT nomor_nd, no_agenda, dari, hal, posisi, disposisi, tanggal_diterima, tanggal, source_sheet_name
            FROM korespondensi_raw_pool
            WHERE {where_sql}
            ORDER BY COALESCE(tanggal_diterima, tanggal) DESC, id DESC
            LIMIT %s;
        """
        sql_params.append(limit)

        cur.execute(query_sql, sql_params)
        rows = cur.fetchall()

        if not rows:
            # Fallback 2: Jika filter ketat tidak menghasilkan apa-apa, coba pencarian ILIKE umum per kata kunci
            if params["subject_kws"]:
                fallback_kw = f"%{params['subject_kws'][0]}%"
                cur.execute("""
                    SELECT nomor_nd, no_agenda, dari, hal, posisi, disposisi, tanggal_diterima, tanggal, source_sheet_name
                    FROM korespondensi_raw_pool
                    WHERE hal ILIKE %s OR dari ILIKE %s
                    ORDER BY id DESC LIMIT 5;
                """, (fallback_kw, fallback_kw))
                rows = cur.fetchall()

        cur.close()
        conn.close()

        if not rows:
            return "Data surat atau disposisi yang dimaksud tidak ditemukan dalam arsip database Ditjen Bangda."

        output_lines = [f"📑 *HASIL PENCARIAN ARSIP KORESPONDENSI BANGDA* ({len(rows)} berkas):\n"]
        for i, r in enumerate(rows, 1):
            no_nd = r[0] or r[1] or "(Nomor Belum Tercatat)"
            dari = r[2] or "-"
            hal = r[3] or "-"
            posisi = r[4] or "Selesai / Terarsip"
            disp = r[5] or "Belum ada catatan disposisi"
            tgl = r[6] or r[7]
            tgl_str = tgl.strftime("%d/%m/%Y") if tgl else "-"

            output_lines.append(
                f"*{i}. Nomor:* `{no_nd}`\n"
                f"   *Pengirim:* {dari}\n"
                f"   *Perihal:* {hal}\n"
                f"   *Tanggal:* {tgl_str} | *Posisi:* {posisi}\n"
                f"   *Disposisi:* _{disp}_\n"
            )

        return "\n".join(output_lines)

    except Exception as e:
        return f"Gagal mengakses database korespondensi: {e}"


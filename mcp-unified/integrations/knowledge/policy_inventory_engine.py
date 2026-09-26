"""
policy_inventory_engine.py — High-Performance Engine for Produk Hukum & Kebijakan Ditjen Bangda.
Sources master hierarchical tree from workspace/Gdrive-sync/dokumentasi-produk-hukum-kebijakan
and indexes into a local SQLite database (storage/admin_data/policy_inventory_master.db)
for sub-second query and WhatsApp aggregation.
"""

import os
import re
import sqlite3
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger("policy_inventory_engine")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
STORAGE_BASE = PROJECT_ROOT / "storage" / "admin_data"
DB_PATH = STORAGE_BASE / "policy_inventory_master.db"
TREE_FILE = PROJECT_ROOT / "workspace" / "Gdrive-sync" / "dokumentasi-produk-hukum-kebijakan" / "tree_output.txt"
README_FILE = PROJECT_ROOT / "workspace" / "Gdrive-sync" / "dokumentasi-produk-hukum-kebijakan" / "README.md"


class PolicyInventoryEngine:
    """
    Mesin inventarisasi, pencarian, dan agregasi regulasi & produk hukum Ditjen Bina Bangda Kemendagri.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._sync_index_if_empty()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS policy_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kategori TEXT NOT NULL,         -- KEPMENDAGRI, PERMENDAGRI, INMENDAGRI, SEB, SE, MOU, PP, UU
                    tahun INTEGER,                  -- 2026, 2025, 2024, dll.
                    sub_kategori TEXT,              -- RPJMD, RTRW, RPIP, RZWP3K, Sarpras, PBJ, Satgas, dll.
                    nama_file TEXT NOT NULL,        -- Nama file lengkap
                    nomor_dokumen TEXT,             -- Nomor regulasi jika terdeteksi
                    judul_tentang TEXT,             -- Perihal / tentang regulasi
                    file_ext TEXT,                  -- pdf, docx, rtf, dll.
                    full_path TEXT,                 -- Path hierarki virtual
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_policy_kat_th ON policy_documents(kategori, tahun);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_policy_th ON policy_documents(tahun);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_policy_nama ON policy_documents(nama_file);")

    def sync_from_tree_file(self, force: bool = False) -> int:
        """
        Membaca dan mem-parsing tree_output.txt ke dalam database SQLite lokal.
        """
        if not TREE_FILE.exists():
            logger.warning(f"Tree file not found at {TREE_FILE}")
            return 0

        with self._get_connection() as conn:
            if not force:
                count = conn.execute("SELECT COUNT(*) FROM policy_documents").fetchone()[0]
                if count > 0:
                    return count
            
            conn.execute("DELETE FROM policy_documents")

        with open(TREE_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        entries = []
        stack = []  # [(depth, name)]

        for line in lines:
            line_str = line.rstrip()
            if not line_str or line_str.startswith("Dokumentasi Produk Hukum"):
                continue

            # Hitung depth berdasarkan indentasi
            # Pola: "├── " atau "└── " atau "│   "
            match = re.search(r"[├└]──\s+(.*)$", line_str)
            if not match:
                continue

            item_name = match.group(1).strip()
            indent_prefix = line_str[:match.start()]
            depth = len(indent_prefix) // 4

            while len(stack) > depth:
                stack.pop()

            stack.append(item_name)
            current_path = " / ".join(stack)

            # Deteksi apakah ini file (bukan folder)
            is_file = any(item_name.lower().endswith(ext) for ext in [".pdf", ".doc", ".docx", ".rtf", ".rar", ".zip", ".xlsx", ".txt"])
            
            if is_file:
                # Ekstrak kategori, tahun, sub_kategori dari stack
                kategori = stack[0].upper() if len(stack) > 0 else "LAINNYA"
                tahun = None
                sub_kategori = "UMUM"

                for elem in stack[1:-1]:
                    if re.match(r"^\d{4}$", elem):
                        tahun = int(elem)
                    else:
                        sub_kategori = elem.upper()

                # Fallback ekstrak tahun dari nama file jika belum ada
                if not tahun:
                    th_match = re.search(r"\b(20\d{2})\b", item_name)
                    if th_match:
                        tahun = int(th_match.group(1))
                    else:
                        tahun = 2026 if "2026" in current_path else 2025

                # Ekstrak nomor dokumen & judul
                nomor_dok, judul = self._extract_metadata_from_name(item_name, kategori, tahun)
                file_ext = item_name.split(".")[-1].lower() if "." in item_name else ""

                entries.append((
                    kategori,
                    tahun,
                    sub_kategori,
                    item_name,
                    nomor_dok,
                    judul,
                    file_ext,
                    current_path
                ))

        with self._get_connection() as conn:
            conn.executemany("""
                INSERT INTO policy_documents 
                (kategori, tahun, sub_kategori, nama_file, nomor_dokumen, judul_tentang, file_ext, full_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, entries)

        logger.info(f"✅ Berhasil sinkronisasi {len(entries)} dokumen kebijakan ke SQLite.")
        return len(entries)

    def _sync_index_if_empty(self):
        with self._get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM policy_documents").fetchone()[0]
            if count == 0:
                self.sync_from_tree_file()

    def _extract_metadata_from_name(self, filename: str, kategori: str, tahun: Optional[int]) -> Tuple[str, str]:
        """Mengekstrak nomor dokumen dan perihal dari nama file secara heuristik."""
        clean_name = re.sub(r"\.[a-zA-Z0-9]+$", "", filename).strip()
        clean_name = re.sub(r"_\d{6}_\d{6}$", "", clean_name)  # hapus timestamp scanner

        nomor = "-"
        # Deteksi nomor: No. XX Tahun YYYY / Nomor XX / SK ...
        no_match = re.search(r"(?:no\.?|nomor|ke-)\s*([0-9\.\-\/A-Za-z]+(?:\s+tahun\s+\d{4})?)", clean_name, flags=re.IGNORECASE)
        if no_match:
            nomor = no_match.group(0).strip()

        # Format judul tentang
        judul = clean_name
        for prefix in ["salinan kepmendagri", "salinan kepmen", "salinan permendagri", "salinan inmendagri", "sk mendagri", "salinan", "sk "]:
            if judul.lower().startswith(prefix):
                judul = judul[len(prefix):].strip(" -_")
                break

        return nomor, judul.title()

    def query_inventory(
        self,
        kategori: Optional[str] = None,
        tahun: Optional[int] = 2026,
        keyword: Optional[str] = None,
        sub_kategori: Optional[str] = None,
        limit: int = 15
    ) -> Dict[str, Any]:
        """
        Menjalankan penelusuran inventarisasi regulasi dengan filter multi-dimensi.
        """
        self._sync_index_if_empty()

        conditions = []
        params = []

        if kategori and kategori.upper() not in ("ALL", "SEMUA", "KEBIJAKAN"):
            # Normalisasi kategori
            kat_clean = kategori.upper().strip()
            if "KEPMEN" in kat_clean or "SK" in kat_clean:
                conditions.append("kategori = 'KEPMENDAGRI'")
            elif "PERMEN" in kat_clean:
                conditions.append("kategori = 'PERMENDAGRI'")
            elif "INMEN" in kat_clean:
                conditions.append("kategori = 'INMENDAGRI'")
            elif "MOU" in kat_clean or "KERJASAMA" in kat_clean or "PKS" in kat_clean:
                conditions.append("kategori IN ('MOU', 'NOTA KESEPAHAMAN', 'PERJANJIAN KERJASAMA')")
            elif "SE" in kat_clean or "SURAT EDARAN" in kat_clean:
                conditions.append("kategori IN ('SE', 'SEB')")
            else:
                conditions.append("kategori LIKE ?")
                params.append(f"%{kat_clean}%")

        if tahun:
            conditions.append("tahun = ?")
            params.append(tahun)

        if sub_kategori:
            conditions.append("sub_kategori LIKE ?")
            params.append(f"%{sub_kategori.upper()}%")

        if keyword:
            conditions.append("(nama_file LIKE ? OR judul_tentang LIKE ? OR sub_kategori LIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        with self._get_connection() as conn:
            # 1. Hitung total agregat per kategori (deduplicated by filename)
            stat_query = f"""
                SELECT kategori, COUNT(DISTINCT nama_file) as count 
                FROM policy_documents {where_clause} 
                GROUP BY kategori ORDER BY count DESC;
            """
            stat_rows = conn.execute(stat_query, params).fetchall()
            stats_by_category = {r["kategori"]: r["count"] for r in stat_rows}
            total_count = sum(stats_by_category.values())

            # 2. Ambil daftar dokumen unik
            query = f"""
                SELECT MIN(id) as id, kategori, tahun, sub_kategori, nama_file, nomor_dokumen, judul_tentang, full_path 
                FROM policy_documents {where_clause} 
                GROUP BY nama_file
                ORDER BY id ASC LIMIT ?;
            """
            doc_rows = conn.execute(query, params + [limit]).fetchall()
            documents = [dict(r) for r in doc_rows]

        return {
            "total_documents": total_count,
            "tahun": tahun,
            "filter_kategori": kategori or "SEMUA",
            "stats_by_category": stats_by_category,
            "limit": limit,
            "documents": documents
        }

    def format_whatsapp_response(self, res: Dict[str, Any], query_label: str = "") -> str:
        """
        Memformat hasil agregasi menjadi laporan ringkas, rapi, dan formal WhatsApp-ready.
        """
        total = res.get("total_documents", 0)
        tahun = res.get("tahun", 2026)
        docs = res.get("documents", [])
        stats = res.get("stats_by_category", {})

        if total == 0:
            return (
                f"📂 *INVENTARISASI PRODUK HUKUM & KEBIJAKAN (TAHUN {tahun})*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Tidak ditemukan dokumen kebijakan yang cocok dengan kriteria pencarian `{query_label}`.\n\n"
                f"_Silakan periksa kembali kata kunci atau kategori yang diinginkan (misal: Kepmendagri, Permendagri, RPJMD, RTRW)._"
            )

        # Rangkuman Statistik
        stat_text = ", ".join([f"*{k}:* {v}" for k, v in stats.items()])

        lines = [
            f"📊 *INVENTARISASI PRODUK HUKUM & KEBIJAKAN DITJEN BANGDA*",
            f"━━━━━━━━━━━━━━━━━━━━━━━━",
            f"📌 *Periode / Tahun:* `{tahun}` | *Total Dokumen Terdata:* `{total} Berkas`",
            f"📈 *Rincian Kategori:* {stat_text}",
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        ]

        # Daftar Dokumen
        for i, d in enumerate(docs, 1):
            kat = d.get("kategori", "")
            sub = d.get("sub_kategori", "")
            nama = d.get("nama_file", "")
            sub_badge = f" `[{sub}]`" if sub and sub != "UMUM" else ""
            
            lines.append(f"*{i}. [{kat}]{sub_badge}*")
            lines.append(f"   📄 *Berkas:* {nama}")
            if d.get("nomor_dokumen") and d.get("nomor_dokumen") != "-":
                lines.append(f"   🔖 *Nomor:* {d.get('nomor_dokumen')}")
            lines.append(f"   📂 *Katalog:* `/{d.get('full_path', '')}`\n")

        if total > len(docs):
            sisa = total - len(docs)
            lines.append(f"_...dan {sisa} dokumen kebijakan lainnya terdaftar dalam master katalog._")

        return "\n".join(lines)


# Singleton instance
policy_inventory_engine = PolicyInventoryEngine()

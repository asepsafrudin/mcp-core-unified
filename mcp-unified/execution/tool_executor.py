"""
Tool Executor Service

Mendefinisikan tools yang bisa dipanggil LLM secara otonom (Agentic).
Setiap tool memiliki schema JSON dan executor function.

Tools operasional Telegram chat:
- get_correspondence  : Ringkasan surat masuk/keluar dari dashboard
- search_letters      : Cari surat berdasarkan kata kunci
- count_letters       : Hitung jumlah surat
- search_by_position  : Cari surat berdasarkan posisi
- get_datetime        : Tanggal & waktu saat ini (WIB)

Tools database native:
- list_db_tables      : Daftar tabel di database
- describe_db_table   : Struktur kolom tabel
- query_database      : Text-to-SQL query

Tools korespondensi lanjutan (Modul 1 — 2026-04-17):
- search_raw_pool     : Cari surat dari 2.201 pool lintas substansi
- get_agenda_pending  : Ambil surat pending di substansi PUU (54 surat)
- get_disposisi_chain : Lacak rantai disposisi suatu surat
- get_surat_keluar    : Ambil data surat keluar PUU
- get_surat_luar_bangda: Cari surat dari instansi eksternal Bangda
"""

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Callable

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

# Koneksi DB langsung untuk tools Modul 1
_DB_PARAMS = {
    "host": os.getenv("PG_HOST", "localhost"),
    "port": int(os.getenv("PG_PORT", "5433")),
    "dbname": os.getenv("PG_DATABASE", "mcp_knowledge"),
    "user": os.getenv("PG_USER", "mcp_user"),
    "password": os.getenv("PG_PASSWORD", "mcp_password_2024"),
}

def _db_query(sql: str, params: Optional[list] = None, limit: int = 50) -> list:
    """Helper: eksekusi SQL dan kembalikan list of dict."""
    conn = psycopg2.connect(**_DB_PARAMS)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or [])
            rows = cur.fetchmany(limit)
            return [dict(r) for r in rows]
    finally:
        conn.close()


# =============================================================================
# DEFINISI TOOLS — Schema untuk Function Calling
# =============================================================================

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "count_letters",
            "description": (
                "Hitung jumlah AKURAT surat untuk periode bulan/tahun tertentu. "
                "WAJIB gunakan untuk pertanyaan: 'berapa surat', 'jumlah surat', 'total surat', "
                "'berapa disposisi', 'berapa surat masuk', 'berapa surat keluar', "
                "'berapa surat internal', 'berapa surat bulan ini', 'berapa surat tahun ini'. "
                "Hasilnya akurat 100% karena menghitung SEMUA data tanpa batasan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tipe": {
                        "type": "string",
                        "description": (
                            "Tipe surat yang dihitung: "
                            "'masuk' = surat eksternal/disposisi yang masuk ke PUU, "
                            "'keluar' = surat produksi yang dikirim oleh tim PUU, "
                            "'internal' = semua surat internal yang ada di PUU (posisi di PUU)"
                        ),
                        "enum": ["masuk", "keluar", "internal"]
                    },
                    "bulan": {
                        "type": "integer",
                        "description": "Nomor bulan 1-12. Contoh: 3=Maret, 1=Januari. Kosongkan untuk semua bulan."
                    },
                    "tahun": {
                        "type": "integer",
                        "description": "Tahun data, default 2026",
                        "default": 2026
                    }
                },
                "required": ["tipe"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_correspondence",
            "description": (
                "Ambil ringkasan dashboard korespondensi terkini (3 surat terbaru per kategori). "
                "Gunakan untuk: melihat surat terbaru, status korespondensi terakhir, "
                "preview situasi terkini. "
                "JANGAN gunakan untuk pertanyaan 'berapa' atau 'jumlah' — gunakan count_letters."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tipe": {
                        "type": "string",
                        "enum": ["masuk", "keluar", "semua"],
                        "default": "semua"
                    },
                    "tahun": {
                        "type": "integer",
                        "default": 2026
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_letters",
            "description": (
                "Cari surat atau korespondensi berdasarkan perihal, nomor surat, atau pengirim. "
                "Gunakan untuk pertanyaan tentang surat masuk, keluar, atau disposisi. "
                "Contoh: 'cari perihal sensus ekonomi'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Kata kunci atau perihal untuk dicari (contoh: 'sensus ekonomi', 'anggaran', dll)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_database",
            "description": (
                "Query PostgreSQL untuk **data operasional**: tasks, dokumen OCR, statistik DB. "
                "Gunakan untuk pertanyaan analisis data yang membutuhkan query SQL kompleks."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pertanyaan": {
                        "type": "string",
                        "description": "Pertanyaan dalam Bahasa Indonesia"
                    }
                },
                "required": ["pertanyaan"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_db_tables",
            "description": "Dapatkan daftar semua tabel yang tersedia di database PostgreSQL (mcp_knowledge). Gunakan untuk eksplorasi data.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "describe_db_table",
            "description": "Lihat skema/struktur kolom dari tabel tertentu di database. Gunakan sebelum melakukan query_database untuk memastikan nama kolom benar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Nama tabel yang ingin diperiksa"
                    }
                },
                "required": ["table_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": (
                "Cari dokumen di knowledge base menggunakan semantic search. "
                "Gunakan untuk: regulasi/UU, SOP, kebijakan, referensi hukum, "
                "dokumen yang tersimpan di database dokumen."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Kata kunci atau pertanyaan untuk dicari"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Jumlah hasil (default 3, max 10)",
                        "default": 3
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_datetime",
            "description": "Dapatkan tanggal dan waktu tepat saat ini dalam WIB.",
            "parameters": {
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "enum": ["full", "date", "time"],
                        "default": "full"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_by_position",
            "description": (
                "Cari daftar surat berdasarkan POSISI saat ini (misal: 'PUU', 'MEJA KEPALA'). "
                "Mendukung pencarian cerdas kode klasifikasi PUU (misal: '500.4' atau '500.4/123'). "
                "Gunakan untuk: mengetahui surat di unit tertentu atau berdasarkan kode posisi."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "posisi": {
                        "type": "string",
                        "description": "Nama posisi/unit atau kode klasifikasi (misal: 'PUU', '500.4/10')"
                    }
                },
                "required": ["posisi"]
            }
        }
    },
    # ── MODUL 1: Korespondensi Lanjutan ──────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "search_raw_pool",
            "description": (
                "Cari surat dari seluruh pool 2.201 korespondensi lintas substansi "
                "(SEKRETARIAT, SUPD I-IV, PEIPD, dll). Lebih luas dari search_letters. "
                "Gunakan untuk: cari surat berdasarkan perihal, nomor ND, atau pengirim "
                "dari semua direktorat."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Kata kunci perihal, nomor ND, atau nama pengirim"
                    },
                    "substansi": {
                        "type": "string",
                        "description": "Filter substansi: SEKRETARIAT, SUPD I, SUPD II, SUPD III, SUPD IV, PEIPD (opsional)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Jumlah hasil maksimal (default 10)",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_agenda_pending",
            "description": (
                "Ambil daftar surat yang masih PENDING di substansi PUU. "
                "Menampilkan agenda, pengirim, instruksi disposisi, tanggal diterima, "
                "dan berapa hari sudah pending. GUNAKAN untuk pertanyaan: "
                "'surat pending', 'belum selesai', 'tunggakan', 'backlog PUU'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "min_hari": {
                        "type": "integer",
                        "description": "Filter hanya surat yang pending minimal N hari (opsional)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_disposisi_chain",
            "description": (
                "Lacak rantai disposisi suatu surat — dari siapa ke siapa, dengan instruksi. "
                "Gunakan untuk: 'surat ini disposisinya ke mana?', 'siapa yang dapat "
                "disposisi 0102/L?', 'tracking distribusi surat'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "nomor_disposisi": {
                        "type": "string",
                        "description": "Nomor disposisi (contoh: '0102/L', '0003/L')"
                    }
                },
                "required": ["nomor_disposisi"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_surat_keluar",
            "description": (
                "Ambil data surat keluar yang diproduksi tim PUU. "
                "Gunakan untuk: 'surat keluar PUU', 'produksi surat bulan ini', "
                "'daftar ND yang diterbitkan PUU'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "bulan": {
                        "type": "integer",
                        "description": "Filter bulan 1-12 (opsional, default semua)"
                    },
                    "query": {
                        "type": "string",
                        "description": "Kata kunci perihal atau nomor ND (opsional)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Jumlah hasil (default 10)",
                        "default": 10
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_surat_luar_bangda",
            "description": (
                "Cari surat dari instansi EKSTERNAL di luar Bangda (578 surat). "
                "Contoh: surat dari Kemenko PMK, Sekjen Kemendagri, PT. dll. "
                "Gunakan untuk pertanyaan tentang surat masuk dari luar Ditjen Bangda."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Kata kunci perihal atau nama instansi pengirim"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Jumlah hasil (default 10)",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": "Pencarian full-text di dalam isi dokumen PDF/Arsip yang sudah di-OCR (vision_results).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Kata kunci teks dalam isi dokumen"},
                    "limit": {"type": "integer", "description": "Jumlah hasil (default 5)", "default": 5}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_file_index",
            "description": "Cari file di direktori OneDrive (onedrive_puu_files) berdasarkan nama file atau kategori.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Potongan nama file"},
                    "category": {"type": "string", "description": "Kategori file (Undangan, Laporan, dll)"},
                    "limit": {"type": "integer", "description": "Jumlah hasil (default 10)", "default": 10}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_anomalies",
            "description": "Cari anomali kritis (surat pending > 30 hari) secara otomatis.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Jumlah maksimal anomali", "default": 5}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_staff_workload",
            "description": "Mendapatkan laporan beban kerja seluruh staf (PIC), termasuk jumlah surat pending.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_staff_details",
            "description": "Mendapatkan detail profil staf berdasarkan nama atau NIP.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Nama atau NIP staf"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "sync_personnel_data",
            "description": "Sinkronisasi data pegawai dari JSON master ke database PostgreSQL. Gunakan jika ada perubahan data pegawai atau jika database perlu diperkaya.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
]

TELEGRAM_CHAT_TOOL_NAMES = {
    "count_letters",
    "get_correspondence",
    "search_letters",
    "search_by_position",
    "query_database",
    "list_db_tables",
    "describe_db_table",
    "get_datetime",
    # Modul 1
    "search_raw_pool",
    "get_agenda_pending",
    "get_disposisi_chain",
    "get_surat_keluar",
    "get_surat_luar_bangda",
    # Modul 3
    "search_documents",
    "get_file_index",
    # Modul 4
    "check_anomalies",
    # Modul 5
    "get_staff_workload",
    "get_staff_details",
    "sync_personnel_data"
}

TELEGRAM_CHAT_TOOL_DEFINITIONS = [
    tool for tool in TOOL_DEFINITIONS
    if isinstance(tool, dict) and tool.get("function", {}).get("name") in TELEGRAM_CHAT_TOOL_NAMES
]


# =============================================================================
# TOOL EXECUTOR
# =============================================================================

class ToolExecutor:
    """
    Eksekutor untuk semua tools yang bisa dipanggil LLM.

    Priority untuk data surat:
    1. bot.dashboard → SELALU tersedia, langsung dari Google Sheets
    2. Tool extended seperti text_to_sql/knowledge → terintegrasi secara native
    """

    def __init__(self, bot=None):
        self.bot = bot
        self._executors: Dict[str, Callable] = {
            "count_letters": self._exec_count_letters,
            "get_correspondence": self._exec_get_correspondence,
            "search_letters": self._exec_search_letters,
            "search_by_position": self._exec_search_by_position,
            "query_database": self._exec_query_database,
            "list_db_tables": self._exec_list_db_tables,
            "describe_db_table": self._exec_describe_db_table,
            "search_knowledge": self._exec_search_knowledge,
            "get_datetime": self._exec_get_datetime,
            # Modul 1 — Korespondensi Lanjutan
            "search_raw_pool": self._exec_search_raw_pool,
            "get_agenda_pending": self._exec_get_agenda_pending,
            "get_disposisi_chain": self._exec_get_disposisi_chain,
            "get_surat_keluar": self._exec_get_surat_keluar,
            "get_surat_luar_bangda": self._exec_get_surat_luar_bangda,
            "search_documents": self._exec_search_documents,
            "get_file_index": self._exec_get_file_index,
            # Modul 4
            "check_anomalies": self._exec_check_anomalies,
            # Modul 5
            "get_staff_workload": self._exec_get_staff_workload,
            "get_staff_details": self._exec_get_staff_details,
            "sync_personnel_data": self._exec_sync_personnel_data,
        }

    async def execute(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
        """Eksekusi tool dan kembalikan hasilnya sebagai string untuk LLM."""
        executor = self._executors.get(tool_name)
        if not executor:
            logger.warning(f"⚠️ [AUDIT] Attempted to call unknown tool: {tool_name}")
            return json.dumps({
                "error": f"Tool '{tool_name}' tidak dikenal",
                "available_tools": list(self._executors.keys())
            }, ensure_ascii=False)

        try:
            # Audit log start
            start_time = datetime.now()
            logger.info(f"🔧 [AUDIT] Tool START: {tool_name} | Args: {json.dumps(tool_args, ensure_ascii=False)}")
            
            result = await executor(tool_args)
            
            # Audit log success
            duration = (datetime.now() - start_time).total_seconds()
            res_summary = str(result)[:100].replace('\n', ' ')
            logger.info(f"✅ [AUDIT] Tool SUCCESS: {tool_name} | Duration: {duration:.2f}s | Result: {res_summary}...")
            
            return result
        except Exception as e:
            # Audit log failure
            logger.error(f"❌ [AUDIT] Tool FAILED: {tool_name} | Error: {str(e)}")
            return json.dumps({
                "error": f"Tool '{tool_name}' gagal: {str(e)}",
                "status": "error"
            }, ensure_ascii=False)

    # -------------------------------------------------------------------------
    # EXECUTORS
    # -------------------------------------------------------------------------

    async def _exec_count_letters(self, args: Dict) -> str:
        """
        Hitung jumlah surat AKURAT per periode.
        Support tipe: masuk (eksternal/dispo), keluar (produksi PUU), internal (pooling PUU)
        """
        tipe = args.get("tipe", "masuk")
        bulan = args.get("bulan")  # None = semua bulan
        tahun = int(args.get("tahun", 2026))

        dashboard = getattr(self.bot, 'dashboard', None)
        if not dashboard:
            return json.dumps({"error": "Dashboard tidak tersedia"}, ensure_ascii=False)

        try:
            if tipe == "internal":
                result = dashboard.count_letters_by_period(bulan=bulan, tahun=tahun, tipe="internal")
                tipe_label = "Surat Internal PUU (semua posisi di PUU)"
            elif tipe == "keluar":
                result = dashboard.count_letters_by_period(bulan=bulan, tahun=tahun, tipe="keluar")
                tipe_label = "Surat Keluar (Produksi Tim PUU)"
            else:
                result = dashboard.count_letters_by_period(bulan=bulan, tahun=tahun, tipe="masuk")
                tipe_label = "Surat Masuk (Disposisi Eksternal PUU)"

            periode = f"{result.get('bulan', 'semua bulan')} {tahun}"

            return json.dumps({
                "status": "success",
                "tipe": tipe_label,
                "periode": periode,
                "total": result["total"],
                "detail": result.get("detail", []),
                "sumber": "Google Sheets (Dispo PUU / Pooling Internal)",
            }, ensure_ascii=False, default=str)

        except Exception as e:
            logger.error(f"count_letters error: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    async def _exec_get_correspondence(self, args: Dict) -> str:
        """
        Ambil data korespondensi dari bot.dashboard.
        """
        tipe = args.get("tipe", "semua")
        tahun = int(args.get("tahun", 2026))

        dashboard = getattr(self.bot, 'dashboard', None)
        if not dashboard:
            return json.dumps({
                "error": "Dashboard tidak tersedia",
                "info": "Sistem dashboard belum diinisialisasi"
            }, ensure_ascii=False)

        try:
            results = {}

            if tipe in ("masuk", "semua"):
                summary = dashboard.get_recent_summary()
                clean = summary.replace('*', '').replace('_', '').replace('`', '').replace('#', '')
                results["data_korespondensi"] = clean[:3000]

            if tipe == "keluar":
                keluar = dashboard.get_puu_production(limit=20, year=tahun)
                clean = keluar.replace('*', '').replace('_', '').replace('`', '').replace('#', '')
                results["surat_keluar_puu"] = clean[:2000]

            results["tahun"] = tahun
            results["status"] = "success"
            results["sumber"] = "Sistem Dashboard Korespondensi"

            return json.dumps(results, ensure_ascii=False)

        except Exception as e:
            logger.error(f"get_correspondence error: {e}")
            return json.dumps({
                "error": f"Gagal ambil data: {str(e)}"
            }, ensure_ascii=False)

    async def _exec_search_letters(self, args: Dict) -> str:
        """Cari surat berdasarkan kata kunci via dashboard."""
        query = args.get("query") or args.get("kata_kunci") or ""
        if not query:
            return json.dumps({"error": "Kata kunci (query) tidak boleh kosong"}, ensure_ascii=False)

        dashboard = getattr(self.bot, 'dashboard', None)
        if not dashboard:
            return json.dumps({"error": "Dashboard tidak tersedia"}, ensure_ascii=False)

        try:
            results = dashboard.search_letters(query)
            if not results:
                return json.dumps({
                    "query": query,
                    "jumlah": 0,
                    "pesan": f"Tidak ditemukan surat dengan kata kunci '{query}'"
                }, ensure_ascii=False)

            items = []
            headers_ref = []
            
            for r in results[:10]:
                if isinstance(r, dict) and "row_data" in r and "header" in r:
                    row_data = r["row_data"]
                    header = r["header"]
                    headers_ref = header
                    
                    item_dict = {
                        "direktorat": r.get("direktorat", "Unknown"),
                        "match_on_hal": r.get("match_on_hal", False)
                    }
                    
                    for i, h in enumerate(header):
                        if i < len(row_data):
                            col_name = str(h).strip() or f"Column_{i}"
                            item_dict[col_name] = row_data[i]
                    
                    items.append(item_dict)
                elif isinstance(r, dict) and "nomor_nd" in r:
                    items.append({
                        "tipe": r.get("tipe", "N/A"),
                        "nomor": r.get("nomor_nd", "-"),
                        "pengirim": r.get("dari", "-"),
                        "perihal": r.get("hal", "-"),
                        "posisi": r.get("posisi", "-"),
                        "disposisi": r.get("disposisi", "-")
                    })
                else:
                    items.append({"data": str(r)})

            return json.dumps({
                "status": "success",
                "query": query,
                "jumlah_total": len(results),
                "hasil_ditampilkan": len(items),
                "headers": headers_ref,
                "data": items,
            }, ensure_ascii=False, default=str)

        except Exception as e:
            logger.error(f"search_letters error: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    async def _exec_search_by_position(self, args: Dict) -> str:
        """Cari surat berdasarkan posisi via dashboard."""
        posisi = args.get("posisi", "")
        if not posisi:
            return json.dumps({"error": "Nama posisi tidak boleh kosong"}, ensure_ascii=False)

        dashboard = getattr(self.bot, 'dashboard', None)
        if not dashboard:
            return json.dumps({"error": "Dashboard tidak tersedia"}, ensure_ascii=False)

        try:
            results = dashboard.search_by_position(posisi)
            if not results:
                return json.dumps({
                    "posisi": posisi,
                    "jumlah": 0,
                    "pesan": f"Tidak ditemukan surat di posisi '{posisi}'"
                }, ensure_ascii=False)

            return json.dumps({
                "posisi": posisi,
                "jumlah": len(results),
                "hasil": results[:15],
                "status": "success"
            }, ensure_ascii=False, default=str)

        except Exception as e:
            logger.error(f"search_by_position executor error: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    async def _exec_query_database(self, args: Dict) -> str:
        """Eksekusi Text-to-SQL query via Knowledge/DB service."""
        pertanyaan = args.get("pertanyaan", "")
        if not pertanyaan:
            return json.dumps({"error": "Pertanyaan tidak boleh kosong"}, ensure_ascii=False)

        text_to_sql = getattr(self.bot, 'text_to_sql', None)
        knowledge = getattr(self.bot, 'knowledge', None)

        if not text_to_sql or not knowledge or not getattr(knowledge, 'is_available', False):
            return json.dumps({
                "status": "db_unavailable",
                "info": "Database PostgreSQL tidak terhubung saat ini.",
                "pertanyaan": pertanyaan
            }, ensure_ascii=False)

        try:
            result = await text_to_sql.execute_natural_query(
                question=pertanyaan,
                knowledge_service=knowledge
            )
            if result.get("success"):
                return json.dumps({
                    "success": True,
                    "pertanyaan": pertanyaan,
                    "sql": result.get("sql", ""),
                    "row_count": result.get("row_count", 0),
                    "columns": result.get("columns", []),
                    "data": result.get("rows", [])[:15],
                }, ensure_ascii=False, default=str)
            else:
                return json.dumps({
                    "success": False,
                    "error": result.get("error", "Query gagal"),
                    "info": "Gunakan tool list_db_tables atau describe_db_table jika tidak yakin dengan struktur tabel."
                }, ensure_ascii=False)
        except Exception as e:
            logger.error(f"query_database error: {e}")
            return json.dumps({
                "error": str(e),
                "info": "Gagal mengeksekusi query database."
            }, ensure_ascii=False)

    async def _exec_list_db_tables(self, args: Dict) -> str:
        """Daftar tabel database secara native via MCP tools."""
        from execution import registry
        try:
            result = await registry.execute("list_tables", {"namespace": "telegram_aria"})
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    async def _exec_describe_db_table(self, args: Dict) -> str:
        """Deskripsi tabel database secara native via MCP tools."""
        from execution import registry
        table_name = args.get("table_name", "")
        try:
            result = await registry.execute("describe_table", {"table": table_name, "namespace": "telegram_aria"})
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    async def _exec_search_knowledge(self, args: Dict) -> str:
        """Semantic search ke knowledge base."""
        query = args.get("query", "")
        limit = min(int(args.get("limit", 3)), 10)

        if not query:
            return json.dumps({"error": "Query tidak boleh kosong"}, ensure_ascii=False)

        memory = getattr(self.bot, 'memory_service', None)
        if memory:
            try:
                result = await memory.get_knowledge_context(query=query, limit=limit)
                if result:
                    return json.dumps({
                        "success": True,
                        "query": query,
                        "results": result[:2000]
                    }, ensure_ascii=False)
            except Exception as e:
                logger.warning(f"knowledge search error: {e}")

        return json.dumps({
            "info": f"Tidak ditemukan dokumen relevan untuk: '{query}'",
            "suggestion": "Coba kata kunci yang lebih spesifik"
        }, ensure_ascii=False)

    async def _exec_get_datetime(self, args: Dict) -> str:
        """Tanggal dan waktu WIB saat ini."""
        fmt = args.get("format", "full")
        wib = timezone(timedelta(hours=7))
        now = datetime.now(wib)
        day_names = {0:'Senin',1:'Selasa',2:'Rabu',3:'Kamis',4:'Jumat',5:'Sabtu',6:'Minggu'}
        month_names = {
            1:'Januari',2:'Februari',3:'Maret',4:'April',5:'Mei',6:'Juni',
            7:'Juli',8:'Agustus',9:'September',10:'Oktober',11:'November',12:'Desember'
        }
        day = day_names[now.weekday()]
        month = month_names[now.month]

        if fmt == "date":
            result = f"{day}, {now.day} {month} {now.year}"
        elif fmt == "time":
            result = f"{now.strftime('%H:%M')} WIB"
        else:
            result = f"{day}, {now.day} {month} {now.year} pukul {now.strftime('%H:%M:%S')} WIB"

        return json.dumps({
            "datetime": result,
            "weekday": day,
            "timezone": "WIB (UTC+7)"
        }, ensure_ascii=False)

    # =========================================================================
    # MODUL 1 — TOOLS KORESPONDENSI LANJUTAN
    # =========================================================================

    async def _exec_search_raw_pool(self, args: Dict) -> str:
        """Cari surat dari pool 2.201 korespondensi lintas substansi."""
        query = args.get("query", "").strip()
        substansi = args.get("substansi", "").strip()
        limit = min(int(args.get("limit", 10)), 30)

        if not query:
            return json.dumps({"error": "Parameter 'query' tidak boleh kosong"}, ensure_ascii=False)

        try:
            q = f"%{query}%"
            params = [q, q, q]
            substansi_filter = ""
            if substansi:
                substansi_filter = " AND source_sheet_name ILIKE %s"
                params.append(f"%{substansi}%")
            params.append(limit)

            sql = f"""
                SELECT nomor_nd, tanggal, dari,
                       LEFT(hal, 120) AS hal,
                       source_sheet_name AS substansi,
                       LEFT(posisi, 80) AS posisi,
                       LEFT(disposisi, 100) AS disposisi
                FROM korespondensi_raw_pool
                WHERE (hal ILIKE %s OR nomor_nd ILIKE %s OR dari ILIKE %s)
                {substansi_filter}
                ORDER BY tanggal DESC
                LIMIT %s
            """
            rows = _db_query(sql, params, limit=limit)

            return json.dumps({
                "status": "success",
                "query": query,
                "total_ditemukan": len(rows),
                "sumber": "korespondensi_raw_pool (2.201 surat lintas substansi)",
                "data": rows
            }, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"search_raw_pool error: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    async def _exec_get_agenda_pending(self, args: Dict) -> str:
        """Ambil surat pending di substansi PUU."""
        min_hari = int(args.get("min_hari", 0))

        try:
            hari_filter = ""
            params: list = []
            if min_hari > 0:
                hari_filter = " AND (CURRENT_DATE - tanggal_diterima) >= %s"
                params.append(min_hari)

            sql = f"""
                SELECT agenda, surat_dari, nomor_surat,
                       LEFT(isi_disposisi, 120) AS instruksi,
                       tanggal_diterima,
                       CURRENT_DATE - tanggal_diterima AS hari_pending,
                       status, no_agenda_ses, doc_url
                FROM surat_untuk_substansi_puu
                WHERE status = 'pending'
                {hari_filter}
                ORDER BY tanggal_diterima ASC
            """
            rows = _db_query(sql, params, limit=60)

            # Klasifikasi urgensi
            kritis = [r for r in rows if (r.get("hari_pending") or 0) > 30]

            return json.dumps({
                "status": "success",
                "total_pending": len(rows),
                "kritis_lebih_30_hari": len(kritis),
                "sumber": "surat_untuk_substansi_puu",
                "data": rows
            }, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"get_agenda_pending error: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    async def _exec_get_disposisi_chain(self, args: Dict) -> str:
        """Lacak rantai disposisi suatu surat."""
        nomor = args.get("nomor_disposisi", "").strip()
        if not nomor:
            return json.dumps({"error": "Parameter 'nomor_disposisi' tidak boleh kosong"}, ensure_ascii=False)

        try:
            sql = """
                SELECT nomor_disposisi, dari, kepada,
                       tanggal_disposisi,
                       LEFT(isi_disposisi, 150) AS instruksi,
                       batas_waktu, source_tab
                FROM disposisi_distributions
                WHERE nomor_disposisi ILIKE %s
                ORDER BY tanggal_disposisi
            """
            rows = _db_query(sql, [f"%{nomor}%"], limit=20)

            if not rows:
                return json.dumps({
                    "status": "not_found",
                    "pesan": f"Tidak ditemukan disposisi dengan nomor '{nomor}'"
                }, ensure_ascii=False)

            return json.dumps({
                "status": "success",
                "nomor_disposisi": nomor,
                "jumlah_distribusi": len(rows),
                "rantai": rows
            }, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"get_disposisi_chain error: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    async def _exec_get_surat_keluar(self, args: Dict) -> str:
        """Ambil data surat keluar PUU."""
        bulan = args.get("bulan")
        query = args.get("query", "").strip()
        limit = min(int(args.get("limit", 10)), 30)

        try:
            conditions = ["1=1"]
            params: list = []

            if bulan:
                conditions.append("EXTRACT(MONTH FROM tanggal_surat) = %s")
                params.append(str(int(bulan)))

            if query:
                conditions.append("(hal ILIKE %s OR nomor_nd ILIKE %s)")
                q = f"%{query}%"
                params.extend([q, q])

            params.append(limit)
            sql = f"""
                SELECT nomor_nd, tanggal_surat, dari,
                       LEFT(hal, 120) AS hal, tujuan
                FROM surat_keluar_puu
                WHERE {" AND ".join(conditions)}
                ORDER BY tanggal_surat DESC
                LIMIT %s
            """
            rows = _db_query(sql, params, limit=limit)

            return json.dumps({
                "status": "success",
                "total": len(rows),
                "sumber": "surat_keluar_puu (45 surat produksi PUU)",
                "data": rows
            }, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"get_surat_keluar error: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    async def _exec_get_surat_luar_bangda(self, args: Dict) -> str:
        """Cari surat dari instansi eksternal Bangda."""
        query = args.get("query", "").strip()
        limit = min(int(args.get("limit", 10)), 30)

        if not query:
            return json.dumps({"error": "Parameter 'query' tidak boleh kosong"}, ensure_ascii=False)

        try:
            q = f"%{query}%"
            sql = """
                SELECT surat_dari, nomor_surat, tgl_surat, tgl_diterima_ula,
                       LEFT(perihal, 120) AS perihal,
                       LEFT(arahan, 80) AS arahan,
                       agenda_ula, status_mailmerge,
                       dispo_nomor, LEFT(dispo_perihal, 120) AS dispo_perihal
                FROM surat_dari_luar_bangda
                WHERE (perihal ILIKE %s OR surat_dari ILIKE %s
                       OR nomor_surat ILIKE %s)
                ORDER BY tgl_surat DESC
                LIMIT %s
            """
            rows = _db_query(sql, [q, q, q, limit], limit=limit)

            return json.dumps({
                "status": "success",
                "query": query,
                "total_ditemukan": len(rows),
                "sumber": "surat_dari_luar_bangda (578 surat eksternal)",
                "data": rows
            }, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"get_surat_luar_bangda error: {e}")
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    async def _exec_search_documents(self, args: Dict[str, Any]) -> str:
        """Pencarian full-text di vision_results (OCR data)."""
        query = args.get("query")
        limit = args.get("limit", 5)
        
        try:
            sql = """
                SELECT file_name, 
                       LEFT(extracted_text, 250) as snippet,
                       processed_at, confidence_score
                FROM vision_results
                WHERE extracted_text ILIKE %s
                ORDER BY processed_at DESC
                LIMIT %s
            """
            rows = _db_query(sql, [f'%{query}%', limit])
            return json.dumps({
                "status": "success",
                "total_ditemukan": len(rows),
                "sumber": "vision_results (OCR Documents)",
                "data": rows
            }, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"search_documents error: {e}")
            return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False)

    async def _exec_get_file_index(self, args: Dict[str, Any]) -> str:
        """Cari file di onedrive_puu_files (OneDrive Archive)."""
        query = args.get("query")
        category = args.get("category")
        limit = args.get("limit", 10)
        
        try:
            conditions = []
            params = []
            
            if query:
                conditions.append("file_name ILIKE %s")
                params.append(f'%{query}%')
            if category:
                conditions.append("category ILIKE %s")
                params.append(f'%{category}%')
                
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            
            sql = f"""
                SELECT file_name, category, subcategory, 
                       file_size_bytes, created_at, status
                FROM onedrive_puu_files
                {where_clause}
                ORDER BY created_at DESC
                LIMIT %s
            """
            params.append(limit)
            
            rows = _db_query(sql, params)
            return json.dumps({
                "status": "success",
                "total_ditemukan": len(rows),
                "sumber": "onedrive_puu_files (4,417 files)",
                "data": rows
            }, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"get_file_index error: {e}")
            return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False)

    async def _exec_check_anomalies(self, args: Optional[Dict[str, Any]] = None) -> str:
        """Deteksi anomali (surat pending > 30 hari)."""
        try:
            sql = """
                SELECT agenda, surat_dari, nomor_surat,
                       tanggal_diterima, 
                       CURRENT_DATE - tanggal_diterima AS hari_pending
                FROM surat_untuk_substansi_puu
                WHERE status = 'pending' AND (CURRENT_DATE - tanggal_diterima) > 30
                ORDER BY tanggal_diterima ASC
            """
            rows = _db_query(sql)
            
            if not rows:
                return json.dumps({
                    "status": "clean",
                    "message": "Tidak ada anomali kritis (pending > 30 hari) saat ini."
                })
            
            return json.dumps({
                "status": "anomaly_detected",
                "total_kritis": len(rows),
                "data": rows
            }, default=str)
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)})

    async def _exec_get_staff_workload(self, args: Optional[Dict[str, Any]] = None) -> str:
        """Get workload report for all staff (PIC)."""
        try:
            sql = """
                SELECT sd.nama, sd.jabatan_fungsional,
                       COUNT(s.id) as total_surat,
                       COUNT(CASE WHEN s.status_pengiriman = 'Belum Diproses' THEN 1 END) as pending
                FROM staff_details sd
                LEFT JOIN surat_masuk_puu_internal s ON sd.nama = s.pic_name
                GROUP BY sd.nama, sd.jabatan_fungsional
                ORDER BY total_surat DESC
            """
            rows = _db_query(sql)
            return json.dumps({
                "status": "success",
                "total_personil": len(rows),
                "data": rows
            }, default=str)
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)})

    async def _exec_get_staff_details(self, args: Dict[str, Any]) -> str:
        """Get detailed info about a specific staff member."""
        query = args.get("query", "")
        try:
            sql = "SELECT * FROM staff_details WHERE nama ILIKE %s OR nip ILIKE %s"
            rows = _db_query(sql, [f"%{query}%", f"%{query}%"])
            return json.dumps({"status": "success", "data": rows}, default=str)
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)})

    async def _exec_sync_personnel_data(self, args: Optional[Dict[str, Any]] = None) -> str:
        """Sinkronisasi data pegawai menggunakan script eksternal (Proven Pipeline)."""
        import subprocess
        try:
            # Script ini sudah terbukti berhasil melakukan pengayaan data dari JSON ke DB
            script_path = "/home/aseps/MCP/korespondensi-server/src/scripts/sync_json_to_db.py"
            result = subprocess.run(
                ["python3", script_path],
                capture_output=True,
                text=True,
                check=True
            )
            return json.dumps({
                "status": "success",
                "message": "Sinkronisasi database pegawai berhasil dijalankan melalui pipeline resmi.",
                "output": result.stdout.strip()
            }, ensure_ascii=False)
        except subprocess.CalledProcessError as e:
            return json.dumps({
                "status": "error",
                "message": "Gagal menjalankan sinkronisasi.",
                "error": e.stderr.strip()
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False)



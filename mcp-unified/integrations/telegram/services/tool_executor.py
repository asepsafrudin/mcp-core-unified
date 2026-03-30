"""
Tool Executor Service

Mendefinisikan tools yang bisa dipanggil LLM secara otonom (Agentic).
Setiap tool memiliki schema JSON dan executor function.

Tools operasional Telegram chat:
- get_correspondence: Ringkasan surat masuk/keluar dari dashboard
- search_letters   : Cari surat berdasarkan kata kunci
- count_letters    : Hitung jumlah surat
- search_by_position: Cari surat berdasarkan posisi
- get_datetime     : Tanggal & waktu saat ini (WIB)

Tools extended/legacy:
- query_database   : Text-to-SQL query ke PostgreSQL
- search_knowledge : Semantic search knowledge base
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger(__name__)


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
                "Query PostgreSQL untuk **data NON-KORESPONDENSI**: tasks, dokumen OCR, statistik DB. "
                "**JANGAN gunakan untuk surat/perihal** — **WAJIB search_letters atau get_correspondence dulu**."
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
]

TELEGRAM_CHAT_TOOL_NAMES = {
    "count_letters",
    "get_correspondence",
    "search_letters",
    "search_by_position",
    "get_datetime",
}

TELEGRAM_CHAT_TOOL_DEFINITIONS = [
    tool for tool in TOOL_DEFINITIONS
    if tool.get("function", {}).get("name") in TELEGRAM_CHAT_TOOL_NAMES
]


# =============================================================================
# TOOL EXECUTOR
# =============================================================================

class ToolExecutor:
    """
    Eksekutor untuk semua tools yang bisa dipanggil LLM.

    Priority untuk data surat:
    1. bot.dashboard → SELALU tersedia, langsung dari Google Sheets
    2. Tool extended seperti text_to_sql/knowledge → hanya untuk service terpisah
    """

    def __init__(self, bot=None):
        self.bot = bot
        self._executors: Dict[str, Callable] = {
            "count_letters": self._exec_count_letters,
            "get_correspondence": self._exec_get_correspondence,
            "search_letters": self._exec_search_letters,
            "search_by_position": self._exec_search_by_position,
            "query_database": self._exec_query_database,
            "search_knowledge": self._exec_search_knowledge,
            "get_datetime": self._exec_get_datetime,
        }

    async def execute(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
        """Eksekusi tool dan kembalikan hasilnya sebagai string untuk LLM."""
        executor = self._executors.get(tool_name)
        if not executor:
            return json.dumps({
                "error": f"Tool '{tool_name}' tidak dikenal",
                "available_tools": list(self._executors.keys())
            }, ensure_ascii=False)

        try:
            logger.info(f"🔧 Tool call: {tool_name}({tool_args})")
            result = await executor(tool_args)
            logger.info(f"✅ Tool {tool_name} → {str(result)[:80]}...")
            return result
        except Exception as e:
            logger.error(f"❌ Tool {tool_name} error: {e}")
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
            # Map tipe 'internal' ke 'keluar' untuk backward compat,
            # tapi dengan label yang berbeda
            if tipe == "internal":
                # Surat internal = semua surat di pooling TANPA filter PUU-only
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
        PRIORITAS UTAMA untuk semua pertanyaan terkait surat.
        """
        tipe = args.get("tipe", "semua")
        tahun = int(args.get("tahun", 2026))

        # Dashboard selalu tersedia
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
                # Bersihkan markdown
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

            # Format hasil pencarian menjadi list of dict (header: value) agar mudah diproses LLM
            items = []
            headers_ref = []
            
            for r in results[:10]:
                if isinstance(r, dict) and "row_data" in r and "header" in r:
                    row_data = r["row_data"]
                    header = r["header"]
                    headers_ref = header # Simpan header terakhir untuk referensi
                    
                    # Buat dict mapping header -> value
                    item_dict = {
                        "direktorat": r.get("direktorat", "Unknown"),
                        "match_on_hal": r.get("match_on_hal", False)
                    }
                    
                    for i, h in enumerate(header):
                        if i < len(row_data):
                            col_name = str(h).strip() or f"Column_{i}"
                            item_dict[col_name] = row_data[i]
                    
                    items.append(item_dict)
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
                "hasil": results[:15], # Limit to avoid token overflow
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

        # Cek apakah DB tersedia
        if not text_to_sql or not knowledge or not getattr(knowledge, 'is_available', False):
            return json.dumps({
                "status": "db_unavailable",
                "info": (
                    "Database PostgreSQL tidak terhubung saat ini. "
                    "Untuk data surat, gunakan tool get_correspondence. "
                    "Akses query database dipisahkan ke service SQL/agent yang dedicated."
                ),
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
                    "info": "Untuk bot chat utama, gunakan tool korespondensi. Query DB ada di service terpisah."
                }, ensure_ascii=False)
        except Exception as e:
            logger.error(f"query_database error: {e}")
            return json.dumps({
                "error": str(e),
                "info": "Untuk bot chat utama, gunakan tool korespondensi. Query DB ada di service terpisah."
            }, ensure_ascii=False)

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

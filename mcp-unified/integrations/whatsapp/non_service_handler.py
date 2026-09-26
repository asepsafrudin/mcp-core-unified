"""
non_service_handler.py — Non-Service Request Detector & Handlers for SATRIA WhatsApp Co-Pilot.
Handles requests outside standard legal/personnel domain: technical bugs, feature ideas,
master data corrections, complaints, system inquiries, and out-of-scope requests.
Persists data strictly within storage/admin_data/ adhering to Rule #4.
"""

import re
import json
import time
import logging
from enum import Enum
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

from integrations.whatsapp.pii_sanitizer import satria_pii_sanitizer

logger = logging.getLogger("satria_non_service")

# Storage isolation path adhering to Rule #4
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
STORAGE_BASE = PROJECT_ROOT / "storage" / "admin_data"
FEEDBACK_DIR = STORAGE_BASE / "satria_feedback"
BACKLOG_DIR = STORAGE_BASE / "satria_backlog"
TRAINING_DIR = STORAGE_BASE / "training_data"


class NonServiceCategory(Enum):
    """Kategori permintaan di luar domain pelayanan reguler SATRIA."""
    TECHNICAL_FEEDBACK = "technical_feedback"  # Bug, error, lag, timeout, freeze
    FEATURE_REQUEST = "feature_request"        # Usulan fitur baru, saran, rekomendasi
    DATA_CORRECTION = "data_correction"        # Koreksi data pegawai, SK mutasi, nomor regulasi
    SYSTEM_QUESTION = "system_question"        # Pertanyaan tentang identitas bot, MCP, cara pakai
    COMPLAINT = "complaint"                    # Keluhan layanan, kekecewaan
    PERSONAL_REQUEST = "personal_request"      # Permintaan urusan pribadi non-kedinasan
    OUT_OF_SCOPE = "out_of_scope"              # Topik yang sama sekali tidak terkait Kemendagri


class NonServiceDetector:
    """
    Mendeteksi dan mengklasifikasikan pesan pengguna ke kategori non-pelayanan.
    """

    def __init__(self):
        self.patterns = self._init_patterns()

    def _init_patterns(self) -> Dict[NonServiceCategory, Dict[str, Any]]:
        return {
            NonServiceCategory.TECHNICAL_FEEDBACK: {
                "keywords": [
                    "error", "bug", "salah", "tidak bekerja", "gagal", "lag", "lambat",
                    "loading", "timeout", "crash", "tidak merespon", "freeze", "hang",
                    "macet", "rusak", "bermasalah", "loading terus"
                ],
                "patterns": [
                    r"bot(?:nya)?\s+(?:error|salah|gagal|macet|rusak)",
                    r"respon(?:nya)?\s+terlalu\s+lambat",
                    r"tidak\s+(?:bisa|dapat)\s+(?:menjawab|memproses|jalan)",
                    r"(?:ada|kenapa)\s+(?:error|bug|gangguan)"
                ]
            },
            NonServiceCategory.FEATURE_REQUEST: {
                "keywords": [
                    "usul fitur", "tambah fitur", "request fitur", "saran fitur",
                    "fitur baru", "ide pengembangan", "pengembangan satria",
                    "masukan untuk satria", "bagus kalau ada fitur"
                ],
                "patterns": [
                    r"(?:tambah|buat|sediakan)\s+fitur",
                    r"mohon\s+(?:ditambah|dibuat|disiapkan)\s+fitur",
                    r"bagaimana\s+(?:kalau|jika)\s+ada\s+fitur",
                    r"usul(?:an)?\s+(?:fitur|pengembangan|fitur baru)",
                    r"saran\s+(?:pengembangan|fitur|untuk\s+satria)"
                ]
            },
            NonServiceCategory.DATA_CORRECTION: {
                "keywords": [
                    "koreksi", "perbaiki", "ubah", "ganti", "perbarui", "update data",
                    "sudah mutasi", "sudah pindah", "bukan pejabat", "salah nama", "salah jabatan", "salah di sistem"
                ],
                "patterns": [
                    r"data\s+(?:pegawai|pejabat|jabatan)\s+(?:salah|keliru|tidak\s+sesuai)",
                    r"(?:koreksi|perbaiki|ubah)\s+data",
                    r"pejabat\s+(?:tersebut\s+)?sudah\s+(?:mutasi|pindah|pensiun)",
                    r"informasi\s+(?:pegawai|regulasi)\s+(?:usang|tidak\s+update)",
                    r"(?:ganti|ubah)\s+nomor",
                    r"nomor\s+(?:telepon|hp)\s+(?:pejabat\s+)?(?:yang\s+)?salah"
                ]
            },
            NonServiceCategory.SYSTEM_QUESTION: {
                "keywords": [
                    "apa itu satria", "siapa satria", "bagaimana cara", "cara pakai",
                    "fungsi satria", "teknologi satria", "teknologi apa", "teknologi bot",
                    "mcp satria", "arsitektur satria", "ai apa", "model apa", "panduan bot", "kemampuan analisis",
                    "microsoft agent framework", "maf", "agent framework", "framework agen",
                    "terintegrasi maf", "integrasi maf", "arsitektur maf", "mesin ai", "engine ai"
                ],
                "patterns": [
                    r"(?:apa|siapa)\s+(?:itu\s+)?satria",
                    r"bagaimana\s+cara\s+(?:kerja|menggunakan|tanya)",
                    r"teknologi\s+(?:apa|yang)\s+digunakan(?:\s+(?:oleh\s+)?satria|\s+bot)?",
                    r"apakah\s+kamu\s+(?:ai|robot|bot)",
                    r"kemampuan\s+analisis\s+satria",
                    r"(?:apakah|apakah\s+kamu|sudahkah\s+kamu)\s+(?:sudah\s+)?terintegrasi\s+(?:dengan\s+)?(?:microsoft|maf|agent\s+framework)",
                    r"microsoft\s+agent\s+framework",
                    r"integrasi\s+(?:dengan\s+)?(?:microsoft|maf)"
                ]
            },
            NonServiceCategory.COMPLAINT: {
                "keywords": [
                    "kecewa", "kurang puas", "tidak puas", "buruk", "jelek",
                    "mengecewakan", "susah", "ribet", "payah", "tidak membantu", "kurang memuaskan"
                ],
                "patterns": [
                    r"saya\s+(?:kecewa|tidak\s+puas|kesal)",
                    r"jawaban(?:nya)?\s+(?:yang\s+\w+\s+)?(?:kurang|tidak)\s+memuaskan",
                    r"bot\s+(?:jelek|buruk|tidak\s+berguna|payah)"
                ]
            },
            NonServiceCategory.PERSONAL_REQUEST: {
                "keywords": [
                    "resep masakan", "lirik lagu", "curhat", "jodoh", "cerita lucu",
                    "game", "film", "ramalan", "zodiak", "tebak-tebakan"
                ],
                "patterns": [
                    r"(?:ceritakan|tuliskan)\s+(?:lelucon|dongeng|lirik)",
                    r"ramal\s+(?:nasib|zodiak)"
                ]
            }
        }

    def detect(self, user_input: str) -> Optional[NonServiceCategory]:
        """
        Mendeteksi apakah pesan pengguna termasuk kategori non-pelayanan.
        Mengembalikan kategori yang cocok atau None jika berupa kueri pelayanan normal.
        """
        if not user_input or len(user_input.strip()) < 3:
            return None

        clean_text = user_input.lower().strip()
        scores: Dict[NonServiceCategory, int] = {}

        for category, config in self.patterns.items():
            score = 0
            for kw in config.get("keywords", []):
                if re.search(r'\b' + re.escape(kw) + r'\b', clean_text):
                    score += 2
            for pat in config.get("patterns", []):
                if re.search(pat, clean_text, re.IGNORECASE):
                    score += 4
            if score > 0:
                scores[category] = score

        if not scores:
            return None

        # Safeguard Dokumen, Regulasi & Substansi Kedinasan:
        # Jika pesan menyangkut surat, arsip, regulasi, berkas, atau substansi perumusan kebijakan (DIM, RUU, Bangda),
        # jangan pernah dialihkan ke non-pelayanan (FEATURE_REQUEST / SYSTEM_QUESTION)
        substantive_indicators = [
            "surat", "arsip", "regulasi", "peraturan", "pasal", "dokumen", "uu",
            "undang-undang", "permendagri", "pp", "daerah", "anri", "kementerian",
            "tampilkan", "cari", "file", "berkas", "aduan", "lapor", "draf", "ranperda",
            "inventaris", "dim", "ruu", "bina pembangunan daerah", "bangda", "potensi masalah"
        ]
        is_substantive_query = any(re.search(r'\b' + re.escape(w) + r'\b', clean_text) for w in substantive_indicators)
        if is_substantive_query:
            if NonServiceCategory.FEATURE_REQUEST in scores:
                del scores[NonServiceCategory.FEATURE_REQUEST]
            if NonServiceCategory.SYSTEM_QUESTION in scores:
                del scores[NonServiceCategory.SYSTEM_QUESTION]

        if not scores:
            return None

        best_category = max(scores, key=scores.get)
        # Ambang batas minimal keyakinan (untuk feature request butuh skor minimal 4)
        min_threshold = 4 if best_category == NonServiceCategory.FEATURE_REQUEST else 2
        if scores[best_category] >= min_threshold:
            return best_category

        return None


class NonServiceHandlers:
    """
    Handler responsif untuk menangani setiap kategori non-pelayanan dengan etika birokrasi,
    mencatat feedback, dan memperbarui backlog produk secara persisten di storage/admin_data.
    """

    def __init__(self):
        self._ensure_directories()

    def _ensure_directories(self):
        """Memastikan struktur direktori storage/admin_data telah siap."""
        FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
        BACKLOG_DIR.mkdir(parents=True, exist_ok=True)
        TRAINING_DIR.mkdir(parents=True, exist_ok=True)

    async def _append_jsonl(self, file_path: Path, data: Dict[str, Any]):
        """Menambahkan satu baris JSONL ke file secara aman dengan PII masking."""
        try:
            clean_data = satria_pii_sanitizer.sanitize_log_dict(data)
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(clean_data, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to append JSONL to {file_path}: {e}")

    def _load_json(self, file_path: Path, default: Any) -> Any:
        """Membaca file JSON persisten."""
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return default

    def _save_json(self, file_path: Path, data: Any):
        """Menyimpan file JSON persisten dengan PII masking."""
        try:
            clean_data = (
                [satria_pii_sanitizer.sanitize_log_dict(item) if isinstance(item, dict) else item for item in data]
                if isinstance(data, list)
                else (satria_pii_sanitizer.sanitize_log_dict(data) if isinstance(data, dict) else data)
            )
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(clean_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save JSON to {file_path}: {e}")

    async def handle_technical_feedback(self, user_input: str, user: Dict[str, Any]) -> str:
        """Menangani laporan bug teknis, error, atau latensi."""
        issue_id = f"ISSUE-2026-{int(time.time() * 1000) % 10000:04d}"
        today_str = datetime.now().strftime("%Y%m%d")

        issue_entry = {
            "issue_id": issue_id,
            "timestamp": datetime.now().isoformat(),
            "user_phone": user.get("phone_number", ""),
            "user_name": user.get("full_name", "Pengguna"),
            "description": user_input.strip(),
            "severity": "high" if any(k in user_input.lower() for k in ["crash", "mati", "error", "gagal"]) else "medium",
            "status": "OPEN"
        }

        # Simpan ke issues persisten
        issues_file = BACKLOG_DIR / "technical_issues.json"
        issues_data = self._load_json(issues_file, [])
        issues_data.append(issue_entry)
        self._save_json(issues_file, issues_data)

        # Log feedback harian
        await self._append_jsonl(FEEDBACK_DIR / f"feedback_{today_str}.jsonl", {
            "type": "technical_feedback",
            **issue_entry
        })

        return (
            f"🛠️ *LAPORAN TEKNIS DITERIMA — SATRIA*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Yth. Bapak/Ibu *{user.get('full_name')}*,\n\n"
            f"Terima kasih atas laporan Anda. Catatan kendala teknis telah kami daftarkan ke sistem antrean perbaikan:\n"
            f"• *Nomor Tiket:* `{issue_id}`\n"
            f"• *Waktu Lapor:* {datetime.now().strftime('%d-%m-%Y %H:%M WIB')}\n"
            f"• *Status:* `Dalam Antrean Tim Rekayasa AI`\n\n"
            f"Kami terus memantau stabilitas layanan agar analisis regulasi dan data kepegawaian dapat disajikan secara prima."
        )

    async def handle_feature_request(self, user_input: str, user: Dict[str, Any]) -> str:
        """Menangani usulan fitur atau ide pengembangan baru dari pengguna."""
        feat_id = f"FEAT-2026-{int(time.time() * 1000) % 10000:04d}"
        today_str = datetime.now().strftime("%Y%m%d")

        backlog_file = BACKLOG_DIR / "product_backlog.json"
        backlog_data = self._load_json(backlog_file, [])

        # Cek apakah usulan serupa sudah ada
        similar_found = False
        for item in backlog_data:
            if any(w in item["title"].lower() for w in user_input.lower().split() if len(w) > 4):
                item["votes"] = item.get("votes", 1) + 1
                feat_id = item["id"]
                similar_found = True
                break

        if not similar_found:
            new_feat = {
                "id": feat_id,
                "title": user_input.strip()[:60] + "...",
                "full_proposal": user_input.strip(),
                "proposed_by": user.get("full_name", "Pengguna"),
                "proposed_phone": user.get("phone_number", ""),
                "created_at": datetime.now().isoformat(),
                "votes": 1,
                "status": "BACKLOG"
            }
            backlog_data.append(new_feat)

        self._save_json(backlog_file, backlog_data)

        # Log feedback
        await self._append_jsonl(FEEDBACK_DIR / f"feedback_{today_str}.jsonl", {
            "type": "feature_request",
            "feat_id": feat_id,
            "user_phone": user.get("phone_number", ""),
            "proposal": user_input.strip()
        })

        return (
            f"💡 *USULAN PENGEMBANGAN FITUR DICATAT — SATRIA*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Yth. Bapak/Ibu *{user.get('full_name')}*,\n\n"
            f"Ide dan masukan Anda sangat berharga bagi evolusi SATRIA! Usulan fitur telah dimasukkan ke dalam *Product Backlog*:\n"
            f"• *ID Usulan:* `{feat_id}`\n"
            f"• *Kategori:* Pengembangan Kapabilitas AI Ditjen Bangda\n"
            f"• *Catatan:* {'Dukungan suara (upvote) berhasil ditambahkan.' if similar_found else 'Usulan baru terdaftar dalam prioritas telaah sprint.'}\n\n"
            f"Terima kasih atas kontribusi aktif Bapak/Ibu dalam memajukan tata kelola digital Ditjen Bangda."
        )

    async def handle_data_correction(self, user_input: str, user: Dict[str, Any]) -> str:
        """Menangani koreksi data master kepegawaian atau rujukan regulasi dari pengguna ahli."""
        corr_id = f"CORR-2026-{int(time.time() * 1000) % 10000:04d}"
        today_str = datetime.now().strftime("%Y%m%d")

        corr_entry = {
            "correction_id": corr_id,
            "timestamp": datetime.now().isoformat(),
            "submitted_by": user.get("full_name", ""),
            "phone_number": user.get("phone_number", ""),
            "correction_note": user_input.strip(),
            "status": "PENDING_VERIFICATION"
        }

        # Simpan ke pending data corrections
        corr_file = BACKLOG_DIR / "pending_data_corrections.json"
        corr_data = self._load_json(corr_file, [])
        corr_data.append(corr_entry)
        self._save_json(corr_file, corr_data)

        # Log feedback
        await self._append_jsonl(FEEDBACK_DIR / f"feedback_{today_str}.jsonl", {
            "type": "data_correction",
            **corr_entry
        })

        return (
            f"📝 *KOREKSI DATA DITERIMA — SATRIA*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Yth. Bapak/Ibu *{user.get('full_name')}*,\n\n"
            f"Koreksi informasi data master telah berhasil kami arsipkan dengan nomor registrasi:\n"
            f"• *Nomor Registrasi:* `{corr_id}`\n"
            f"• *Status:* `Menunggu Validasi Dokumen SK / Sumber Resmi`\n\n"
            f"Setelah diverifikasi oleh administrator data, perubahan akan otomatis disinkronkan ke dalam Master Knowledge Base SATRIA. Terima kasih atas ketelitian Bapak/Ibu."
        )

    async def handle_system_question(self, user_input: str, user: Dict[str, Any]) -> str:
        """Menjawab pertanyaan seputar profil SATRIA, integrasi Microsoft Agent Framework (MAF), arsitektur MCP, dan panduan penggunaan."""
        return (
            f"🤖 *STATUS INTEGRASI SATRIA & ARSITEKTUR MAF/MCP*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Yth. Bapak/Ibu *{user.get('full_name')}*,\n\n"
            f"**STATUS: 🟢 TERINTEGRASI PENUH DENGAN MICROSOFT AGENT FRAMEWORK (MAF)**\n\n"
            f"**SATRIA** (*Sistem Analisis Tata Kelola, Regulasi, & Insan Aparatur*) adalah asisten cerdas berlevel Fungsional Ahli Madya Ditjen Bangda Kemendagri RI yang telah beroperasi di atas arsitektur terintegrasi:\n\n"
            f"📌 *Arsitektur & Landasan Teknologi Resmi:*\n"
            f"1. **Microsoft Agent Framework (MAF Engine):** Engine orkestrasi agen inti (`agent-framework-core` v1.19.0) yang mengelola penalaran kognitif multi-step, multi-channel session persistence, dan routing multi-agent secara terpadu.\n"
            f"2. **Model Context Protocol (MCP Universal Hub):** Standar protokol terbuka yang menghubungkan MAF Engine ke perkakas database internal (RAG pgvector regulasi 2024–2026, Master Data Kepegawaian SK 2026 Ditjen Bangda, dan database korespondensi persuratan).\n"
            f"3. **Multi-Channel & Resilience Engine:** Dilengkapi *Circuit Breaker*, *Timeout Guard*, *Typing Keep-Alive*, dan *Session Memory* lintas-kanal (WhatsApp, Telegram, Web).\n\n"
            f"💡 *Kemampuan yang Dapat Diakses:*\n"
            f"• _\"Siapa koordinator atau Ahli Madya bidang PUU?\"_\n"
            f"• _\"Apa pokok muatan PP No. 1 Tahun 2026 tentang standar pelayanan dasar?\"_\n"
            f"• _\"Lakukan audit 6 dimensi BPHN terhadap naskah draf regulasi berikut...\"_\n"
            f"• _\"Cek status kesehatan sistem\"_ untuk memantau performa MAF dan database."
        )

    async def handle_complaint(self, user_input: str, user: Dict[str, Any]) -> str:
        """Menangani keluhan rasa tidak puas secara diplomatis dan berempati."""
        today_str = datetime.now().strftime("%Y%m%d")
        comp_id = f"COMP-2026-{int(time.time() * 1000) % 10000:04d}"

        # Catat ke log feedback untuk evaluasi kualitas pelayanan
        await self._append_jsonl(FEEDBACK_DIR / f"feedback_{today_str}.jsonl", {
            "type": "complaint",
            "complaint_id": comp_id,
            "timestamp": datetime.now().isoformat(),
            "user_phone": user.get("phone_number", ""),
            "user_name": user.get("full_name", ""),
            "text": user_input.strip()
        })

        return (
            f"🙏 *PERMOHONAN MAAF & EVALUASI LAYANAN — SATRIA*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Yth. Bapak/Ibu *{user.get('full_name')}*,\n\n"
            f"Kami memohon maaf yang sebesar-besarnya atas ketidaknyamanan yang Bapak/Ibu rasakan. Catatan evaluasi ini telah diregistrasi dengan ID `{comp_id}`.\n\n"
            f"Mohon berkenan menyampaikan bagian mana dari telaah atau data yang kurang sesuai agar tim pengembang dapat segera melakukan penyempurnaan pada sesi interaksi berikutnya."
        )

    async def handle_out_of_scope(self, user_input: str, user: Dict[str, Any]) -> str:
        """Menangani kueri di luar wewenang dan materi tugas Ditjen Bangda dengan santun."""
        return (
            f"🏛️ *PEMBERITAHUAN CAKUPAN LAYANAN — SATRIA*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Yth. Bapak/Ibu *{user.get('full_name')}*,\n\n"
            f"Pertanyaan yang diajukan berada di luar ruang lingkup kewenangan kedinasan SATRIA Ditjen Bina Pembangunan Daerah Kemendagri RI.\n\n"
            f"SATRIA difokuskan khusus untuk:\n"
            f"1. Pembagian Urusan Pemerintahan Konkuren Daerah (UU 23/2014)\n"
            f"2. Tata Kelola Ranperda & Uji 6-Dimensi BPHN Kemenkumham\n"
            f"3. Master Data Kepegawaian & Fungsional Ditjen Bangda (SK 2026)\n"
            f"4. Penelaahan Naskah Berkas Regulasi (PDF/DOCX)\n\n"
            f"Silakan mengajukan pertanyaan terkait topik-topik di atas."
        )


# Singleton instances
satria_non_service_detector = NonServiceDetector()
satria_non_service_handlers = NonServiceHandlers()

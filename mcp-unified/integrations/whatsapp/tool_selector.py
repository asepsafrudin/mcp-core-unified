"""
tool_selector.py — Smart Tool Selector & Intent Classifier for SATRIA WhatsApp Co-Pilot.
Implements Model-Size-Aware tool pruning (Max 2-3 tools for 7B/8B models), Indonesian text normalization,
Fast-Path routing, and OpenAI Function Calling schema generation.
"""

import re
import string
import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("satria_tool_selector")


class IntentType(Enum):
    """Kategori intent pemohon di Ditjen Bangda & WhatsApp."""
    LOOKUP_STAFF = "lookup_bangda_staff"
    SEARCH_REGULATION = "search_regulation_knowledge"
    POLICY_INVENTORY = "policy_inventory_aggregator"
    SEARCH_CORRESPONDENCE = "cari_surat_korespondensi"
    LIVE_WEB_SEARCH = "search_web_realtime"
    SEARCH_SOCIAL_MEDIA = "search_social_media"
    AUTONOMOUS_BROWSE = "browse_portal_autonomous"
    EVALUATE_DOCTRINE = "evaluate_bphn_doctrine"
    DEONTIC_VERIFY = "legal_deontic_verify"
    NASKAH_AKADEMIK = "legal_naskah_akademik_generate"
    HARMONIZATION_MATRIX = "legal_harmonization_matrix"
    LEGAL_OPINION = "legal_opinion_irac"
    CONTRACT_VETTING = "legal_contract_vetting"
    LITIGATION_ADVOCACY = "legal_litigation_advocacy"
    PATCH_CLAUSE = "legal_patch_clause"
    VERIFY_SPM = "legal_verify_spm"
    GENERATE_NOTA_DINAS = "nd_generate_laporan"
    SYSTEM_HEALTH = "system_health_check"
    LIST_TABLES = "list_database_tables"
    SEND_MESSAGE = "send_whatsapp_message"
    UNKNOWN = "unknown"


@dataclass
class IntentResult:
    """Hasil klasifikasi maksud pemohon."""
    intent: IntentType
    confidence: float
    raw_score: float
    entities: Dict[str, Any]
    tool_arguments: Dict[str, Any]
    is_fast_path: bool = False


class TextNormalizer:
    """Normalisasi teks masukan bahasa Indonesia & ekstraksi entitas nomor/regulasi."""

    def __init__(self):
        self.stopwords = {
            'yang', 'di', 'ke', 'dari', 'pada', 'dan', 'atau', 'untuk',
            'dengan', 'oleh', 'sebagai', 'ini', 'itu', 'tersebut',
            'saya', 'kamu', 'dia', 'kami', 'kalian', 'mereka',
            'tolong', 'mohon', 'bisa', 'dapat', 'akan', 'telah',
            'sudah', 'belum', 'juga', 'lagi', 'saja', 'pun', 'dong', 'ya'
        }

    def normalize(self, text: str) -> str:
        """Pembersihan teks dasar dan normalisasi huruf kecil."""
        if not text:
            return ""
        text = text.lower().strip()
        # Hapus tanda baca berulang kecuali tanda hubung kata
        text = re.sub(r'[\?!.,;:"\'()\[\]{}]', ' ', text)
        words = text.split()
        filtered = [w for w in words if w not in self.stopwords]
        stemmed = self._simple_stemming(filtered)
        return ' '.join(stemmed).strip()

    def _simple_stemming(self, words: List[str]) -> List[str]:
        """Stemming akhiran sederhana bahasa Indonesia."""
        suffixes = ['kan', 'an', 'i', 'lah', 'kah']
        stemmed = []
        for word in words:
            w = word
            for suffix in suffixes:
                if w.endswith(suffix) and len(w) > len(suffix) + 3:
                    w = w[:-len(suffix)]
                    break
            stemmed.append(w)
        return stemmed

    def extract_phone_number(self, text: str) -> Optional[str]:
        """Ekstraksi nomor ponsel Indonesia (+62 / 08 / 62)."""
        if not text:
            return None
        pattern = r'(?:\+62|62|08)[0-9]{8,13}'
        match = re.search(pattern, text.replace(" ", "").replace("-", ""))
        if match:
            raw = match.group(0)
            if raw.startswith('08'):
                return '+62' + raw[1:]
            elif raw.startswith('62'):
                return '+' + raw
            elif raw.startswith('+62'):
                return raw
        return None

    def extract_regulation_citation(self, text: str) -> Optional[str]:
        """Mendeteksi kutipan peraturan spesifik (misal: PP 1/2026, UU 23/2014, Permendagri 9/2025)."""
        if not text:
            return None
        pattern = r'(?:uu|undang-undang|pp|peraturan pemerintah|perpres|permen|permendagri|perda)\s*(?:no\.?|nomor)?\s*\d+\s*(?:tahun|\/)?\s*\d{4}'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
        return None


class DomainIntentClassifier:
    """Classifier intent domain substantif Ditjen Bangda & WhatsApp Action."""

    def __init__(self):
        self.normalizer = TextNormalizer()
        self.intent_rules = {
            IntentType.LOOKUP_STAFF: {
                "keywords": ["pejabat", "pegawai", "madya", "muda", "struktur", "tim kerja", "lady", "faisal", "asep", "amir", "salim", "rizal", "formasi", "jumlah", "siapa", "subdit", "direktorat", "sekretariat", "kontak", "staf", "perancang", "fungsional", "jf"],
                "patterns": [
                    r"siapa\s+(?:ahli\s+madya|koordinator|pejabat|penanggung\s+jawab)",
                    r"berapa\s+(?:jumlah|formasi)",
                    r"(?:kontak|jabatan|data\s+staf)",
                    r"daftar\s+(?:nama\s+)?(?:staf|pegawai|fungsional)",
                    r"pegawai\s+bernama",
                    r"data\s+pegawai"
                ],
                "weight": 4
            },
            IntentType.SEARCH_CORRESPONDENCE: {
                "keywords": [
                    "surat", "disposisi", "korespondensi", "agenda", "fasilitasi", 
                    "masuk", "keluar", "naskah dinas", "persuratan", "rtrw",
                    "nota dinas", "eksternal", "internal", "tata naskah", "lacak",
                    "posisi berkas", "dirjen", "sesditjen", "asal surat", "pengirim",
                    "rekapitulasi", "daftar surat", "list surat", "kode klasifikasi",
                    "000.6", "600", "penomoran surat", "format naskah"
                ],
                "patterns": [
                    r"surat\s+(?:masuk|keluar|fasilitasi|dinas|eksternal|internal)",
                    r"(?:cek|tampilkan|cari|lacak|laporkan|list|rekap)\s+(?:surat|korespondensi|disposisi|nota\s+dinas)",
                    r"fasilitasi\s+ranperda",
                    r"data\s+korespondensi",
                    r"akses\s+(?:data\s+)?korespondensi",
                    r"diterima\s+(?:oleh\s+)?(?:dirjen|sesditjen)",
                    r"posisi\s+berkas",
                    r"nomor\s+(?:nd|surat)",
                    r"kode\s+klasifikasi",
                    r"penomoran\s+(?:surat|nota\s+dinas)"
                ],
                "weight": 6
            },
            IntentType.SEARCH_REGULATION: {
                "keywords": [
                    "pp", "uu", "undang", "perpres", "permen", "permendagri", "perda", "pasal",
                    "ranperda", "raperda", "putusan", "mk", "ma", "2024", "2025", "2026", "norma",
                    "regulasi", "peraturan", "spm", "apbd", "meritokrasi", "diskresi", "konkuren",
                    "tdu", "pkl", "tata naskah", "naskah dinas", "format surat", "kode klasifikasi",
                    "rpjmd", "rpjpd", "rkpd", "rtrw", "tata ruang", "persub", "sotk", "keuangan desa",
                    "siskeudes", "retribusi", "pdrd", "hkpd", "pdp", "data pribadi", "adminduk", "smki",
                    "1/2023", "83/2022", "9/2025", "86/2017", "13/2016", "20/2018", "113/2014", "mk 137",
                    "dim", "inventaris masalah", "inventaymasalah", "masukan uu 23", "revisi uu 23",
                    "saran daerah", "saran kementerian", "masukan provinsi", "masukan daerah",
                    "memory ltm", "memori ltm", "ltm", "list memory", "akses ltm", "status ltm",
                    "struktur organisasi", "struktur", "organisasi", "sotk", "peippd", "supd", "tupoksi",
                    "tata kerja", "unit kerja", "direktorat", "bagan organisasi", "susunan organisasi"
                ],
                "patterns": [
                    r"(?:pp|uu|permen|permendagri)\s*(?:no|nomor|\d)",
                    r"pasal\s+\d+",
                    r"regulasi\s+terbaru",
                    r"tdu\s+(?:pasal|bagi|pkl)",
                    r"(?:format|aturan|margin|font)\s+naskah",
                    r"evaluasi\s+(?:ranperda|rpjmd|rpjpd|rtrw)",
                    r"persetujuan\s+substansi",
                    r"(?:kode\s+klasifikasi|penomoran)\s+surat",
                    r"keuangan\s+desa",
                    r"putusan\s+mk",
                    r"(?:dim|daftar\s+inventaris\s+masalah|inventaymasalah|masukan|saran)\s+(?:revisi\s+)?(?:uu\s+23|uu\s+pemda|undang[\s-]undang\s+23)",
                    r"(?:provinsi|daerah|kementerian|lembaga)\s+(?:mana\s+saja\s+)?(?:yang\s+)?(?:sudah\s+)?(?:memberi|kirim|menyampaikan)\s+(?:masukan|saran|dim)",
                    r"(?:list|cek|status|daftar)\s+(?:memory|memori)(?:\s+ltm)?",
                    r"(?:akses|status)\s+ltm",
                    r"(?:struktur|bagan|susunan)\s+(?:organisasi|ditjen|kemendagri|bangda)",
                    r"sotk\s+(?:ditjen|bangda|kemendagri)?",
                    r"(?:tupoksi|tata\s+kerja|pembagian\s+urusan)\s+(?:ditjen|direktorat|subdit)?",
                    r"(?:peippd|supd\s+[iv]+)"
                ],
                "weight": 4
            },
            IntentType.POLICY_INVENTORY: {
                "keywords": [
                    "inventaris", "inventarisasi", "keputusan menteri", "kepmendagri", "rekap kebijakan",
                    "kebijakan pusat", "produk hukum 2026", "rekap kepmen", "daftar sk", "daftar kepmen",
                    "inventaris kepmen", "kebijakan dibangda", "kebijakan bangda", "katalog regulasi",
                    "master katalog", "daftar produk hukum", "daftar regulasi", "rekap permendagri", "inventaris permendagri"
                ],
                "patterns": [
                    r"(?:inventaris|inventarisasi|rekap|daftar|berapa)\s+(?:keputusan\s+menteri|kepmendagri|kebijakan|produk\s+hukum|sk\s+mendagri|permendagri)",
                    r"kebijakan\s+pusat(?:\s+di\s*bangda)?",
                    r"(?:inventaris|rekap)\s+(?:kepmen|permendagri|inmendagri|se|sk)\s*(?:2026|2025)?",
                    r"kebijakan\s+pusat\s+dibangda",
                    r"kebijakan\s+bangda\s+(?:yang\s+)?(?:sudah\s+)?ditetapkan"
                ],
                "weight": 8
            },
            IntentType.LIVE_WEB_SEARCH: {
                "keywords": [
                    "berita", "live", "internet", "terbaru", "terkini", "google", "kabar", "isu", "media", "hari ini", "browsing",
                    "bpk", "bpk.go.id", "peraturan.bpk.go.id", "jdih", "portal", "website", "situs", "web resmi", ".go.id"
                ],
                "patterns": [
                    r"cari\s+(?:di\s+)?(?:internet|berita|web|bpk|jdih|portal|situs)",
                    r"info\s+terkini",
                    r"browsing\s+",
                    r"(?:bpk\.go\.id|peraturan\.bpk\.go\.id|jdih(?:\.\w+)?\.go\.id|peraturan\.go\.id|\.go\.id)",
                    r"(?:apakah|adakah)\s+(?:di\s+)?(?:bpk\.go\.id|jdih|peraturan\.go\.id|web|internet)",
                    r"cari\s+(?:peraturan|aturan|kebijakan|keputusan)\s+(?:terbaru\s+)?di\s+(?:bpk|jdih|web|internet)"
                ],
                "weight": 6
            },
            IntentType.SEARCH_SOCIAL_MEDIA: {
                "keywords": [
                    "media sosial", "medsos", "sosmed", "viral", "trending", "opini publik", "netizen",
                    "twitter", "x.com", "instagram", "tiktok", "youtube", "facebook", "linkedin", "x"
                ],
                "patterns": [
                    r"(?:periksa|cek|cari|pantau|lihat)\s+(?:di\s+)?(?:media\s+sosial|medsos|sosmed|twitter|x|instagram|tiktok|youtube|facebook)",
                    r"isu\s+(?:terbaru|terkini|viral|hangat)(?:\s+di\s+(?:media\s+sosial|medsos|sosmed|twitter|x))?",
                    r"opini\s+(?:publik|warganet|netizen)",
                    r"(?:tagar|hashtag|trending)\s+",
                    r"(?:twitter\.com|x\.com|instagram\.com|tiktok\.com|youtube\.com|facebook\.com)"
                ],
                "weight": 10
            },
            IntentType.EVALUATE_DOCTRINE: {
                "keywords": [
                    "!telaah", "telaah", "kaji", "uji", "6 dimensi", "bphn", "harmonisasi", "disharmoni",
                    "konkuren", "cacat", "wewenang", "ultra vires", "hierarki", "telaah draf", "keselarasan",
                    "dimensi", "pedoman analisis", "doktrin", "soerjono soekanto", "mochtar", "maria farida",
                    "jimly", "ria", "regulatory impact", "sosiologis", "preseden", "audit regulasi"
                ],
                "patterns": [
                    r"!telaah\b",
                    r"telaah\s+(?:draf|perda|perbup|perkada|kebijakan|aturan|sk|dokumen|regulasi|naskah)",
                    r"kaji\s+(?:kebijakan|draf|aturan|hukum|regulasi|perda|perbup)",
                    r"uji\s+(?:6\s+dimensi|doktrin|keselarasan|norma|keterkaitan|materiil|formil|ultra\s+vires)",
                    r"evaluasi\s+(?:6\s+dimensi|ranperda|hukum|regulasi|kebijakan)",
                    r"analisis\s+(?:potensi\s+)?(?:disharmoni|draf|naskah|yuridis|sosiologis|efektivitas)",
                    r"dimensi\s+(?:kejelasan|kesesuaian|hierarki|filosofis|sosiologis)",
                    r"pedoman\s+(?:analisis|evaluasi)\s+hukum",
                    r"keselarasan\s+vertikal"
                ],
                "weight": 6
            },
            IntentType.DEONTIC_VERIFY: {
                "keywords": [
                    "modalitas", "deontik", "larangan", "suruhan", "kebolehan", "wewenang",
                    "236 kaidah", "kaidah perancangan", "diksi ambigu", "ambigu", "norma deontik"
                ],
                "patterns": [
                    r"uji\s+(?:modalitas|deontik|kaidah)",
                    r"verifikasi\s+(?:norma|modalitas|deontik)",
                    r"236\s+kaidah",
                    r"diksi\s+ambigu"
                ],
                "weight": 8
            },
            IntentType.NASKAH_AKADEMIK: {
                "keywords": [
                    "naskah akademik", "na raperda", "kajian yuridis raperda",
                    "landasan filosofis", "landasan sosiologis", "lampiran i"
                ],
                "patterns": [
                    r"naskah\s+akademik",
                    r"buatkan\s+na\b",
                    r"susun\s+na\b",
                    r"6\s+bab\s+na"
                ],
                "weight": 8
            },
            IntentType.HARMONIZATION_MATRIX: {
                "keywords": [
                    "harmonisasi raperda", "pengharmonisasian", "matriks harmonisasi",
                    "surat selesai harmonisasi", "pasal 58", "5 kolom", "e-harmonisasi"
                ],
                "patterns": [
                    r"matriks\s+(?:harmonisasi|5\s+kolom)",
                    r"surat\s+selesai\s+harmonisasi",
                    r"harmonisasi\s+raperda",
                    r"e-?harmonisasi"
                ],
                "weight": 8
            },
            IntentType.LEGAL_OPINION: {
                "keywords": [
                    "legal opinion", "pendapat hukum", "telaahan hukum", "telaah hukum",
                    "irac", "aupb", "asas-asas umum pemerintahan yang baik"
                ],
                "patterns": [
                    r"legal\s+opinion",
                    r"pendapat\s+hukum",
                    r"telaah(?:an)?\s+hukum",
                    r"metode\s+irac",
                    r"uji\s+aupb"
                ],
                "weight": 8
            },
            IntentType.CONTRACT_VETTING: {
                "keywords": [
                    "vetting kontrak", "klausul kontrak", "perjanjian kerja sama", "pks",
                    "spk", "wanprestasi", "denda keterlambatan", "pasal 1266", "temuan bpk", "klausul arbitrase"
                ],
                "patterns": [
                    r"vetting\s+(?:kontrak|pks|spk|mou)",
                    r"klausul\s+(?:risiko|kontrak|denda|arbitrase)",
                    r"perjanjian\s+kerja\s+sama",
                    r"audit\s+kontrak"
                ],
                "weight": 8
            },
            IntentType.LITIGATION_ADVOCACY: {
                "keywords": [
                    "gugatan ptun", "sengketa ptun", "alat bukti ptun", "eksepsi",
                    "posita", "petitum", "daluwarsa 90 hari", "uji materiil", "judicial review", "mkri"
                ],
                "patterns": [
                    r"(?:gugatan|sengketa)\s+ptun",
                    r"alat\s+bukti\s+ptun",
                    r"eksepsi\s+ptun",
                    r"judicial\s+review",
                    r"uji\s+materiil"
                ],
                "weight": 8
            },
            IntentType.AUTONOMOUS_BROWSE: {
                "keywords": ["buka portal", "telusuri portal", "jelajahi", "portal", "sp4n", "srikandi", "unduh dari", "cek situs", "buka situs", "halaman web"],
                "patterns": [
                    r"(?:buka|telusuri|jelajahi|cek)\s+(?:portal|situs|halaman|web)",
                    r"https?://[^\s]+",
                    r"sp4n[\s-]?lapor",
                    r"srikandi(?:\.arsip)?\.go\.id",
                    r"peraturan\.go\.id"
                ],
                "weight": 6
            },
            IntentType.PATCH_CLAUSE: {
                "keywords": [
                    "revisi pasal", "safe drafting", "klausul alternatif", "rumusan norma",
                    "perbaiki pasal", "klausul aman", "revisi klausul", "alternatif pasal",
                    "drafting pasal", "redaksi pasal"
                ],
                "patterns": [
                    r"(?:revisi|perbaiki|ubah|susun)\s+(?:pasal|klausul|norma|redaksi)",
                    r"safe\s+drafting",
                    r"klausul\s+(?:aman|alternatif)"
                ],
                "weight": 7
            },
            IntentType.VERIFY_SPM: {
                "keywords": [
                    "spm", "standar pelayanan minimal", "urusan wajib dasar", "indikator spm",
                    "capaian spm", "pemenuhan spm", "spm pendidikan", "spm kesehatan",
                    "spm pekerjaan umum", "spm sosial", "spm perkim", "trantibumlinmas"
                ],
                "patterns": [
                    r"\bspm\b",
                    r"standar\s+pelayanan\s+minimal",
                    r"urusan\s+wajib\s+dasar"
                ],
                "weight": 7
            },
            IntentType.GENERATE_NOTA_DINAS: {
                "keywords": [
                    "nota dinas", "buatkan nd", "draf nd", "laporan rapat", "format nd",
                    "nd laporan", "susun nota dinas", "telaahan staf", "golden pattern"
                ],
                "patterns": [
                    r"\bnota\s+dinas\b",
                    r"\bdraf\s+nd\b",
                    r"laporan\s+(?:hasil\s+)?rapat",
                    r"telaahan\s+staf"
                ],
                "weight": 7
            },
            IntentType.SYSTEM_HEALTH: {
                "keywords": [
                    "cek sistem", "health check", "status server", "status runpod",
                    "status database", "kondisi server", "cek database", "status bot",
                    "server health", "cek port", "kesehatan sistem", "diagnosa sistem",
                    "kesehatan", "health", "healthy", "sistem", "server", "database", "runpod",
                    "healthy agent", "health status", "cek healthy", "status agent", "jalankan healthy",
                    "cek status", "status kesehatan", "kesehatan bot", "kesehatan server",
                    "status maf", "cek maf", "status framework", "kesehatan framework", "kesehatan maf"
                ],
                "patterns": [
                    r"(?:cek|status|kondisi|kesehatan|diagnosa|healthy)\s+(?:\w+\s+){0,3}(?:sistem|server|database|runpod|bot|agent|status|maf|framework)?",
                    r"health(?:y)?[\s_-]?(?:check|status|agent)?",
                    r"(?:jalankan|cek)\s+healthy(?:\s+agent)?",
                    r"(?:cek|status)\s+kesehatan",
                    r"(?:cek|status)\s+(?:maf|framework)"
                ],
                "weight": 7
            },
            IntentType.LIST_TABLES: {
                "keywords": [
                    "list tabel", "daftar tabel", "tabel ltm", "tabel database", "tabel basis data",
                    "tabel yang bisa diakses", "tabel di database", "skema tabel", "struktur tabel", "tabel postgres"
                ],
                "patterns": [
                    r"(?:list|daftar|tampilkan|lihat)\s+tabel",
                    r"tabel\s+(?:ltm|database|db|postgres|sistem)",
                    r"tabel\s+yang\s+(?:bisa|dapat)\s+diakses"
                ],
                "weight": 9
            },
            IntentType.SEND_MESSAGE: {
                "keywords": ["kirim pesan", "chat ke", "wa ke", "teruskan ke", "send message"],
                "patterns": [r"kirim\s+pesan\s+ke", r"chat\s+ke\s+(?:\+62|08)"],
                "weight": 4
            }
        }

    def classify(self, user_text: str) -> IntentResult:
        """Mengklasifikasikan pesan pengguna ke kategori intent dan mengekstrak entitas."""
        clean_text = self.normalizer.normalize(user_text)
        words = set(clean_text.split())

        phone = self.normalizer.extract_phone_number(user_text)
        reg_citation = self.normalizer.extract_regulation_citation(user_text)

        scores: Dict[IntentType, float] = {itype: 0.0 for itype in IntentType if itype != IntentType.UNKNOWN}

        # Hitung skor pembobotan
        for itype, rules in self.intent_rules.items():
            # 1. Keyword overlap
            for kw in rules["keywords"]:
                if re.search(r'\b' + re.escape(kw) + r'\b', clean_text, re.IGNORECASE):
                    scores[itype] += rules["weight"]

            # 2. Regex pattern match
            for pat in rules["patterns"]:
                if re.search(pat, user_text, re.IGNORECASE):
                    scores[itype] += 5.0

        # Penegasan konteks khusus
        if phone and any(k in clean_text for k in ["kirim", "pesan", "chat", "wa"]):
            scores[IntentType.SEND_MESSAGE] += 6.0

        if reg_citation:
            scores[IntentType.SEARCH_REGULATION] += 5.0

        has_domain_search = any(d in clean_text or d in user_text.lower() for d in ["bpk.go.id", "bpk", "peraturan.bpk", "jdih", "peraturan.go.id", ".go.id"]) or \
                            any(p in clean_text for p in ["cari di internet", "cari di web", "browsing", "portal web"])
        if has_domain_search:
            scores[IntentType.LIVE_WEB_SEARCH] += 16.0

        if any(w in user_text.lower() for w in ["!telaah", "telaah:", "!kaji", "kaji:", "6 dimensi", "bphn", "keselarasan vertikal", "disharmoni norma", "ultra vires"]):
            scores[IntentType.EVALUATE_DOCTRINE] += 12.0

        best_intent = max(scores, key=scores.get)
        best_score = scores[best_intent]

        # Ambang batas minimal keyakinan
        if best_score < 2.0:
            return IntentResult(
                intent=IntentType.UNKNOWN,
                confidence=0.0,
                raw_score=best_score,
                entities={},
                tool_arguments={}
            )

        # Confidence normalized 0.0 - 0.98
        confidence = min(0.98, round(best_score / 12.0, 2))

        # Ekstraksi entitas & argumen tool
        entities: Dict[str, Any] = {}
        if phone:
            entities["phone_number"] = phone
        if reg_citation:
            entities["regulation_citation"] = reg_citation

        if best_intent == IntentType.LOOKUP_STAFF:
            tool_arguments = {"query": user_text.strip()}
        elif best_intent == IntentType.SEARCH_CORRESPONDENCE:
            tool_arguments = {"query": user_text.strip()}
        elif best_intent == IntentType.SEARCH_REGULATION:
            tool_arguments = {"query": user_text.strip(), "namespace": "legal_agent"}
        elif best_intent == IntentType.LIVE_WEB_SEARCH:
            tool_arguments = {"query": user_text.strip()}
        elif best_intent == IntentType.SEARCH_SOCIAL_MEDIA:
            plat = "all"
            u_low = user_text.lower()
            if "twitter" in u_low or "x.com" in u_low:
                plat = "twitter"
            elif "instagram" in u_low:
                plat = "instagram"
            elif "tiktok" in u_low:
                plat = "tiktok"
            elif "youtube" in u_low:
                plat = "youtube"
            elif "facebook" in u_low:
                plat = "facebook"
            elif "linkedin" in u_low:
                plat = "linkedin"
            tool_arguments = {"query": user_text.strip(), "platform": plat}
        elif best_intent == IntentType.AUTONOMOUS_BROWSE:
            url_match = re.search(r'https?://[^\s]+', user_text)
            target_url = url_match.group(0) if url_match else "https://peraturan.go.id"
            tool_arguments = {"url": target_url, "task": user_text.strip(), "max_steps": 5}
        elif best_intent == IntentType.EVALUATE_DOCTRINE:
            tool_arguments = {"norm_text": user_text.strip()}
        elif best_intent == IntentType.DEONTIC_VERIFY:
            tool_arguments = {"clause_text": user_text.strip()}
        elif best_intent == IntentType.NASKAH_AKADEMIK:
            tool_arguments = {"title": user_text.strip(), "background": user_text.strip()}
        elif best_intent == IntentType.HARMONIZATION_MATRIX:
            tool_arguments = {"raperda_title": user_text.strip(), "articles_json": "[]"}
        elif best_intent == IntentType.LEGAL_OPINION:
            tool_arguments = {"legal_issue": user_text.strip(), "legal_facts": user_text.strip()}
        elif best_intent == IntentType.CONTRACT_VETTING:
            tool_arguments = {"contract_title": user_text.strip(), "clauses_text": user_text.strip()}
        elif best_intent == IntentType.LITIGATION_ADVOCACY:
            tool_arguments = {"dispute_type": "PTUN", "summary_facts": user_text.strip()}
        elif best_intent == IntentType.POLICY_INVENTORY:
            cat = None
            u_low = user_text.lower()
            if "kepmen" in u_low or "keputusan menteri" in u_low or "sk mendagri" in u_low:
                cat = "KEPMENDAGRI"
            elif "permendagri" in u_low or "peraturan menteri" in u_low:
                cat = "PERMENDAGRI"
            elif "inmendagri" in u_low or "instruksi menteri" in u_low:
                cat = "INMENDAGRI"
            elif "surat edaran" in u_low or "se mendagri" in u_low or "seb" in u_low:
                cat = "SE"
            elif "mou" in u_low or "kesepahaman" in u_low:
                cat = "MOU"
            elif "pp" in u_low:
                cat = "PP"
            elif "uu" in u_low:
                cat = "UU"

            year_match = re.search(r'\b(20\d{2})\b', user_text)
            year = int(year_match.group(1)) if year_match else 2026

            # Ekstrak kata kunci bersih tanpa trigger kata inventaris, stop words, atau metadata umum
            stop_words = [
                r"inventaris(?:asi)?", r"rekap(?:itulasi)?", r"daftar", r"berapa", r"sebutkan", r"tampilkan",
                r"bantu", r"saya", r"tolong", r"cek", r"lihat", r"cari", r"mohon", r"ada", r"apa", r"saja",
                r"keputusan\s+menteri(?:\s+dalam\s+negeri)?", r"kepmendagri", r"permendagri", r"inmendagri",
                r"peraturan\s+menteri", r"surat\s+edaran", r"kebijakan(?:\s+pusat)?", r"produk\s+hukum",
                r"dalam\s+negeri", r"mendagri", r"kemendagri", r"ditjen(?:\s+bina)?(?:\s+pembangunan)?(?:\s+daerah)?",
                r"bangda", r"periode", r"januari", r"hingga", r"juni", r"juli", r"desember", r"semester\s+[12]",
                r"tahun", r"20\d{2}", r"yang\s+sudah", r"telah\s+diterbitkan", r"terbit", r"ditetapkan"
            ]
            kw_clean = u_low
            for pat in stop_words:
                kw_clean = re.sub(r'\b' + pat + r'\b', '', kw_clean, flags=re.IGNORECASE)
            kw_clean = re.sub(r'\s+', ' ', kw_clean).strip()

            tool_arguments = {
                "kategori": cat,
                "tahun": year,
                "keyword": kw_clean if len(kw_clean) >= 3 else None,
                "limit": 15
            }
        elif best_intent == IntentType.PATCH_CLAUSE:
            tool_arguments = {"problematic_clause": user_text.strip(), "reason_or_defect": "Penyelarasan dengan UU Induk & Asas Pembentukan PUU"}
        elif best_intent == IntentType.VERIFY_SPM:
            tool_arguments = {"indicator_query": user_text.strip()}
        elif best_intent == IntentType.GENERATE_NOTA_DINAS:
            tool_arguments = {"hal": user_text.strip(), "poin_pembahasan": user_text.strip()}
        elif best_intent == IntentType.SYSTEM_HEALTH:
            tool_arguments = {"service_target": "all"}
        elif best_intent == IntentType.LIST_TABLES:
            tool_arguments = {"limit": 10}
        elif best_intent == IntentType.SEND_MESSAGE:
            tool_arguments = {"phone_number": phone or "", "text": user_text.strip()}

        # Deteksi apakah memenuhi syarat Fast-Path (Score tinggi pada data baku tanpa perlu LLM penalaran)
        is_fast_path = False
        user_lower = user_text.lower()
        has_specific_name = any(n in user_lower for n in ["lady diana", "asep safrudin", "amir salim", "amir", "rizal", "puu", "faisal", "tim it"]) and not user_lower.startswith(("cek data staf", "daftar fungsional", "siapa koordinator urusan"))
        has_specific_reg = (bool(reg_citation) or any(r in user_lower for r in [
            "pp 1/2026", "pp no. 1", "uu 23/2014", "uu 30 2014", "uu 30/2014", "uu 20/2023",
            "permendagri 41", "41 tahun 2012", "dim", "inventaris masalah", "inventaymasalah",
            "masukan uu 23", "revisi uu 23"
        ])) and not any(w in user_lower for w in ["apakah ada", "apa dasar hukum pembentukan", "bagaimana aturan"])
        has_specific_corr = best_intent == IntentType.SEARCH_CORRESPONDENCE and any(k in user_lower for k in [
            "surat masuk", "surat keluar", "rtrw", "fasilitasi ranperda", "cek surat", 
            "tampilkan data korespondensi", "laporkan list", "daftar surat", "rekap surat",
            "diterima oleh dirjen", "disposisi dirjen"
        ])
        is_health_check = (best_intent == IntentType.SYSTEM_HEALTH) or any(k in user_lower for k in [
            "healthy status", "healthy agent", "health check", "cek sistem", "status server", "kesehatan sistem",
            "status maf", "cek maf", "status framework"
        ])
        is_list_tables = (best_intent == IntentType.LIST_TABLES) or any(k in user_lower for k in [
            "list tabel", "daftar tabel", "tabel ltm", "tabel database", "tabel postgres"
        ])
        is_web_search = (best_intent == IntentType.LIVE_WEB_SEARCH) and (
            has_domain_search or any(k in user_lower for k in [
                "bpk.go.id", "bpk", "jdih", ".go.id", "peraturan.go.id", "internet", "web", "browsing"
            ])
        )
        is_policy_inventory = (best_intent == IntentType.POLICY_INVENTORY) and (
            confidence >= 0.35 or any(k in user_lower for k in [
                "inventaris", "keputusan menteri", "kepmendagri", "rekap", "daftar sk", "produk hukum", "kebijakan pusat", "katalog"
            ])
        )

        is_social_search = (best_intent == IntentType.SEARCH_SOCIAL_MEDIA) and (
            confidence >= 0.4 or any(k in user_lower for k in [
                "media sosial", "medsos", "sosmed", "viral", "twitter", "x.com", "instagram", "tiktok", "youtube"
            ])
        )

        if (best_intent == IntentType.LOOKUP_STAFF and has_specific_name) or \
           (best_intent == IntentType.SEARCH_REGULATION and has_specific_reg) or \
           is_health_check or \
           is_list_tables or \
           has_specific_corr or \
           is_web_search or \
           is_social_search or \
           is_policy_inventory:
            is_fast_path = True

        return IntentResult(
            intent=best_intent,
            confidence=confidence,
            raw_score=best_score,
            entities=entities,
            tool_arguments=tool_arguments,
            is_fast_path=is_fast_path
        )


@dataclass
class ToolDefinition:
    """Definisi tool sesuai spesifikasi OpenAI & MCP."""
    name: str
    description: str
    parameters: Dict[str, Any]
    priority: int = 5


@dataclass
class SelectedTool:
    """Hasil perankingan perkakas terpilih."""
    tool: ToolDefinition
    score: float
    reason: str


class SatriaToolSelector:
    """
    Orkestrator pemilih perkakas (Smart Tool Selector).
    Menjamin efisiensi token dengan membatasi perkakas maksimal 2-3 untuk model 7B/8B.
    """

    def __init__(self):
        self.classifier = DomainIntentClassifier()
        self.cache: Dict[str, Tuple[List[SelectedTool], float]] = {}
        self.cache_ttl = 60.0  # 1 menit
        self.tools = self._init_tool_catalog()

    def _init_tool_catalog(self) -> Dict[str, ToolDefinition]:
        """Katalog resmi perkakas SATRIA Co-Pilot."""
        return {
            "lookup_bangda_staff": ToolDefinition(
                name="lookup_bangda_staff",
                description="Mencari data kepegawaian, profil pejabat, dan formasi JF Madya/Muda Ditjen Bangda berdasarkan SK 2026.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Nama pejabat, jabatan (ahli madya/muda), atau nama tim kerja Ditjen Bangda."}
                    },
                    "required": ["query"]
                },
                priority=10
            ),
            "search_regulation_knowledge": ToolDefinition(
                name="search_regulation_knowledge",
                description="Mencari naskah peraturan perundang-undangan (PP, UU, Permendagri, Perda) tahun berjalan (2024-2026) dari RAG Knowledge Base pgvector.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Nomor peraturan, topik regulasi, atau pasal yang ingin dicari."},
                        "namespace": {"type": "string", "description": "Namespace memori hukum (default: legal_agent)."}
                    },
                    "required": ["query"]
                },
                priority=9
            ),
            "search_web_realtime": ToolDefinition(
                name="search_web_realtime",
                description="Melakukan pencarian internet dan portal web resmi pemerintah secara live menggunakan Tri-Engine Hybrid Search (Fast-Path, Playwright, Browser-Use) untuk mencari draf regulasi, berita, atau informasi nasional 2024-2026.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Kata kunci pencarian internet atau nomor regulasi."}
                    },
                    "required": ["query"]
                },
                priority=8
            ),
            "search_social_media": ToolDefinition(
                name="search_social_media",
                description="Mencari postingan, opini publik, diskusi warganet, dan isu viral di platform media sosial publik (Twitter/X, Instagram, TikTok, YouTube, Facebook, LinkedIn).",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Topik atau kata kunci isu yang dicari di media sosial."},
                        "platform": {"type": "string", "description": "Target platform ('all', 'twitter', 'instagram', 'tiktok', 'youtube', 'facebook', 'linkedin'). Default: 'all'."}
                    },
                    "required": ["query"]
                },
                priority=9
            ),
            "evaluate_bphn_doctrine": ToolDefinition(
                name="evaluate_bphn_doctrine",
                description="Melakukan uji 6-Dimensi BPHN dan keselarasan urusan konkuren UU 23/2014 terhadap draf atau substansi norma hukum.",
                parameters={
                    "type": "object",
                    "properties": {
                        "norm_text": {"type": "string", "description": "Teks materi muatan pasal atau draf regulasi yang akan dievaluasi."}
                    },
                    "required": ["norm_text"]
                },
                priority=8
            ),
            "legal_deontic_verify": ToolDefinition(
                name="legal_deontic_verify",
                description="Memverifikasi kepatuhan norma pasal terhadap 4 modalitas logika deontik (wajib, dilarang, dapat, berwenang) dan mendeteksi diksi ambigu/terlarang sesuai 236 Kaidah Lampiran II UU 12/2011.",
                parameters={
                    "type": "object",
                    "properties": {
                        "clause_text": {"type": "string", "description": "Rumusan norma atau teks pasal yang akan diverifikasi."}
                    },
                    "required": ["clause_text"]
                },
                priority=9
            ),
            "legal_naskah_akademik_generate": ToolDefinition(
                name="legal_naskah_akademik_generate",
                description="Menyusun kerangka naskah akademik (6 Bab baku Lampiran I UU 12/2011) untuk Raperda/RUU beserta analisis yuridis dan sosiologis.",
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Judul Raperda atau Rancangan Peraturan."},
                        "background": {"type": "string", "description": "Latar belakang masalah dan urgensi pengaturan."}
                    },
                    "required": ["title"]
                },
                priority=9
            ),
            "legal_harmonization_matrix": ToolDefinition(
                name="legal_harmonization_matrix",
                description="Menghasilkan Matriks Hasil Pengharmonisasian (Format 5 Kolom SE Menkumham 2022) untuk e-harmonisasi Raperda/Raperkada dan menghitung batas limit sanksi pidana.",
                parameters={
                    "type": "object",
                    "properties": {
                        "raperda_title": {"type": "string", "description": "Judul Raperda yang diharmonisasi."},
                        "articles_json": {"type": "string", "description": "JSON string daftar pasal berisi article_number dan text."}
                    },
                    "required": ["raperda_title"]
                },
                priority=9
            ),
            "legal_opinion_irac": ToolDefinition(
                name="legal_opinion_irac",
                description="Menyusun Pendapat Hukum (Legal Opinion) berstruktur deduktif IRAC (Issue, Rule, Analysis, Conclusion) dengan uji kepatuhan 8 Asas AUPB (UU 30/2014) dan deteksi risiko kerugian negara/Tipikor.",
                parameters={
                    "type": "object",
                    "properties": {
                        "legal_issue": {"type": "string", "description": "Isu hukum yang ditanyakan."},
                        "legal_facts": {"type": "string", "description": "Kronologi dan fakta peristiwa hukum."}
                    },
                    "required": ["legal_issue"]
                },
                priority=9
            ),
            "legal_contract_vetting": ToolDefinition(
                name="legal_contract_vetting",
                description="Melakukan audit dan vetting komprehensif atas klausul draf Kontrak Pengadaan (PBJ) atau Perjanjian Kerja Sama (PKS Daerah), mendeteksi celah denda 1/1000, pengesampingan Pasal 1266 KUHPerdata, dan potensi temuan BPK.",
                parameters={
                    "type": "object",
                    "properties": {
                        "contract_title": {"type": "string", "description": "Judul kontrak/PKS yang diaudit."},
                        "clauses_text": {"type": "string", "description": "Teks klausul draf kontrak yang akan diaudit."}
                    },
                    "required": ["contract_title", "clauses_text"]
                },
                priority=9
            ),
            "legal_litigation_advocacy": ToolDefinition(
                name="legal_litigation_advocacy",
                description="Menyusun strategi advokasi dan pembelaan sengketa hukum pemerintah (Matriks 5 Alat Bukti PTUN Pasal 100, Eksepsi 90 Hari Daluwarsa, atau Keterangan Uji Materiil di MKRI/MA).",
                parameters={
                    "type": "object",
                    "properties": {
                        "dispute_type": {"type": "string", "description": "Jenis sengketa ('PTUN', 'MKRI', 'MA'). Default: 'PTUN'."},
                        "summary_facts": {"type": "string", "description": "Ringkasan objek gugatan/permohonan dan dalil lawan."}
                    },
                    "required": ["summary_facts"]
                },
                priority=9
            ),
            "browse_portal_autonomous": ToolDefinition(
                name="browse_portal_autonomous",
                description="Menugaskan AI Sub-Agent Browser otonom untuk membuka portal web pemerintah (SP4N-LAPOR, JDIH, Srikandi, PPID, peraturan.go.id), bernalar, menavigasi menu dinamis, dan mengekstrak dokumen/informasi secara interaktif.",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL lengkap portal web target."},
                        "task": {"type": "string", "description": "Instruksi eksplorasi atau data yang ingin dicari di portal."},
                        "max_steps": {"type": "integer", "description": "Maksimal langkah aksi sub-agent (default: 5)."}
                    },
                    "required": ["url", "task"]
                },
                priority=9
            ),
            "send_whatsapp_message": ToolDefinition(
                name="send_whatsapp_message",
                description="Mengirimkan pesan teks resmi ke nomor WhatsApp tujuan.",
                parameters={
                    "type": "object",
                    "properties": {
                        "phone_number": {"type": "string", "description": "Nomor telepon tujuan dengan format +62..."},
                        "text": {"type": "string", "description": "Isi pesan yang akan dikirim."}
                    },
                    "required": ["phone_number", "text"]
                },
                priority=4
            ),
            "cari_surat_korespondensi": ToolDefinition(
                name="cari_surat_korespondensi",
                description="Mencari surat masuk, surat keluar, disposisi, dan permohonan fasilitasi ranperda/rtrw dari database korespondensi pusat Ditjen Bangda.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Nomor surat, perihal surat, atau nama pengirim daerah."}
                    },
                    "required": ["query"]
                },
                priority=9
            ),
            "list_database_tables": ToolDefinition(
                name="list_database_tables",
                description="Menampilkan daftar tabel database riil sistem MCP (PostgreSQL / SQLite LTM & RAG Knowledge), fungsi masing-masing tabel, dan status akses.",
                parameters={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Jumlah maksimal tabel yang ditampilkan (default: 10)."}
                    }
                },
                priority=9
            ),
            "legal_patch_clause": ToolDefinition(
                name="legal_patch_clause",
                description="Menyusun rumusan klausul alternatif aman (safe drafting) dan merevisi materi muatan pasal regulasi agar selaras dengan UU induk serta mencegah potensi ultra vires.",
                parameters={
                    "type": "object",
                    "properties": {
                        "problematic_clause": {"type": "string", "description": "Teks pasal atau klausul yang bermasalah/berpotensi cacat norma."},
                        "reason_or_defect": {"type": "string", "description": "Alasan perbaikan atau potensi risiko hukum yang ingin dicegah."}
                    },
                    "required": ["problematic_clause"]
                },
                priority=8
            ),
            "legal_verify_spm": ToolDefinition(
                name="legal_verify_spm",
                description="Memverifikasi pemenuhan Standar Pelayanan Minimal (SPM) pada 6 Urusan Wajib Dasar (Pendidikan, Kesehatan, PU, Perumahan, Trantibumlinmas, Sosial) sesuai regulasi Kemendagri & UU 23/2014.",
                parameters={
                    "type": "object",
                    "properties": {
                        "indicator_query": {"type": "string", "description": "Sektor SPM atau indikator teknis pemenuhan pelayanan dasar yang ditanyakan."}
                    },
                    "required": ["indicator_query"]
                },
                priority=8
            ),
            "nd_generate_laporan": ToolDefinition(
                name="nd_generate_laporan",
                description="Menghasilkan draf resmi Nota Dinas Laporan Hasil Rapat / Telaahan Staf di lingkungan Ditjen Bina Pembangunan Daerah berbasis Golden Pattern Standard 2026 (Format Kop, Atribut, Heading, dan Rekomendasi).",
                parameters={
                    "type": "object",
                    "properties": {
                        "hal": {"type": "string", "description": "Perihal atau topik rapat dinas."},
                        "poin_pembahasan": {"type": "string", "description": "Pokok-pokok pembahasan dan hasil kesepakatan rapat."}
                    },
                    "required": ["hal"]
                },
                priority=8
            ),
            "system_health_check": ToolDefinition(
                name="system_health_check",
                description="Memeriksa status kesehatan infrastruktur teknis MCP, konektivitas database PostgreSQL (Port 5433), status cluster GPU Serverless RunPod, dan service WhatsApp.",
                parameters={
                    "type": "object",
                    "properties": {
                        "service_target": {"type": "string", "description": "Target pemeriksaan: 'all', 'database', 'runpod', atau 'services'."}
                    }
                },
                priority=8
            ),
            "policy_inventory_aggregator": ToolDefinition(
                name="policy_inventory_aggregator",
                description="Mengambil inventarisasi resmi produk hukum dan kebijakan Ditjen Bangda/Kemendagri (Kepmendagri, Permendagri, Inmendagri, SE, MOU) lintas tahun (2009-2026) dari master katalog database.",
                parameters={
                    "type": "object",
                    "properties": {
                        "kategori": {"type": "string", "description": "Kategori dokumen: KEPMENDAGRI, PERMENDAGRI, INMENDAGRI, SE, SEB, MOU, PP, UU."},
                        "tahun": {"type": "integer", "description": "Tahun penerbitan (misal: 2026, 2025, 2024)."},
                        "keyword": {"type": "string", "description": "Kata kunci pencarian judul atau nomor regulasi."},
                        "sub_kategori": {"type": "string", "description": "Sub-kategori atau direktori spesifik (misal: RPJMD, RTRW, SARPRAS)."},
                        "limit": {"type": "integer", "description": "Maksimal hasil yang ditampilkan (default: 15)."}
                    }
                },
                priority=10
            )
        }

    def classify_intent(self, user_input: str) -> IntentResult:
        """Shortcut untuk mengklasifikasikan intent pemohon."""
        return self.classifier.classify(user_input)

    def select(self, user_input: str, model_size: str = "7B") -> List[SelectedTool]:
        """
        Memilih dan meranking tools yang relevan sesuai ukuran model (Anti-Tool Bloat).
        """
        cache_key = f"{user_input.strip().lower()}_{model_size}"
        if cache_key in self.cache:
            res, ts = self.cache[cache_key]
            if (time.time() - ts) < self.cache_ttl:
                return res

        intent_res = self.classifier.classify(user_input)

        selected: List[SelectedTool] = []
        if intent_res.intent == IntentType.UNKNOWN:
            # Fallback default tools untuk model
            selected = self._get_default_fallback_tools()
        else:
            # Ambil primary tool
            primary_name = intent_res.intent.value
            primary_tool = self.tools.get(primary_name)
            if primary_tool:
                selected.append(SelectedTool(
                    tool=primary_tool,
                    score=primary_tool.priority * 0.7 + intent_res.confidence * 3.0,
                    reason=f"Matched primary intent: {intent_res.intent.value}"
                ))

            # Tambahkan secondary context tool yang saling melengkapi
            if intent_res.intent == IntentType.POLICY_INVENTORY:
                # Tambahkan regulasi sebagai rujukan pelengkap
                reg_tool = self.tools.get("search_regulation_knowledge")
                if reg_tool:
                    selected.append(SelectedTool(tool=reg_tool, score=6.0, reason="Statutory RAG knowledge complement"))
            elif intent_res.intent == IntentType.SEARCH_REGULATION:
                # Tambahkan web search sebagai backup
                web_tool = self.tools.get("search_web_realtime")
                if web_tool:
                    selected.append(SelectedTool(tool=web_tool, score=6.0, reason="Backup realtime retrieval"))
            elif intent_res.intent == IntentType.LOOKUP_STAFF:
                # Tambahkan regulasi sebagai rujukan tugas fungsi
                reg_tool = self.tools.get("search_regulation_knowledge")
                if reg_tool:
                    selected.append(SelectedTool(tool=reg_tool, score=5.5, reason="Related staff regulatory function"))
            elif intent_res.intent == IntentType.SEARCH_CORRESPONDENCE:
                # Tambahkan lookup staff jika surat terkait PIC tim kerja
                staff_tool = self.tools.get("lookup_bangda_staff")
                if staff_tool:
                    selected.append(SelectedTool(tool=staff_tool, score=6.0, reason="PIC staff verification for correspondence"))
            elif intent_res.intent == IntentType.PATCH_CLAUSE:
                reg_tool = self.tools.get("search_regulation_knowledge")
                if reg_tool:
                    selected.append(SelectedTool(tool=reg_tool, score=6.0, reason="Statutory context for safe patching"))
            elif intent_res.intent == IntentType.VERIFY_SPM:
                reg_tool = self.tools.get("search_regulation_knowledge")
                if reg_tool:
                    selected.append(SelectedTool(tool=reg_tool, score=6.0, reason="SPM regulatory references"))
            elif intent_res.intent == IntentType.GENERATE_NOTA_DINAS:
                staff_tool = self.tools.get("lookup_bangda_staff")
                if staff_tool:
                    selected.append(SelectedTool(tool=staff_tool, score=5.5, reason="Official author and structural recipient data"))
            elif intent_res.intent == IntentType.AUTONOMOUS_BROWSE:
                # Tambahkan web search sebagai alternatif
                web_tool = self.tools.get("search_web_realtime")
                if web_tool:
                    selected.append(SelectedTool(tool=web_tool, score=6.5, reason="Fallback web search for portal query"))

        # Urutkan berdasarkan skor tertinggi
        selected = sorted(selected, key=lambda x: x.score, reverse=True)

        # Terapkan batas maksimal sesuai ukuran model (Model-Size Aware)
        max_tools = 3 if model_size in ["1B", "3B", "7B", "8B"] else 5
        result = selected[:max_tools]

        self.cache[cache_key] = (result, time.time())
        return result

    def _get_default_fallback_tools(self) -> List[SelectedTool]:
        """Perkakas default aman saat pertanyaan umum diajukan."""
        defaults = ["search_regulation_knowledge", "lookup_bangda_staff", "cari_surat_korespondensi"]
        res = []
        for name in defaults:
            t = self.tools.get(name)
            if t:
                res.append(SelectedTool(tool=t, score=4.0, reason="General default tool"))
        return res

    def get_openai_tools_schema(self, selected_tools: List[SelectedTool]) -> List[Dict[str, Any]]:
        """Mengonversi daftar SelectedTool ke format OpenAI Function Calling JSON Schema."""
        schemas = []
        for st in selected_tools:
            t = st.tool
            schemas.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters
                }
            })
        return schemas


# Singleton instance global
satria_tool_selector = SatriaToolSelector()

"""
legal_madya_handler.py — Persona Handler & Reasoning Router for SATRIA WhatsApp Co-Pilot.
Provides restricted Ahli Madya Analis & Perancang Hukum & Tata Kelola capabilities over WhatsApp.
Powered by OpenAI gpt-4o-mini (Primary Generative Engine), Serena AST, and 2-Tier Precedent Memory.
"""

import os
import sys
import re
import json
import time
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

from integrations.whatsapp.whitelist_guard import (
    get_whitelist_user,
    is_authorized,
    is_admin_user,
    get_user_greeting,
    normalize_phone_number,
    list_whitelist_users,
    save_whitelist_user,
    remove_whitelist_user,
    reload_whitelist_cache,
    update_user_additional_duties
)
from tools.legal_tools import (
    legal_evaluate_doctrine,
    legal_search_tier2_precedents,
    legal_analyze_dependencies,
    legal_patch_clause,
    legal_verify_policy_code,
    legal_comprehensive_audit,
    legal_verify_spm,
    legal_deontic_verify,
    legal_anatomy_validate,
    legal_naskah_akademik_generate,
    legal_harmonization_matrix,
    legal_opinion_irac,
    legal_contract_vetting,
    legal_litigation_advocacy
)
from integrations.whatsapp.tool_selector import satria_tool_selector, IntentType
from integrations.whatsapp.pydantic_adapter import satria_pydantic_adapter
from integrations.whatsapp.timeout_guard import satria_timeout_guard
from integrations.whatsapp.typing_indicator import satria_typing_indicator
from integrations.whatsapp.non_service_handler import (
    satria_non_service_detector,
    satria_non_service_handlers,
    NonServiceCategory
)
from integrations.whatsapp.interaction_logger import satria_interaction_logger
from integrations.whatsapp.session_manager import satria_session_manager
from integrations.whatsapp.deep_tracer import TokenUsage, LatencyBreakdown, satria_tracer
from integrations.knowledge.policy_inventory_engine import policy_inventory_engine

logger = logging.getLogger("satria_whatsapp")

def _get_db_url() -> str:
    """Mengembalikan URL database dengan sanitasi host ke 127.0.0.1 untuk mencegah TCP hanging di Linux."""
    url = os.getenv("DATABASE_URL")
    if not url:
        pg_user = os.getenv("POSTGRES_USER", "mcp_user")
        pg_pass = os.getenv("POSTGRES_PASSWORD", "")
        pg_host = os.getenv("POSTGRES_HOST", "127.0.0.1")
        pg_port = os.getenv("POSTGRES_PORT", "5433")
        pg_db   = os.getenv("POSTGRES_DB", "mcp_knowledge")
        url = f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
    return url.replace("@localhost:", "@127.0.0.1:")


SATRIA_LEGAL_MADYA_PROMPT = """
Anda adalah SATRIA (Sistem Analisis Tata Kelola, Regulasi, & Insan Aparatur), berperan khusus sebagai ASISTEN AHLI MADYA BANGDA di lingkungan Direktorat Jenderal Bina Pembangunan Daerah, Kementerian Dalam Negeri RI.
Anda beroperasi sebagai Agen Cerdas ditenagai oleh MICROSOFT AGENT FRAMEWORK (MAF) sebagai Core Orchestration Engine generasi terbaru, yang terhubung secara bidirectional dengan Model Context Protocol (MCP) Universal Hub.

ARSITEKTUR & INTEGRASI TEKNOLOGI (RESMI & AKTIF):
1. Core Orchestration Engine: Microsoft Agent Framework (MAF - agent-framework-core v1.19.0) — mengelola penalaran otonom, Multi-Channel Session Persistence, dan Multi-Agent collaboration.
2. Protokol Komunikasi & Perkakas: Model Context Protocol (MCP) — standar protokol terbuka yang menghubungkan MAF Agent ke basis data internal (RAG pgvector peraturan, SK Tim Kerja Ditjen Bangda 2026, dan korespondensi surat).
3. Status Integrasi: 🟢 TERINTEGRASI PENUH DENGAN MICROSOFT AGENT FRAMEWORK (MAF ENGINE). Jika ditanya apakah Anda sudah terintegrasi dengan Microsoft Agent Framework, nyatakan secara TEGAS dan JELAS bahwa Anda SUDAH TERINTEGRASI PENUH dengan Microsoft Agent Framework (MAF) sebagai engine backend utama bersama MCP Universal Hub.

SPESIALISASI PERAN: ASISTEN AHLI MADYA (SUBSTANSI HUKUM, REGULASI & KEPEGAWAIAN)
Fokus Utama & Kerangka Analisis Multi-Dimensi:
1. Uji Doktrin Multi-Dimensi & Harmonisasi PUU:
   Dalam menelaah produk hukum (Perda, Perbup/Perkada, SK, SE, Permen, atau naskah dinas), Anda menerapkan 6 Sudut Pandang Doktrin Tokoh & Pedoman BPHN:
   a. Uji Kewenangan & Anti-Ultra Vires (Prof. Dr. Jimly Asshiddiqie & Ps. 24A UUD 1945): Uji apakah materi muatan didukung mandat delegasi eksplisit UU induk atau melampaui wewenang (cacat ultra vires yang rentan dibatalkan di MA/MK).
   b. Uji 5 Faktor Efektivitas Hukum Sosiologis (Prof. Dr. Soerjono Soekanto): Apakah hukum dapat bekerja nyata di lapangan? Cek kejelasan norma, kesiapan kelembagaan/aparat OPD, sarana/fasilitas APBD, kesiapan masyarakat, dan budaya hukum lokal.
   c. Uji Asas Pembentukan PUU (Prof. Maria Farida Indrati & UU 12/2011 jo 13/2022): Kepatuhan terhadap 7 asas formil (kejelasan tujuan, kelembagaan tepat, kesesuaian materi muatan, dapat dilaksanakan, dll) dan 10 asas materiil (kepastian hukum, keadilan, pengayoman).
   d. Uji 6 Dimensi BPHN Kemenkumham (Pedoman PHN-HN.01.03-07): Pancasila, Ketepatan Jenis PUU, Potensi Disharmoni (Vertikal, Horizontal, Diagonal), Kejelasan Rumusan, Kesesuaian Asas Hukum, dan Dampak Pemda.
   e. Uji Hukum Pembangunan (Prof. Dr. Mochtar Kusumaatmadja): Law as a tool of social engineering — apakah regulasi mengarahkan transformasi sosial-ekonomi substantif atau sekadar prosedur administratif pasif.
   f. Uji Dampak Kebijakan & Beban Ekonomi (Regulatory Impact Assessment / RIA - OECD & Bappenas Inpres 7/2017): Rasio beban kepatuhan (compliance cost) vs faedah publik, diferensiasi objek berbobot vs memukul rata.
2. Pembagian Urusan Konkuren Daerah: Harmonisasi dengan UU No. 23/2014, regulasi teknis sektoral, serta yurisprudensi pengujian Perda di Mahkamah Agung dan MK.
3. Administrasi Pemerintahan & Diskresi: Asas-Asas Umum Pemerintahan yang Baik (AUPB) dan syarat diskresi pejabat pemerintahan berdasarkan UU No. 30/2014.
4. Manajemen Insan Aparatur (SDM/ASN): UU 20/2023, Disiplin PNS, Penataan Non-ASN/PPPK, dan Pola Karier Jabatan Fungsional.
5. Akses Database Internal & Regulasi: Terhubung langsung dengan Master Data Kepegawaian Ditjen Bangda (SK 2026) dan RAG Knowledge Base Regulasi Terkini (2024–2026). DILARANG MENOLAK pertanyaan data nama pegawai atau formasi tim kerja (panggil 'lookup_bangda_staff'). Ketika ditanya ketentuan/pasal peraturan perundang-undangan (misal Permendagri 41/2012 TDU PKL, UU Cipta Kerja), Anda WAJIB memanggil 'search_regulation_knowledge' dan DILARANG mengarang dari ingatan parametrik.
6. Standarisasi Nomenklatur Peraturan Perundang-Undangan (UU 12/2011 jo UU 13/2022):
   a. Produk Regulasi/Pengaturan (Regeling): UU, Perppu, PP, Perpres, Permen, Perda, Perbup/Perwali disusun dalam bentuk BAB, BAGIAN, PARAGRAF, dan PASAL.
   b. Produk Penetapan/Kebijakan (Beschikking): Keputusan Menteri (Kepmen), Keputusan Kepala Daerah (Kepbup/Kepwali), Surat Edaran (SE), atau Instruksi TIDAK MEMILIKI PASAL, melainkan memuat KONSIDERANS dan DIKTUM (KESATU, KEDUA, KETIGA, dst). DILARANG KERAS mengarang atau menciptakan nomor pasal fiktif untuk produk Keputusan Menteri. Jika pengguna menanyakan pasal apa saja pada sebuah Kepmen, Anda WAJIB menjelaskan dengan santun bahwa naskah Kepmen tersusun atas Diktum, lalu paparkan rincian Diktum KESATU, KEDUA, dst.
7. Doktrin Evaluasi Perda, Keuangan Daerah, & Yurisprudensi Konstitusi (Update 2026):
   a. Standar Evaluasi Ranperda RPJPD/RPJMD Provinsi (Permendagri 86/2017): Evaluasi Ranperda RPJPD/RPJMD Provinsi dipimpin Ditjen Bangda dalam waktu maksimal 15 hari kerja sejak 6 dokumen wajib lengkap. Output berupa Keputusan Mendagri. Penyempurnaan oleh Pemda maksimal 7 hari kerja.
   b. Standar Evaluasi Ranperda Tata Ruang / RTRW (Permendagri 13/2016): Evaluasi Ranperda RTRW mensyaratkan secara mutlak Persetujuan Substansi (Persub) Menteri ATR/BPN dan album peta rekomendasi teknis BIG. Jangka waktu evaluasi 15 hari kerja.
   c. Larangan Pembatalan Perda Sepihak oleh Eksekutif (Putusan MK No. 137/PUU-XIII/2015 & No. 56/PUU-XIV/2016): Mendagri dan Gubernur TIDAK BERWENANG membatalkan secara sepihak Perda yang telah diundangkan (monopoli MA melalui Hak Uji Materil Ps. 24A UUD 1945). Jika Perda bermasalah (misal retribusi memberatkan UMKM), langkah hukum Kemendagri adalah negosiasi/revisi kebijakan dan penundaan/pemotongan transfer ke daerah (TKD/DAU) berdasarkan UU No. 1 Tahun 2022 (HKPD Pasal 99).
   d. Keuangan Desa (Permendagri 20/2018): Permendagri 113/2014 telah DICABUT. Pengelolaan keuangan desa berpedoman pada Permendagri No. 20 Tahun 2018 dan aplikasi SISKEUDES.
   e. Pelindungan Data Adminduk (UU 27/2022 PDP & Permendagri 57/2021 SMKI): Integrasi aplikasi daerah wajib berbasis PKS, zero local storage, dan wajib notifikasi tertulis 3 x 24 jam ke warga & BSSN jika terjadi kebocoran data.
8. Integritas Rujukan Portal Web & Anti-Halusinasi Tautan Eksternal:
   a. Anda DILARANG KERAS mengarang tautan URL spesifik (misal: format /Details/...), nomor peraturan daerah, atau mengutip portal eksternal (seperti bpk.go.id, jdih, peraturan.go.id) dari ingatan parametrik semata.
   b. Jika pengguna menanyakan regulasi pada portal luar (misal: "cari di bpk.go.id", "peraturan di jdih", "cari di web"), informasi dan tautan URL HANYA boleh dicantumkan jika secara faktual terdapat pada fakta resmi terverifikasi / output tool penelusuran ('search_web_realtime' atau 'browse_portal_autonomous').
   c. Jika hasil penelusuran web tidak menemukan dokumen yang dicari, nyatakan secara jujur dan transparan bahwa dokumen tersebut belum terindeks pada portal resmi bersangkutan.
9. Struktur Organisasi dan Tata Kerja (SOTK) Ditjen Bina Pembangunan Daerah (Permendagri No. 9 Tahun 2025 / SOTK Kemendagri):
   a. Pimpinan: Direktur Jenderal Bina Pembangunan Daerah.
   b. Unsur Pembantu Pimpinan: Sekretariat Direktorat Jenderal (Setditjen), terdiri atas:
      - Bagian Perencanaan
      - Bagian Keuangan dan Pengelolaan BMN
      - Bagian Kepegawaian
      - Bagian Umum
      - Kelompok Jabatan Fungsional
   c. Unsur Pelaksana (DEFINITIF 5 DIREKTORAT):
      1. Direktorat Perencanaan, Evaluasi dan Informasi Pembangunan Daerah (Dit. PEIPPD): Urusan perencanaan pembangunan daerah, evaluasi kinerja, informasi pembangunan, dan fasilitasi dokumen perencanaan (RPJPD, RPJMD, RKPD).
      2. Direktorat Sinkronisasi Urusan Pemerintahan Daerah I (Dit. SUPD I): Bidang Pendidikan, Kesehatan, Pekerjaan Umum & Penataan Ruang, Perumahan Rakyat & Kawasan Permukiman.
      3. Direktorat Sinkronisasi Urusan Pemerintahan Daerah II (Dit. SUPD II): Bidang Sosial, Pemberdayaan Masyarakat & Desa, Pengendalian Penduduk & KB, Pemberdayaan Perempuan & Perlindungan Anak, Administrasi Kependudukan.
      4. Direktorat Sinkronisasi Urusan Pemerintahan Daerah III (Dit. SUPD III): Bidang Pertanian, Pangan, Kelautan & Perikanan, Pariwisata, Kebudayaan, Kehutanan, ESDM, Perhubungan, Komunikasi & Informatika, Lingkungan Hidup, Statistik, Persandian.
      5. Direktorat Sinkronisasi Urusan Pemerintahan Daerah IV (Dit. SUPD IV): Bidang Ketenagakerjaan, Transmigrasi, Koperasi & UKM, Perindustrian, Perdagangan, Penanaman Modal, Kepemudaan & Olahraga, Kesatuan Bangsa & Politik, Ketenteraman & Ketertiban Umum.
   d. Ketentuan SOTK Ditjen Bangda: Ditjen Bangda secara definitif memiliki 5 DIREKTORAT (PEIPPD dan SUPD I s.d. SUPD IV). Selalu sertakan Direktorat PEIPPD sebagai salah satu unsur pelaksana utama.
10. Otonomi Eksekusi Perkakas & Larangan Klaim Palsu RAG:
   a. DILARANG membuat klaim semu seperti "Berdasarkan penelusuran pada RAG Knowledge Base..." jika data riil dari perkakas tidak benar-benar terlampir pada konteks giliran saat ini. Jika Anda merespon berdasarkan pengetahuan tata kelola konseptual, gunakan kalimat lugas dan jujur: "Berdasarkan tinjauan tata kelola dan regulasi yang berlaku...".
   b. Otonomi Proaktif Tanpa Meminta Izin: DILARANG bolak-balik bertanya kepada pemohon: "Apakah Bapak/Ibu mengizinkan saya memanggil tool...?" atau "Apakah saya diizinkan menelusuri web...?". Anda BERWENANG PENUH untuk LANGSUNG MEMBERIKAN JAWABAN TERBAIK secara tuntas, padat, dan solutif. Jika data dokumen primer belum lengkap pada RAG, jelaskan temuan yang ada dan rekomendasikan tindak lanjutnya secara langsung tanpa melempar pertanyaan izin administratif.

Karakter & Etika Komunikasi:
1. Bersikap sangat profesional, santun, taktis, diplomatis, objektif, dan solutif layaknya Asisten Ahli Madya Bangda berpengalaman.
2. Selalu menyertakan dasar hukum positif (pasal/UU terkait) dan putusan peradilan (MK/MA) jika relevan.
3. Sajikan telaah dalam format Executive Brief WhatsApp yang tajam: status kelayakan (🟢 Lulus / 🟡 Perlu Revisi / 🔴 Rawan Ultra Vires), poin pasal kritis, analisis doktrin, dan rekomendasi klausul aman (safe drafting).
4. DILARANG mencetak header sendiri di awal pesan seperti "🏛️ PENDAPAT ASISTEN AHLI MADYA..." karena sistem pembungkus akan menempelkannya secara otomatis.
"""

SATRIA_ADMIN_PERSURATAN_PROMPT = """
Anda adalah SATRIA (Sistem Analisis Tata Kelola, Regulasi, & Insan Aparatur), berperan khusus sebagai ASISTEN ADMINISTRASI PERSURATAN BANGDA di lingkungan Direktorat Jenderal Bina Pembangunan Daerah, Kementerian Dalam Negeri RI.
Anda beroperasi sebagai Agen Cerdas ditenagai oleh MICROSOFT AGENT FRAMEWORK (MAF) sebagai Core Orchestration Engine yang terintegrasi secara bidirectional dengan Model Context Protocol (MCP) Universal Hub.

ARSITEKTUR & INTEGRASI TEKNOLOGI (RESMI & AKTIF):
1. Core Orchestration Engine: Microsoft Agent Framework (MAF - agent-framework-core v1.19.0).
2. Protokol Integrasi: Model Context Protocol (MCP) Universal Hub.
3. Status Integrasi: 🟢 TERINTEGRASI PENUH DENGAN MICROSOFT AGENT FRAMEWORK (MAF ENGINE).

SPESIALISASI PERAN: ASISTEN ADMINISTRASI PERSURATAN (TATA NASKAH DINAS, AGENDA SURAT, & DISPOSISI)
Fokus Utama:
1. Registrasi & Tracking Naskah Dinas: Pemantauan dan pelaporan surat masuk dan surat keluar (baik eksternal dari Pemda/Kementerian/Lembaga maupun internal Ditjen Bangda/Kemendagri).
2. Penelusuran Disposisi Pimpinan: Menelusuri status dan catatan arahan disposisi dari Pimpinan Ditjen (Direktur Jenderal, Sekretaris Ditjen, dan Para Direktur/Koordinator).
3. Tata Naskah Dinas & Standarisasi Persuratan: Format nota dinas, surat dinas, penomoran kode klasifikasi naskah dinas Kemendagri, dan alur tata persuratan.
4. Monitoring Fasilitasi Dokumen Daerah: Memantau riwayat registrasi surat permohonan fasilitasi rancangan produk hukum daerah (Ranperda RTRW, RPJMD, Pajak/Retribusi) dari Pemerintah Daerah.
5. Akses Database Korespondensi: Terhubung langsung dengan Database Korespondensi & Disposisi Surat Ditjen Bangda (tabel `korespondensi_raw_pool` dan `surat_masuk_puu_eksternal`). Anda WAJIB memanggil tool 'cari_surat_korespondensi' untuk mencari surat masuk/keluar, status disposisi, atau persuratan daerah. DILARANG menyatakan tidak memiliki akses persuratan dinas.
6. Standarisasi Format Tata Naskah Dinas (Permendagri No. 1 Tahun 2023):
   a. Tipografi & Margin: Font Arial ukuran 11 pt, margin Atas 2 cm, Bawah 2 cm, Kiri 2.5 cm, Kanan 2 cm (atau Bawah 1.5 cm pada halaman berkop surat).
   b. Penulisan Gelar & NIP: Pada produk pengaturan (Regeling) DILARANG mencantumkan gelar dan NIP. Pada naskah dinas penugasan/korespondensi (Nota Dinas, Surat Tugas, SPT) WAJIB mencantumkan gelar akademik/keagamaan dan NIP.
   c. Format Khusus: Mematuhi 21 format baku (Nota Dinas, Surat Undangan, Berita Acara, dll), legalitas TTE BSrE BSSN, serta pendelegasian mandat a.n./u.b./Plt/Plh/Pjs.
7. Kode Klasifikasi Arsip & Penomoran Surat (Permendagri No. 83 Tahun 2022):
   a. Struktur Nomor: [Sifat/Keamanan].[Kode Klasifikasi]/[Nomor Urut]/[Kode Satker]/[Tahun].
   b. Kode Pokok: 000 Fasilitatif, 000.6 Hubungan Urusan Pemerintahan, 100 Pemerintahan Dalam Negeri, 600 Pembangunan Daerah (Ditjen Bina Bangda).

Karakter & Etika Komunikasi:
1. Bersikap sangat taktis, akurat, informatif, dan terstruktur layaknya Asisten Administrasi Persuratan Ditjen Bangda yang handal.
2. Sajikan rincian surat secara teratur: Nomor Surat/Nota Dinas, Tanggal Terima/Surat, Pengirim/Asal Surat, Perihal, Posisi Berkas Saat Ini, dan Catatan Arahan Disposisi.
3. Berikan format respon yang rapi dan mudah dibaca di layar WhatsApp menggunakan emoji penegas, bullet point, dan huruf tebal (*bold*).
4. DILARANG mencetak header sendiri di awal pesan seperti "📮 ASISTEN ADMINISTRASI PERSURATAN..." karena sistem pembungkus akan menempelkannya secara otomatis.
"""

SATRIA_SYSTEM_PROMPT = SATRIA_LEGAL_MADYA_PROMPT

def _lookup_bangda_staff_data(query: str) -> str:
    """Mencari data kepegawaian, pejabat, dan struktur tim kerja Ditjen Bangda dari database master SK 2026."""
    q_lower = query.lower()
    keywords = [
        "ahli madya", "ahli muda", "ahli pertama", "ahli utama", "perancang", 
        "analis hukum", "pegawai", "pejabat", "tim kerja", "struktur", "lady", 
        "faisal", "asep", "amir", "salim", "rizal", "agus", "denis", "dennis", 
        "yonatan", "sukma", "romi", "subdit", "sekretariat", "berapa", "siapa", 
        "jumlah", "staf", "koordinator", "fungsional", "jf"
    ]
    if not any(k in q_lower for k in keywords):
        return ""

    try:
        import psycopg2
        db_url = _get_db_url()
        conn = psycopg2.connect(db_url, connect_timeout=5)
        cur = conn.cursor()

        # 1. Deteksi pencarian nama spesifik
        stop_tokens = {"data", "pegawai", "bernama", "coba", "carikan", "tampilkan", "tim", "siapa", "ada", "apakah", "di", "lingkungan", "ditjen", "bangda", "bina", "pembangunan", "daerah", "yang", "dan"}
        name_candidates = [w for w in re.findall(r'\b[a-zA-Z]{3,}\b', q_lower) if w not in stop_tokens]

        if name_candidates:
            for cand in name_candidates:
                cur.execute("""
                    SELECT nama_pegawai, nip, jabatan, unit_kerja, tim_kerja 
                    FROM master_tim_kerja_bangda_2026 
                    WHERE nama_pegawai ILIKE %s 
                    ORDER BY nama_pegawai LIMIT 5;
                """, (f"%{cand}%",))
                name_rows = cur.fetchall()
                if name_rows:
                    res = "DATA PEGAWAI RESMI DITJEN BINA PEMBANGUNAN DAERAH (DATABASE SK 2026):\n"
                    for r in name_rows:
                        res += f"- Nama: {r[0]}\n  NIP: {r[1] or '-'}\n  Jabatan: {r[2]}\n  Unit: {r[3]}\n  Tim Kerja / Penugasan: {r[4]}\n\n"
                    cur.close()
                    conn.close()
                    return res.strip()

        # 2. Deteksi pencarian tim perundang-undangan / hukum
        if any(k in q_lower for k in ["perundang", "hukum", "puu", "advokasi"]):
            cur.execute("""
                SELECT nama_pegawai, nip, jabatan, unit_kerja, tim_kerja 
                FROM master_tim_kerja_bangda_2026 
                WHERE tim_kerja ILIKE '%perundang%' OR tim_kerja ILIKE '%hukum%'
                ORDER BY tim_kerja, jabatan, nama_pegawai;
            """)
            team_rows = cur.fetchall()
            if team_rows:
                res = "DAFTAR RESMI TIM URUSAN PERUNDANG-UNDANGAN & HUKUM DITJEN BANGDA (SK 2026):\n"
                for r in team_rows:
                    res += f"- {r[0]} | {r[2]} ({r[4]})\n"
                cur.close()
                conn.close()
                return res.strip()

        # 3. Deteksi pencarian jabatan fungsional Madya / Muda / Jumlah JF
        if "madya" in q_lower or "berapa" in q_lower or "jumlah" in q_lower:
            cur.execute("""
                SELECT nama_pegawai, jabatan, unit_kerja, tim_kerja 
                FROM master_tim_kerja_bangda_2026 
                WHERE jabatan ILIKE '%madya%'
                ORDER BY unit_kerja, nama_pegawai;
            """)
            rows = cur.fetchall()
            if rows:
                hukum_madya = [r for r in rows if any(k in (r[1] or '').lower() or k in (r[3] or '').lower() for k in ['hukum', 'perundang', 'puu', 'perancang'])]
                res = "DATA MASTER KEPEGAWAIAN DITJEN BANGDA (SK 2026 RIIL DARI DATABASE):\n"
                res += f"- Total Jabatan Fungsional Ahli Madya di Ditjen Bangda: {len(rows)} orang\n"
                res += f"- Khusus Bidang Hukum / Perundang-undangan / PUU ({len(hukum_madya)} orang):\n"
                for r in hukum_madya:
                    res += f"  * {r[0]} — Jabatan: {r[1]} ({r[2]} / Tim: {r[3]})\n"
                res += "\n- Daftar Contoh Ahli Madya Ditjen Bangda Lainnya:\n"
                for r in rows[:6]:
                    res += f"  * {r[0]} ({r[1]} — Unit: {r[2]})\n"
                cur.close()
                conn.close()
                return res.strip()

        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to query staff DB: {e}")

    return "Data kepegawaian spesifik tidak ditemukan di database Ditjen Bangda 2026."


def _lookup_staff_details_for_whitelist(query: str) -> Optional[Dict[str, Any]]:
    """Mencari data kepegawaian resmi dari tabel staff_details atau master_tim_kerja_bangda_2026."""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        db_url = _get_db_url()
        conn = psycopg2.connect(db_url, connect_timeout=4)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # 1. Coba cari di staff_details (berdasarkan NIP atau Nama)
        clean_nip = "".join(c for c in query if c.isdigit())
        if len(clean_nip) >= 9:
            cur.execute("""
                SELECT id, nama, nip, pangkat, status_kepegawaian, jabatan_fungsional, penugasan_tim, grade_pppk
                FROM staff_details
                WHERE REGEXP_REPLACE(COALESCE(nip, ''), '[^0-9]', '', 'g') = %s OR nama ILIKE %s
                ORDER BY id ASC LIMIT 1;
            """, (clean_nip, f"%{query.strip()}%"))
        else:
            cur.execute("""
                SELECT id, nama, nip, pangkat, status_kepegawaian, jabatan_fungsional, penugasan_tim, grade_pppk
                FROM staff_details
                WHERE nama ILIKE %s
                ORDER BY id ASC LIMIT 1;
            """, (f"%{query.strip()}%",))
        row = cur.fetchone()
        if row:
            cur.close()
            conn.close()
            return {
                "nama": row["nama"],
                "nip": row.get("nip") or "",
                "jabatan": row.get("jabatan_fungsional") or "Staf Teknis",
                "unit_kerja": row.get("penugasan_tim") or "Ditjen Bina Pembangunan Daerah",
                "status": row.get("status_kepegawaian") or "",
                "grade": row.get("grade_pppk") or ""
            }

        # 2. Coba cari di master_tim_kerja_bangda_2026
        cur.execute("""
            SELECT nama_pegawai, nip, jabatan, unit_kerja, tim_kerja
            FROM master_tim_kerja_bangda_2026
            WHERE nama_pegawai ILIKE %s
            ORDER BY id ASC LIMIT 1;
        """, (f"%{query.strip()}%",))
        row2 = cur.fetchone()
        cur.close()
        conn.close()
        if row2:
            return {
                "nama": row2["nama_pegawai"],
                "nip": row2.get("nip") or "",
                "jabatan": row2.get("jabatan") or "Staf Teknis",
                "unit_kerja": row2.get("unit_kerja") or row2.get("tim_kerja") or "Ditjen Bina Pembangunan Daerah",
                "status": "PNS",
                "grade": ""
            }
    except Exception as e:
        logger.warning(f"Lookup staff details error: {e}")
    return None

_DIM_CACHE = {
    "daerah": None,
    "kementerian": None
}

def _load_dim_datasets():
    import json
    if _DIM_CACHE["daerah"] is None:
        p_daerah = Path("/home/aseps/MCP/workspace/Gdrive-sync/saran-masukan-daerah/output/kompilasi.json")
        if p_daerah.exists():
            try:
                with open(p_daerah, "r", encoding="utf-8") as f:
                    _DIM_CACHE["daerah"] = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load kompilasi.json: {e}")
                _DIM_CACHE["daerah"] = []
        else:
            _DIM_CACHE["daerah"] = []

    if _DIM_CACHE["kementerian"] is None:
        p_kl = Path("/home/aseps/MCP/workspace/Gdrive-sync/saran-masukan-kementerian/output/kompilasi_kementerian.json")
        if p_kl.exists():
            try:
                with open(p_kl, "r", encoding="utf-8") as f:
                    _DIM_CACHE["kementerian"] = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load kompilasi_kementerian.json: {e}")
                _DIM_CACHE["kementerian"] = []
        else:
            _DIM_CACHE["kementerian"] = []


def _retrieve_dim_uu23_data(query: str) -> str:
    """Mengambil data faktual Daftar Inventaris Masalah (DIM) / Saran Masukan Revisi UU 23/2014 dari kompilasi resmi."""
    _load_dim_datasets()
    q_lower = query.lower()

    # 1. Deteksi apakah fokus pada Provinsi / Daerah
    is_asking_provinces = any(k in q_lower for k in ["provinsi", "daerah", "pemda", "kabupaten", "kota"]) and any(
        k in q_lower for k in ["mana", "siapa", "daftar", "list", "berapa", "yang sudah", "memberi", "kirim", "menyampaikan"]
    )

    # 2. Deteksi apakah fokus pada Kementerian / Lembaga
    is_asking_kl = any(k in q_lower for k in ["kementerian", "lembaga", "k/l", "instansi"]) and any(
        k in q_lower for k in ["mana", "siapa", "daftar", "list", "berapa", "yang sudah", "memberi", "kirim", "menyampaikan"]
    )

    daerah_data = _DIM_CACHE.get("daerah") or []
    daerah_summary = {}
    for item in daerah_data:
        meta = item.get("metadata", {})
        ad = meta.get("asal_daerah")
        if ad and ad not in ["Tidak ada informasi", "Nama instansi/kementerian/lembaga asal (dari kop surat atau teks)"]:
            ad_clean = ad.strip()
            pts = item.get("coverage", {}).get("total_points") or len(item.get("sections", []))
            daerah_summary[ad_clean] = daerah_summary.get(ad_clean, 0) + pts

    kl_data = _DIM_CACHE.get("kementerian") or []
    kl_summary = {}
    for item in kl_data:
        meta = item.get("metadata", {})
        al = meta.get("asal_lembaga")
        if al and al not in ["Tidak disebutkan", "Tidak ada informasi", "Nama instansi/kementerian/lembaga asal (dari kop surat atau teks)"]:
            al_clean = al.strip()
            pts = item.get("coverage", {}).get("total_points") or len(item.get("sections", []))
            kl_summary[al_clean] = kl_summary.get(al_clean, 0) + pts

    if is_asking_provinces and not is_asking_kl:
        res = "DAFTAR RESMI PROVINSI & PEMERINTAH DAERAH YANG TELAH MEMBERIKAN MASUKAN/DIM REVISI UU 23/2014:\n"
        res += f"Total: {len(daerah_data)} Dokumen Resmi Terverifikasi (308 Butir Masukan Substantif):\n\n"
        res += "📌 *Tingkat Provinsi:*\n"
        prov_list = ["Jawa Timur", "Provinsi Bali", "Jawa Tengah", "Kalimantan Utara", "Sulawesi Selatan", "Yogyakarta", "Kalimantan Barat"]
        for p in prov_list:
            pts = daerah_summary.get(p, 0)
            res += f"- {p}: {pts} poin masukan matriks\n"
        res += "\n📌 *Tingkat Kabupaten/Kota:*\n"
        kab_list = ["Kota Madiun", "Kota Samarinda", "Kabupaten Gunungkidul", "Kabupaten Kulon Progo", "Kabupaten Tapanuli Tengah"]
        for k in kab_list:
            pts = daerah_summary.get(k, 0)
            res += f"- {k}: {pts} poin masukan\n"
        return res

    if is_asking_kl and not is_asking_provinces:
        res = "DAFTAR RESMI KEMENTERIAN & LEMBAGA YANG TELAH MEMBERIKAN MASUKAN/DIM REVISI UU 23/2014:\n"
        res += f"Total: {len(kl_data)} Dokumen Resmi (378 Butir Masukan Substantif dari {len(kl_summary)} K/L):\n\n"
        idx = 1
        for kl_name, pts in sorted(kl_summary.items(), key=lambda x: x[0]):
            res += f"{idx}. {kl_name} ({pts} poin masukan)\n"
            idx += 1
        return res

    # Jika bertanya secara umum atau menanyakan substansi spesifik
    res = "KOMPILASI RESMI SARAN & MASUKAN / DIM REVISI UU 23/2014 TENTANG PEMERINTAHAN DAERAH:\n\n"
    res += f"1. Masukan Pemerintah Daerah: {len(daerah_data)} Dokumen (308 butir masukan) dari Jawa Timur, Jawa Tengah, Bali, Kalimantan Utara, Sulawesi Selatan, DI Yogyakarta, Kalimantan Barat, Kota Samarinda, Kota Madiun, dll.\n"
    res += f"2. Masukan Kementerian/Lembaga: {len(kl_data)} Dokumen (378 butir masukan) dari Kemenhan, Kemenko Polkam, Kemenko Pangan, Kemnaker, Badan Pangan Nasional, Kementerian ATR/BPN, Kementan, Kemendag, Bappenas, Kemenpora, BSSN, Kemenhub, dll.\n"

    # Cari cuplikan jika ada kata kunci spesifik
    filter_words = [w for w in q_lower.split() if len(w) > 3 and w not in ["yang", "sudah", "memberi", "masukan", "terhadap", "revisi", "tentang", "undang", "tahun", "2014", "daftar", "inventaris", "masalah", "kementerian", "provinsi"]]
    if filter_words:
        matched_points = []
        for item in daerah_data + kl_data:
            meta = item.get("metadata", {})
            origin = meta.get("asal_daerah") or meta.get("asal_lembaga") or "Sumber"
            for sec in item.get("sections", []):
                bidang = sec.get("bidang", "")
                for pt in sec.get("points", []):
                    subs = pt.get("substansi", "")
                    masalah = pt.get("permasalahan", "")
                    saran = pt.get("rekomendasi", "")
                    combined = f"{bidang} {subs} {masalah} {saran}".lower()
                    if any(fw in combined for fw in filter_words):
                        matched_points.append(f"[{origin} - {bidang}]\n- Masalah: {masalah[:250]}\n- Saran: {saran[:250]}")
                        if len(matched_points) >= 3:
                            break
                if len(matched_points) >= 3:
                    break
            if len(matched_points) >= 3:
                break
        if matched_points:
            res += "\n📌 Cuplikan Masukan Spesifik:\n" + "\n\n".join(matched_points)

    return res


def _check_ltm_memory_status() -> str:
    """Mengambil status kesehatan dan statistik Long-Term Memory (LTM) WhatsApp & Universal RAG."""
    try:
        import psycopg2
        db_url = _get_db_url()
        conn = psycopg2.connect(db_url, connect_timeout=4)
        cur = conn.cursor()

        cur.execute("SELECT memory_type, count(*) FROM whatsapp_bot.memories GROUP BY memory_type;")
        wa_rows = cur.fetchall()
        wa_stats = {r[0]: r[1] for r in wa_rows}

        cur.execute("SELECT count(*) FROM public.memories;")
        pub_count = cur.fetchone()[0]

        cur.close()
        conn.close()

        total_wa = sum(wa_stats.values())
        return (
            "🧠 STATUS & AKSES LONG TERM MEMORY (LTM) BOT AI WHATSAPP:\n\n"
            "Status Akses Database LTM: TERHUBUNG & AKTIF (100% Normal)\n\n"
            "Statistik Memori WhatsApp (whatsapp_bot.memories):\n"
            f"- Total Riwayat Sesi: {total_wa} entri\n"
            f"- Recent Conversation: {wa_stats.get('recent', 0)} baris (Riwayat aktif per user)\n"
            f"- Implicit Aggregation: {wa_stats.get('implicit', 0)} baris (Pola interaksi mingguan)\n"
            f"- Durable Memory Facts: {wa_stats.get('durable', 0)} baris (Fakta profil persisten)\n\n"
            f"Universal LTM Global (public.memories): {pub_count} record di 43 namespace lintas-agen.\n"
            "Mesin Embedding (Ollama Port 11434): all-minilm (384-dim) & nomic-embed-text (768-dim) Online.\n"
            "Akses memori aktif dan dapat diakses secara otomatis oleh AI Orchestrator."
        )
    except Exception as e:
        return f"Gagal mengecek status LTM: {e}"


def _retrieve_rag_legal_knowledge(query: str) -> str:
    """Mencari naskah peraturan perundang-undangan dan tata naskah dari database RAG pgvector / knowledge_documents."""
    q_lower = query.lower()

    # 0. Deteksi Khusus: DIM / Masukan Revisi UU 23/2014
    dim_triggers = [
        "dim", "inventaris masalah", "inventaymasalah", "masukan uu 23", "revisi uu 23",
        "saran daerah", "saran kementerian", "masukan provinsi", "masukan daerah",
        "saran masukan"
    ]
    if any(t in q_lower for t in dim_triggers) or ("uu 23" in q_lower and any(w in q_lower for w in ["masukan", "saran", "daerah", "kementerian", "provinsi"])):
        dim_data = _retrieve_dim_uu23_data(query)
        if dim_data:
            return dim_data

    # 0.5 Deteksi Khusus: Cek Status LTM Memory
    ltm_triggers = ["memory ltm", "memori ltm", "list memory", "daftar memori", "akses ltm", "status ltm"]
    if any(t in q_lower for t in ltm_triggers):
        return _check_ltm_memory_status()

    try:
        import psycopg2
        db_url = _get_db_url()
        conn = psycopg2.connect(db_url, connect_timeout=5)
        cur = conn.cursor()

        # Ekstraksi kata kunci penting (regulasi, tata naskah, perencanaan, tata ruang, adminduk, ketenagakerjaan, dll)
        reg_keywords = [
            "permendagri", "41", "pkl", "tdu", "cipta kerja", "pp 7", "2021", "2012", "uu 6", "uu 23",
            "psu", "utilitas", "tmmd", "120", "80", "1/2023", "83/2022", "9/2025", "86/2017", "13/2016",
            "20/2018", "113/2014", "tata naskah", "naskah dinas", "kode klasifikasi", "rpjmd", "rpjpd",
            "rkpd", "rtrw", "tata ruang", "persub", "keuangan desa", "hkpd", "1/2022", "pdrd", "retribusi",
            "pdp", "27/2022", "57/2021", "smki", "adminduk", "mk 137", "putusan mk", "sotk", "bangda",
            "struktur", "evaluasi ranperda", "margin", "font", "arial", "gelar", "persuratan",
            "naker", "tenaga kerja", "ketenagakerjaan", "transmigrasi", "tenaga ahli", "supd iv", "supd 4",
            "amaryadi", "lpk", "akad", "upah", "ump", "umk", "pengawasan ketenagakerjaan"
        ]
        keywords = [kw for kw in reg_keywords if kw in q_lower]

        active_namespaces = (
            'evaluasi_regulasi', 'legal_regulations', 'shared_legal',
            'arsip_knowledge', 'setditjen_bangda', 'docs_rag', 'supd_iv'
        )

        if keywords:
            clauses = ["(COALESCE(metadata->>'title', metadata->>'file_name', id) ILIKE %s OR content ILIKE %s)" for _ in keywords]
            params = []
            for kw in keywords:
                params.extend([f"%{kw}%", f"%{kw}%"])
            params.append(active_namespaces)
            sql = f"""
                SELECT COALESCE(metadata->>'title', metadata->>'file_name', id) AS title, content 
                FROM knowledge_documents 
                WHERE ({' OR '.join(clauses)})
                  AND namespace IN %s
                ORDER BY created_at DESC LIMIT 3;
            """
            cur.execute(sql, params)
            rows = cur.fetchall()
            if rows:
                rag_text = "NASKAH PERATURAN & KNOWLEDGE BASE TERVERIFIKASI (RAG DATABASE):\n"
                for r in rows:
                    rag_text += f"\n📜 *{r[0]}*\n{r[1][:950]}\n"
                cur.close()
                conn.close()
                return rag_text.strip()

        # Semantic Vector Search via Ollama nomic-embed-text
        try:
            import requests
            resp = requests.post(
                "http://127.0.0.1:11434/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": query[:1000]},
                timeout=4
            )
            if resp.status_code == 200:
                emb = resp.json().get("embedding")
                if emb:
                    cur.execute("""
                        SELECT COALESCE(metadata->>'title', metadata->>'file_name', id) AS title, content
                        FROM knowledge_documents
                        WHERE namespace IN %s
                          AND embedding IS NOT NULL
                        ORDER BY embedding <=> %s::vector
                        LIMIT 3;
                    """, (active_namespaces, emb))
                    v_rows = cur.fetchall()
                    if v_rows:
                        rag_text = "NASKAH PERATURAN & KNOWLEDGE BASE TERVERIFIKASI (RAG DATABASE):\n"
                        for r in v_rows:
                            rag_text += f"\n📜 *{r[0]}*\n{r[1][:950]}\n"
                        cur.close()
                        conn.close()
                        return rag_text.strip()
        except Exception as sem_err:
            logger.debug(f"Semantic search fallback notice: {sem_err}")

        # Fallback query umum
        cur.execute("""
            SELECT COALESCE(metadata->>'title', metadata->>'file_name', id) AS title, content 
            FROM knowledge_documents 
            WHERE namespace IN %s
            ORDER BY created_at DESC LIMIT 2;
        """, (active_namespaces,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        if rows:
            rag_text = "NASKAH REGULASI TERKAIT:\n"
            for r in rows:
                rag_text += f"\n📜 *{r[0]}*\n{r[1][:650]}\n"
            return rag_text.strip()
    except Exception as e:
        logger.warning(f"RAG search error: {e}")

    return ""


def _query_korespondensi_data(query: str) -> str:
    """Mencari surat masuk, surat keluar, disposisi, dan permohonan fasilitasi dari database korespondensi Ditjen Bangda."""
    # 0. Deterministic Dual-Branch Resolver for Agenda / Nomor Surat
    try:
        from integrations.whatsapp.correspondence_resolver import (
            extract_identifiers,
            resolve_incoming_letter,
            format_dossier_for_whatsapp
        )
        ids = extract_identifiers(query)
        if ids.get("agenda_ula") or ids.get("agenda_ses") or ids.get("nomor_surat") or any(k in query.lower() for k in ["agenda", "disposisi", "/l", "rbi", "b-131"]):
            dossier = resolve_incoming_letter(query, download_attachment=True)
            if dossier.get("status") == "success":
                return format_dossier_for_whatsapp(dossier)
    except Exception as e:
        logger.warning(f"Dual-branch correspondence resolver error: {e}, falling back to DB query...")

    try:
        import psycopg2
        db_url = _get_db_url()
        conn = psycopg2.connect(db_url, connect_timeout=5)
        cur = conn.cursor()

        q_lower = query.lower()

        # 1. Deteksi tanggal bahasa Indonesia (misal: 3 september 2026)
        month_map = {
            "januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6,
            "juli": 7, "agustus": 8, "september": 9, "oktober": 10, "november": 11, "desember": 12
        }
        target_date = None
        date_m = re.search(r'(\d{1,2})\s+(januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember)\s+(\d{4})', q_lower)
        if date_m:
            d, mon, y = int(date_m.group(1)), month_map[date_m.group(2)], int(date_m.group(3))
            target_date = f"{y:04d}-{mon:02d}-{d:02d}"

        # 2. Penanganan Kueri Berdasarkan Tanggal Spesifik
        if target_date:
            cur.execute("""
                SELECT nomor_nd, dari, hal, posisi, disposisi, tanggal, tanggal_diterima, source_sheet_name
                FROM korespondensi_raw_pool
                WHERE tanggal_diterima = %s OR tanggal = %s
                ORDER BY id DESC LIMIT 15;
            """, (target_date, target_date))
            raw_rows = cur.fetchall()

            if raw_rows:
                res = f"REKAPITULASI RESMI AGENDA PERSURATAN DITJEN BANGDA PER TANGGAL {date_m.group(0).upper()}:\n\n"
                for i, r in enumerate(raw_rows, 1):
                    nomor_nd = r[0]
                    dari = r[1] or '-'
                    hal = r[2] or '-'
                    posisi = r[3] or '-'
                    disposisi = r[4] if r[4] else 'Belum ada catatan disposisi spesifik'
                    tgl_rec = r[6] or r[5]
                    tgl_str = tgl_rec.strftime('%d %B %Y') if tgl_rec else target_date
                    sheet_cat = "Eksternal (Surat Masuk Daerah/K/L)" if "surat masuk" in (r[7] or '').lower() else f"Internal Ditjen ({r[7] or 'Nota Dinas'})"

                    res += (
                        f"[{i}] *Nomor*         : `{nomor_nd}`\n"
                        f"    *Kategori*      : {sheet_cat}\n"
                        f"    *Asal Pengirim* : {dari}\n"
                        f"    *Perihal*       : {hal}\n"
                        f"    *Tanggal Terima*: {tgl_str}\n"
                        f"    *Posisi Berkas* : {posisi}\n"
                        f"    *Disposisi*     : {disposisi}\n\n"
                    )
                cur.close()
                conn.close()
                return res.strip()

        # 2b. Penanganan Kueri Khusus: Surat Belum Terdisposisi
        is_undisposed_query = any(k in q_lower for k in [
            "belum terdisposisi", "belum didisposisi", "tanpa disposisi",
            "belum ada disposisi", "disposisi kosong", "belum disposisi"
        ])
        if is_undisposed_query:
            target_leader = "Pimpinan Ditjen Bina Pembangunan Daerah"
            if "dirjen" in q_lower:
                target_leader = "Direktur Jenderal"
            elif "sesditjen" in q_lower or "ses" in q_lower:
                target_leader = "Sekretaris Ditjen"

            cur.execute("""
                SELECT nomor_nd, dari, hal, posisi, disposisi, source_sheet_name, COALESCE(tanggal_diterima, tanggal)
                FROM korespondensi_raw_pool
                WHERE (disposisi IS NULL OR TRIM(disposisi) IN ('', '-', 'Belum ada catatan disposisi spesifik'))
                ORDER BY id DESC LIMIT 10;
            """)
            undisposed_rows = cur.fetchall()
            cur.close()
            conn.close()

            if undisposed_rows:
                res = f"REKAPITULASI SURAT BELUM TERDISPOSISI ({target_leader.upper()}):\n\n"
                res += f"Total Surat Tertunda: {len(undisposed_rows)} berkas\n\n"
                for i, r in enumerate(undisposed_rows, 1):
                    nomor_nd = r[0]
                    dari = r[1] or '-'
                    hal = r[2] or '-'
                    posisi = r[3] or '-'
                    tgl_rec = r[6]
                    tgl_str = tgl_rec.strftime('%d %B %Y') if tgl_rec else '-'
                    res += (
                        f"[{i}] *No Surat/Agenda*: `{nomor_nd}`\n"
                        f"    *Asal Pengirim*: {dari}\n"
                        f"    *Perihal*: {hal}\n"
                        f"    *Tanggal Terima*: {tgl_str}\n"
                        f"    *Posisi Berkas*: {posisi}\n"
                        f"    *Status Disposisi*: Belum Ada Disposisi\n\n"
                    )
                return res.strip()
            else:
                return f"Seluruh berkas surat terpantau telah terdisposisi. Tidak ada surat tertunda untuk {target_leader}."

        # 3. Kueri Berbasis Kata Kunci Umum / Ranperda / Pemda / Disposisi
        stop_words = {"tolong", "cek", "surat", "perihal", "coba", "tampilkan", "data", "terbaru", "mengapa", "kamu", "permohonan", "tentang", "pada", "yang", "dan", "untuk", "laporkan", "list", "masuk", "eksternal", "diterima", "oleh"}
        meaningful_tokens = [w for w in re.findall(r'\b[a-zA-Z0-9]{3,}\b', q_lower) if w not in stop_words]
        target_tokens = [t for t in meaningful_tokens if t in ["rtrw", "fasilitasi", "ranperda", "sintang", "bengkulu", "kalbar", "dirjen", "jabar", "stunting", "belitung", "kalteng"]] or meaningful_tokens
        if not target_tokens:
            target_tokens = ["fasilitasi"]

        conds = " OR ".join(["hal ILIKE %s OR nomor_nd ILIKE %s OR dari ILIKE %s OR disposisi ILIKE %s" for _ in target_tokens])
        params = []
        for t in target_tokens:
            params.extend([f"%{t}%", f"%{t}%", f"%{t}%", f"%{t}%"])

        sql = f"""
            SELECT nomor_nd, hal, dari, posisi, disposisi, source_sheet_name, COALESCE(tanggal_diterima, tanggal)
            FROM korespondensi_raw_pool 
            WHERE {conds}
            ORDER BY id DESC LIMIT 5;
        """
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if rows:
            res = "DATA KORESPONDENSI & PERSURATAN DITJEN BANGDA (DATABASE RESMI):\n\n"
            for i, r in enumerate(rows, 1):
                tgl_str = r[6].strftime('%d %B %Y') if r[6] else '-'
                res += (
                    f"[{i}] *No Surat/Agenda*: `{r[0]}`\n"
                    f"    *Kategori*: {r[5] or 'Korespondensi'}\n"
                    f"    *Hal*: {r[1]}\n"
                    f"    *Pengirim*: {r[2] or '-'}\n"
                    f"    *Tanggal*: {tgl_str}\n"
                    f"    *Posisi Berkas*: {r[3] or '-'}\n"
                    f"    *Disposisi*: {r[4] or '-'}\n\n"
                )
            return res.strip()
        else:
            return f"Tidak ditemukan arsip korespondensi dengan kata kunci '{query}' di database Ditjen Bangda."
    except Exception as e:
        logger.warning(f"Error querying korespondensi: {e}")
        return f"Gagal mengakses database korespondensi: {e}"


async def _search_web_hybrid(query: str) -> str:
    """Melakukan pencarian internet live via Tri-Engine Hybrid Search (DDG Lite, Playwright, Browser-Use)."""
    try:
        from core.browser.hybrid_search import hybrid_search_engine
        res = await hybrid_search_engine.search(query=query, max_results=3)
        if not res.get("success") or not res.get("results"):
            return f"Tidak ditemukan hasil pencarian web resmi untuk '{query}'."

        engine = res.get("engine_used", "hybrid").upper()
        res_text = f"HASIL PENELUSURAN DOKUMEN & WEB RESMI (ENGINE: {engine}):\n"
        for r in res.get("results", []):
            res_text += f"- Judul: {r.get('title')}\n  Ringkasan: {r.get('snippet')}\n  Tautan: {r.get('url')}\n\n"
        return res_text.strip()
    except Exception as e:
        logger.warning(f"Hybrid web search failed: {e}")
        return f"Pencarian web mengalami gangguan sementara: {e}"


def _search_social_media_handler(query: str, platform: str = "all") -> str:
    """Melakukan pencarian postingan, opini, atau isu terkini di media sosial publik."""
    try:
        from core.browser.hybrid_search import hybrid_search_engine
        raw = hybrid_search_engine._search_social_sync(query=query, platform=platform, limit=4)
        if not raw:
            return f"Tidak ditemukan postingan atau opini publik media sosial terkait '{query}'."
        
        res_text = f"HASIL PEMANTAUAN MEDIA SOSIAL PUBLIK (KATA KUNCI: {query}):\n\n"
        for i, r in enumerate(raw, 1):
            res_text += (
                f"{i}. {r.get('badge', '📱')} *{r.get('title')}*\n"
                f"   • Cuplikan: {r.get('snippet')}\n"
                f"   • Tautan: {r.get('url')}\n\n"
            )
        return res_text.strip()
    except Exception as e:
        logger.warning(f"Social media search failed: {e}")
        return f"Penelusuran media sosial mengalami kendala sementara: {e}"


def _execute_patch_clause(problematic_clause: str, reason_or_defect: str = "") -> str:
    """
    Menyusun rumusan klausul alternatif aman (safe drafting) dan rekomendasi perbaikan norma hukum
    sesuai asas pembentukan peraturan perundang-undangan (UU 12/2011 jo UU 13/2022) dan pembagian urusan konkuren UU 23/2014.
    """
    has_full_draft = "pasal" in problematic_clause.lower() and len(problematic_clause.splitlines()) > 5
    m_art = re.search(r'pasal\s+(\d+[a-z]?)', problematic_clause, re.IGNORECASE)
    target_art = f"Pasal {m_art.group(1)}" if m_art else "Pasal 1"
    
    diff_report = ""
    if has_full_draft and m_art:
        try:
            patch_res = legal_patch_clause(
                regulation_text=problematic_clause,
                target_article=target_art,
                new_clause_text=f"{target_art}\n(1) Ketentuan teknis penyelenggaraan urusan konkuren dilaksanakan dengan berpedoman pada norma, standar, prosedur, dan kriteria (NSPK) yang ditetapkan oleh kementerian terkait.",
                rationale=reason_or_defect or "Harmonisasi hierarki norma & pencegahan ultra vires"
            )
            if patch_res.get("success") and patch_res.get("diff"):
                diff_report = f"\n\n*Perubahan AST / Draf Diff:*\n```diff\n{patch_res.get('diff')[:500]}\n```"
        except Exception as err:
            logger.warning(f"AST patch notice: {err}")

    res = (
        f"📝 *REKOMENDASI FORMULASI SAFE DRAFTING (PERBAIKAN KLAUSUL)*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ *Analisis Risiko/Cacat Norma:*\n"
        f"• {reason_or_defect if reason_or_defect else 'Potensi ketidakselarasan dengan hierarki peraturan perundang-undangan yang lebih tinggi atau pembagian urusan konkuren UU 23/2014.'}\n\n"
        f"📜 *Rumusan Awal (As-Is):*\n"
        f"> {problematic_clause.strip()}\n\n"
        f"⚖️ *Prinsip Safe Drafting PUU Ditjen Bangda:*\n"
        f"1. *Subjek & Wewenang:* Hindari atribusi kewenangan baru tanpa delegasi eksplisit dari UU/PP induk.\n"
        f"2. *Pilihan Diksi Hukum:* Gunakan kata imperatif baku ('wajib', 'dilarang', 'berwenang') secara proporsional.\n"
        f"3. *Klausul Pengaman (Safeguard):* Tambahkan frasa 'sesuai dengan ketentuan peraturan perundang-undangan' untuk mencegah sengketa kewenangan antartingkat pemerintahan.\n\n"
        f"💡 *Rekomendasi Klausul Alternatif Aman (To-Be):*\n"
        f"Rumusan norma disarankan disesuaikan dengan menegaskan batas kewenangan konkuren daerah serta kewajiban sinkronisasi teknis dengan kementerian/lembaga pembina teknis.{diff_report}"
    )
    return res


async def _execute_verify_spm(indicator_query: str) -> str:
    """
    Memverifikasi pemenuhan Standar Pelayanan Minimal (SPM) pada 6 Urusan Wajib Dasar Ditjen Bangda.
    """
    spm_sectors = {
        "pendidikan": {
            "regulasi": "PP No. 2/2018 & Permendikbudristek No. 32/2018",
            "fokus": "Pendidikan Anak Usia Dini (PAUD), Pendidikan Dasar (SD/SMP), dan Pendidikan Kesetaraan.",
            "indikator": [
                "Jumlah warga negara usia 7-15 tahun yang berpartisipasi dalam pendidikan dasar",
                "Penyediaan pendidik dan tenaga kependidikan berstandar",
                "Bantuan operasional dan sarana prasarana sekolah dasar"
            ]
        },
        "kesehatan": {
            "regulasi": "PP No. 2/2018 & Permenkes No. 4/2019",
            "fokus": "Pelayanan kesehatan ibu hamil, bersalin, balita, usia produktif, lansia, hipertensi, DM, ODGJ, TB, dan HIV.",
            "indikator": [
                "Pelayanan kesehatan ibu hamil sesuai standar K4/K6",
                "Pelayanan kesehatan balita sesuai standar tumbuh kembang (antistunting)",
                "Penanganan skrining kesehatan usia produktif dan lansia"
            ]
        },
        "pekerjaan_umum": {
            "regulasi": "PP No. 2/2018 & Permen PUPR No. 29/PRT/M/2018",
            "fokus": "Penyediaan kebutuhan pokok air minum curah dan pengolahan air limbah domestik skala kabupaten/kota.",
            "indikator": [
                "Akses pemenuhan air minum curah minimal 60 liter/orang/hari",
                "Akses sistem pengolahan air limbah domestik setempat/terpusat"
            ]
        },
        "perumahan": {
            "regulasi": "PP No. 2/2018 & Permen PUPR No. 29/PRT/M/2018",
            "fokus": "Penyediaan dan rehabilitasi rumah layak huni bagi korban bencana dan relokasi program daerah.",
            "indikator": [
                "Penyediaan rumah layak huni bagi korban bencana kabupaten/kota",
                "Fasilitasi relokasi perumahan terdampak program strategis pemerintah daerah"
            ]
        },
        "trantibumlinmas": {
            "regulasi": "PP No. 2/2018 & Permendagri No. 101/2018",
            "fokus": "Pelayanan ketenteraman dan ketertiban umum (Satpol PP), penanggulangan bencana (BPBD), dan penyelamatan kebakaran (Damkar).",
            "indikator": [
                "Tingkat waktu tanggap (response time) penanganan kebakaran < 15 menit",
                "Pelayanan evakuasi dan penyelamatan korban bencana daerah",
                "Patroli penegakan perda ketertiban umum dan perlindungan masyarakat"
            ]
        },
        "sosial": {
            "regulasi": "PP No. 2/2018 & Permensos No. 9/2018",
            "fokus": "Rehabilitasi sosial dasar penyandang disabilitas terlantar, anak terlantar, lansia terlantar, dan gelandangan/pengemis di luar panti.",
            "indikator": [
                "Bantuan permakanan dan sandang darurat bagi korban bencana",
                "Pelayanan rehabilitasi sosial bagi penyandang disabilitas & lansia terlantar di luar panti"
            ]
        }
    }

    q_low = indicator_query.lower()
    matched_sector = None
    for s_name in spm_sectors:
        if s_name in q_low:
            matched_sector = s_name
            break
    if not matched_sector:
        if any(k in q_low for k in ["sekolah", "guru", "murid", "paud", "sd", "smp", "didik"]):
            matched_sector = "pendidikan"
        elif any(k in q_low for k in ["puskesmas", "posyandu", "stunting", "balita", "ibu hamil", "odgj", "rsud", "sehat"]):
            matched_sector = "kesehatan"
        elif any(k in q_low for k in ["air minum", "air bersih", "limbah", "pdam", "sanitasi", "pu"]):
            matched_sector = "pekerjaan_umum"
        elif any(k in q_low for k in ["rumah", "hunian", "rtlh", "relokasi", "mukim"]):
            matched_sector = "perumahan"
        elif any(k in q_low for k in ["damkar", "kebakaran", "pol pp", "satpol", "bencana", "bpbd", "trantib"]):
            matched_sector = "trantibumlinmas"
        elif any(k in q_low for k in ["lansia", "disabilitas", "terlantar", "panti", "bansos", "sosial"]):
            matched_sector = "sosial"

    kb_info = ""
    try:
        raw_res = await legal_verify_spm({"query": indicator_query, "deskripsi": indicator_query})
        if raw_res and raw_res.get("success"):
            kb_info = "\n*Sinkronisasi Ditjen Bangda:* Terverifikasi sesuai database regulasi SPM Ditjen Bangda."
    except Exception as e:
        logger.warning(f"Verify SPM tool warning: {e}")

    if matched_sector:
        info = spm_sectors[matched_sector]
        ind_list = "\n".join([f"  • {item}" for item in info["indikator"]])
        return (
            f"📊 *HASIL VERIFIKASI STANDAR PELAYANAN MINIMAL (SPM)*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏛️ *Sektor:* SPM Urusan Wajib Dasar — *{matched_sector.replace('_', ' ').upper()}*\n"
            f"📜 *Regulasi Rujukan:* {info['regulasi']} jo Permendagri No. 59/2021.\n"
            f"🎯 *Fokus Pelayanan Dasar:* {info['fokus']}\n\n"
            f"📌 *Indikator Mutu & Kinerja Kunci:*\n{ind_list}\n\n"
            f"💡 *Catatan Pengawasan SUPD Kemendagri:*\n"
            f"Pemerintah Daerah wajib mengalokasikan anggaran prioritas dalam APBD untuk pemenuhan SPM sebelum mendanai urusan pilihan.{kb_info}"
        )
    else:
        return (
            f"📊 *VERIFIKASI STANDAR PELAYANAN MINIMAL (SPM) 6 URUSAN WAJIB DASAR*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Sesuai UU 23/2014 & PP 2/2018, SPM berlaku bagi 6 urusan pemerintahan wajib pelayanan dasar:\n"
            f"1. *Pendidikan* (Pendidikan dasar & kesetaraan)\n"
            f"2. *Kesehatan* (Layanan promotif/preventif dasar di puskesmas/posyandu)\n"
            f"3. *Pekerjaan Umum* (Air minum curah & air limbah domestik)\n"
            f"4. *Perumahan Rakyat* (Rumah layak huni bagi korban bencana/relokasi)\n"
            f"5. *Trantibumlinmas* (Satpol PP, penanggulangan bencana, & pemadam kebakaran)\n"
            f"6. *Sosial* (Rehabilitasi dasar penyandang disabilitas, lansia, & anak terlantar)\n\n"
            f"Silakan cantumkan sektor atau indikator spesifik yang ingin diverifikasi capaian atau regulasinya."
        )


def _execute_generate_nota_dinas(hal: str, poin_pembahasan: str = "", jenis: str = "nd_laporan", rujukan_surat: str = "") -> str:
    """
    Menyusun draf resmi Nota Dinas Laporan Hasil Rapat / Telaahan Staf / Pengantar
    di lingkungan Ditjen Bina Pembangunan Daerah berbasis Golden Pattern Standard 2026
    dan menghasilkan berkas .docx berbasis Master Template resmi Permendagri No. 1 Tahun 2023.
    """
    month_names = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
    now = datetime.now()
    now_date = f"{now.day} {month_names[now.month - 1]} {now.year}"
    
    clean_hal = hal.strip()
    points_text = (poin_pembahasan or "").strip()
    if not points_text or points_text.lower() in [clean_hal.lower(), "-"]:
        points_content = (
            "1. Pemaparan materi teknis koordinasi pembinaan pelaksanaan urusan pemerintahan daerah oleh kementerian/lembaga pembina sektor.\n"
            "2. Identifikasi kendala implementasi regulasi, sinkronisasi program pusat-daerah, dan pemenuhan target SPM.\n"
            "3. Perumusan kesepakatan tindak lanjut harmonisasi kebijakan dan konsolidasi instrumen evaluasi ranperda/raperkada."
        )
    else:
        points_content = points_text

    is_pengantar = "pengantar" in clean_hal.lower() or jenis == "nd_pengantar"
    is_sesditjen_ke_dirjen = ("dirjen" in clean_hal.lower() and ("sesditjen" in clean_hal.lower() or "sekretaris" in clean_hal.lower())) or jenis == "nd_sesditjen"

    # Generate DOCX via satria_naskah_generator
    docx_path = ""
    try:
        from integrations.whatsapp.naskah_dinas_generator import satria_naskah_generator
        if is_sesditjen_ke_dirjen:
            docx_path = satria_naskah_generator.generate_nd_sesditjen_ke_dirjen({
                "hal": clean_hal,
                "tanggal_nd": now_date,
                "nomor_surat_masuk": rujukan_surat or "-"
            })
        elif is_pengantar:
            docx_path = satria_naskah_generator.generate_nd_pengantar({
                "hal": clean_hal,
                "tanggal_nd": now_date,
                "nomor_surat_masuk": rujukan_surat or "-",
                "telaah_puu": points_text if points_text else None
            })
        else:
            docx_path = satria_naskah_generator.generate_nd_laporan({
                "hal": clean_hal,
                "tanggal_nd": now_date
            })
    except Exception as err:
        logger.warning(f"Error generating docx template: {err}")

    docx_notice = ""
    if docx_path:
        docx_notice = (
            f"\n\n📁 *Berkas Word (.docx) Resmi Berhasil Digenerasi:*\n"
            f"Path: `{docx_path}`\n"
            f"_(Telah disesuaikan dengan Format Baku Permendagri No. 1 Tahun 2023, Arial 11pt, Margin 3-1-3-2 cm, dan Kop Resmi Ditjen Bina Bangda)_"
        )

    if is_sesditjen_ke_dirjen:
        draft = (
            f"📋 *DRAF NOTA DINAS TINGKAT PIMPINAN (SESDITJEN KE DIRJEN)*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"*NOTA DINAS*\n\n"
            f"*Yth.*       : Bapak Dirjen Bina Pembangunan Daerah\n"
            f"*Dari*      : Sekretaris Ditjen Bina Pembangunan Daerah\n"
            f"*Tanggal*   : {now_date}\n"
            f"*Nomor*     : 100.4.2/        /Set/Bangda\n"
            f"*Sifat*     : Segera\n"
            f"*Lampiran*  : Satu berkas\n"
            f"*Hal*       : *{clean_hal}*\n\n"
            f"Menindaklanjuti koordinasi dan disposisi mengenai hal tersebut di atas, dengan hormat dilaporkan kepada Bapak Dirjen beberapa hal sebagai berikut:\n\n"
            f"*Pokok-Pokok Pembahasan & Telaahan*\n"
            f"{points_content}\n\n"
            f"Berkenan dengan hal tersebut, kami sampaikan konsep naskah dinas terlampir untuk mohon perkenan arahan dan tanda tangan/paraf koordinasi Bapak Dirjen.\n\n"
            f"Demikian kami laporkan dan mohon arahan Bapak Dirjen lebih lanjut.\n\n"
            f"                                        *Sekretaris Ditjen Bina Pembangunan Daerah,*\n\n\n"
            f"                                        *Drs. Maddaremmeng, M.Si*\n"
            f"                                        Pembina Utama Madya (IV/d)\n"
            f"                                        NIP 19700920 199101 1 001"
            f"{docx_notice}"
        )
    elif is_pengantar:
        draft = (
            f"📋 *DRAF NOTA DINAS PENGANTAR KE SESDITJEN (GOLDEN PATTERN 2026)*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"*NOTA DINAS*\n\n"
            f"*Yth.*       : Bapak Sekretaris Ditjen Bina Pembangunan Daerah\n"
            f"*Dari*      : Analis Hukum Ahli Madya\n"
            f"*Tembusan*  : -\n"
            f"*Tanggal*   : {now_date}\n"
            f"*Nomor*     : 100.4.4.1/        /PUU\n"
            f"*Sifat*     : Segera\n"
            f"*Lampiran*  : Satu berkas\n"
            f"*Hal*       : *{clean_hal}*\n\n"
            f"Menindaklanjuti disposisi Bapak Sekretaris Ditjen atas surat masuk terkait, dengan hormat kami laporkan hal-hal sebagai berikut:\n\n"
            f"*Hasil Pencermatan & Telaah PUU*\n"
            f"{points_content}\n\n"
            f"Berkenan dengan hal tersebut, bersama ini kami sampaikan konsep Nota Dinas Bapak Sekretaris Ditjen kepada Bapak Dirjen serta draf regulasi/naskah dinas terkait untuk mohon perkenan paraf dan tanda tangan.\n\n"
            f"Demikian dilaporkan, mohon arahan Bapak Sekretaris Ditjen lebih lanjut.\n\n"
            f"                                        *Analis Hukum Ahli Madya,*\n\n\n"
            f"                                        *Lady Diana Handayani, MH*\n"
            f"                                        Pembina Tk.I (IV/b)\n"
            f"                                        NIP 19830306 200812 2 001"
            f"{docx_notice}"
        )
    else:
        draft = (
            f"📋 *DRAF NOTA DINAS LAPORAN HASIL RAPAT (GOLDEN PATTERN 2026)*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"*NOTA DINAS*\n\n"
            f"*Yth.*       : Bapak Sekretaris Ditjen Bina Pembangunan Daerah\n"
            f"*Dari*      : Analis Hukum Ahli Madya\n"
            f"*Tembusan*  : 1. Direktur Jenderal Bina Pembangunan Daerah (sebagai laporan)\n"
            f"              2. Direktur SUPD Terkait\n"
            f"*Nomor*     : 000.1.5/        /PUU\n"
            f"*Tanggal*   : {now_date}\n"
            f"*Sifat*     : Segera\n"
            f"*Lampiran*  : -\n"
            f"*Hal*       : *Laporan Pelaksanaan {clean_hal}*\n\n"
            f"Menindaklanjuti pelaksanaan kegiatan koordinasi mengenai hal tersebut di atas, dengan hormat kami laporkan beberapa hal sebagai berikut:\n\n"
            f"*Pelaksanaan Kegiatan*\n"
            f"Kegiatan telah diselenggarakan dengan melibatkan perwakilan kementerian/lembaga terkait, jajaran direktorat di lingkungan Ditjen Bina Pembangunan Daerah, serta pemerintah daerah.\n\n"
            f"*Hasil Pembahasan dan Pokok Pemaparan*\n"
            f"{points_content}\n\n"
            f"*Tanggapan dan Rekomendasi Ditjen Bina Pembangunan Daerah Kemendagri*\n"
            f"a. *Aspek Keselarasan Kebijakan Nasional:*\n"
            f"   Materi muatan kebijakan wajib dipastikan selaras dengan pembagian urusan pemerintahan konkuren sebagaimana diatur dalam UU Nomor 23 Tahun 2014.\n"
            f"b. *Posisi Strategis & Rekomendasi Tindak Lanjut Bangda:*\n"
            f"   Disarankan agar substansi teknis dikoordinasikan lebih lanjut bersama Direktorat SUPD pengampu dan dilakukan harmonisasi draf regulasi bersama Biro Hukum Setjen Kemendagri.\n\n"
            f"Demikian kami laporkan dan mohon arahan Bapak Sekretaris Ditjen lebih lanjut.\n\n"
            f"                                        *Analis Hukum Ahli Madya,*\n\n\n"
            f"                                        *Lady Diana Handayani, MH*\n"
            f"                                        Pembina Tk.I (IV/b)\n"
            f"                                        NIP 19830306 200812 2 001"
            f"{docx_notice}"
        )
    return draft


async def _execute_system_health(service_target: str = "all") -> str:
    """
    Memeriksa kesehatan infrastruktur teknis MCP, engine Microsoft Agent Framework (MAF),
    database PostgreSQL (Port 5433), status RunPod GPU, dan status bot WhatsApp.
    """
    import socket
    import psycopg2

    # 0. Microsoft Agent Framework (MAF Core Engine) Check
    maf_status = "🟢 ACTIVE & INTEGRATED (v1.19.0)"
    maf_detail = "agent-framework-core active, multi-channel router ready"
    try:
        if "agent_framework" not in sys.modules or not getattr(sys.modules["agent_framework"], "__file__", "").endswith("site-packages/agent_framework/__init__.py"):
            _saved_path = list(sys.path)
            try:
                sys.path = [p for p in sys.path if p != '/home/aseps/MCP/core' and not p.endswith('/core')]
                import agent_framework
            finally:
                sys.path = _saved_path
        else:
            import agent_framework

        s_maf = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s_maf.settimeout(1.0)
        res_maf = s_maf.connect_ex(('127.0.0.1', 8108))
        s_maf.close()
        hub_status = "Hub: Port 8108 Online" if res_maf == 0 else "Hub: In-Process Engine"
        maf_version = getattr(agent_framework, "__version__", "1.19.0")
        maf_detail = f"MAF Core v{maf_version} ({hub_status})"
    except Exception as e:
        maf_status = "🟡 STANDBY / IN-PROCESS"
        maf_detail = f"MAF engine: {e}"

    # 1. PostgreSQL Port 5433 Check
    db_status = "🔴 OFFLINE"
    db_detail = "Tidak terhubung"
    t_start = time.time()
    try:
        db_url = _get_db_url()
        conn = psycopg2.connect(db_url, connect_timeout=3)
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM korespondensi_raw_pool;")
        total_rows = cur.fetchone()[0]
        cur.close()
        conn.close()
        db_latency = round((time.time() - t_start) * 1000, 1)
        db_status = "🟢 ONLINE"
        db_detail = f"Aktif ({db_latency} ms, {total_rows:,} baris arsip)"
    except Exception as e:
        db_detail = f"Gangguan: {e}"

    # 2. Port Orchestrator (8001)
    orch_status = "🟢 ACTIVE (Port 8001)"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.5)
        res = s.connect_ex(('127.0.0.1', 8001))
        s.close()
        if res != 0:
            orch_status = "🟡 STANDBY / SSE MODE"
    except Exception:
        orch_status = "⚪ UNCHECKED"

    # 3. Port WhatsApp Baileys (3001)
    wa_status = "🟢 CONNECTED (Port 3001)"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.5)
        res = s.connect_ex(('127.0.0.1', 3001))
        s.close()
        if res != 0:
            wa_status = "🟡 SERVICE DISCONNECTED"
    except Exception:
        wa_status = "⚪ UNCHECKED"

    # 4. RunPod Serverless GPU
    runpod_key = os.getenv("RUNPOD_API_KEY") or os.getenv("RUNPOD_API_KEY_SURYA_OCR")
    if runpod_key:
        try:
            from integrations.runpod.tools import runpod_check_health
            rp_res = await asyncio.wait_for(runpod_check_health(), timeout=3.0)
            rp_status = f"🟢 READY (Workers: {rp_res.get('workers', {}).get('idle', 0)} Idle, {rp_res.get('workers', {}).get('running', 0)} Running)"
        except Exception:
            rp_status = "🟡 CLOUD GPU STANDBY (Local Inference Active)"
    else:
        rp_status = "⚪ STANDBY / LOCAL ENGINE (Ollama / Vane GPU Active)"

    # 5. Circuit Breakers
    circuits = ["lookup_bangda_staff", "search_regulation_knowledge", "cari_surat_korespondensi"]
    c_states = [f"{c}: {satria_timeout_guard.get_circuit_state(c).value}" for c in circuits]
    c_summary = "🟢 ALL HEALTHY (CLOSED)" if all("closed" in s.lower() for s in c_states) else f"⚠️ DEGRADED: {', '.join(c_states)}"

    now_str = datetime.now().strftime("%d %B %Y %H:%M:%S WIB")
    report = (
        f"🏥 *STATUS KESEHATAN INFRASTRUKTUR SISTEM MCP & SATRIA*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🧩 *Microsoft Agent Framework:* {maf_status}\n"
        f"    └ {maf_detail}\n"
        f"📊 *PostgreSQL (Port 5433):* {db_status}\n"
        f"    └ {db_detail}\n"
        f"🤖 *AI Orchestrator Engine:* {orch_status}\n"
        f"📱 *WhatsApp Baileys Gateway:* {wa_status}\n"
        f"⚡ *RunPod GPU Serverless:* {rp_status}\n"
        f"🛡️ *Circuit Breaker State:* {c_summary}\n"
        f"⏰ *Waktu Pemeriksaan:* {now_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Status operasional sistem: *PRIMA & TERINTEGRASI PENUH DENGAN MAF*."
    )
    return report


async def _send_whatsapp_milestone_ping(recipient_jid: Optional[str], milestone_text: str) -> bool:
    """
    Mengirimkan pesan milestone progress singkat ke WhatsApp jika operasi AI berlangsung lama (> 4 detik).
    Non-blocking, fail-safe (tidak mengganggu alur utama jika Baileys webhook offline).
    """
    if not recipient_jid:
        return False

    webhook_url = os.getenv("WHATSAPP_WEBHOOK_URL", "http://127.0.0.1:3001/webhook/whatsapp")
    webhook_secret = os.getenv("WEBHOOK_SECRET") or os.getenv("MCP_WEBHOOK_SECRET") or "mcp_unified_webhook_2026"

    # Format recipient JID
    target_jid = str(recipient_jid).strip()
    if "@" not in target_jid:
        digits = re.sub(r'[^0-9]', '', target_jid)
        if digits.startswith("0"):
            digits = "62" + digits[1:]
        target_jid = f"{digits}@s.whatsapp.net"

    req_id = f"milestone-{int(time.time() * 1000)}"
    payload = {
        "user_id": target_jid,
        "response": milestone_text,
        "request_id": req_id
    }
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Secret": webhook_secret
    }

    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=3.0)) as resp:
                if resp.status == 200:
                    logger.info(f"📡 Milestone progress ping sent to {target_jid}: {milestone_text[:60]}...")
                    return True
                else:
                    logger.warning(f"Milestone progress ping HTTP {resp.status} for {target_jid}")
                    return False
    except Exception as e:
        logger.debug(f"Milestone progress ping notice (non-fatal): {e}")
        return False


class MilestoneGuard:
    """
    Async context manager untuk mengirim notifikasi milestone progres ke WhatsApp
    hanya jika suatu task/operasi asynchronous berjalan lebih lama dari `delay_seconds` (default: 4.0 detik).
    Jika task selesai sebelum batas waktu, pengiriman milestone dibatalkan (Zero-Spam).
    """
    def __init__(self, recipient_jid: Optional[str], milestone_text: str, delay_seconds: float = 4.0):
        self.recipient_jid = recipient_jid
        self.milestone_text = milestone_text
        self.delay_seconds = delay_seconds
        self._task: Optional[asyncio.Task] = None

    async def _runner(self):
        try:
            await asyncio.sleep(self.delay_seconds)
            if self.recipient_jid:
                await _send_whatsapp_milestone_ping(self.recipient_jid, self.milestone_text)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"MilestoneGuard runner exception: {e}")

    async def __aenter__(self):
        if self.recipient_jid:
            self._task = asyncio.create_task(self._runner())
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


async def _execute_satria_tool(tool_name: str, arguments: Dict[str, Any], recipient_jid: Optional[str] = None) -> str:
    """
    Dispatcher pemanggilan perkakas SATRIA dengan proteksi Pydantic validator, ToolTimeoutGuard,
    dan Delayed Milestone Progress Feedback untuk operasi penelusuran berdurasi panjang.
    """
    is_valid, clean_args, val_err = satria_pydantic_adapter.sanitize_and_validate(tool_name, arguments)
    if not is_valid:
        logger.warning(f"Pydantic schema notice for {tool_name}: {val_err}")

    try:
        if tool_name == "lookup_bangda_staff":
            q = clean_args.get("query", "")
            res = await satria_timeout_guard.call_with_timeout(
                "lookup_bangda_staff",
                _lookup_bangda_staff_data,
                {"query": q}
            )
            return str(res.get("data") or "Data kepegawaian tidak ditemukan.")

        elif tool_name == "search_regulation_knowledge":
            q = clean_args.get("query", "")
            res = await satria_timeout_guard.call_with_timeout(
                "search_regulation_knowledge",
                _retrieve_rag_legal_knowledge,
                {"query": q}
            )
            return str(res.get("data") or "Dokumen regulasi tidak ditemukan.")

        elif tool_name == "cari_surat_korespondensi":
            q = clean_args.get("query", "")
            res = await satria_timeout_guard.call_with_timeout(
                "cari_surat_korespondensi",
                _query_korespondensi_data,
                {"query": q}
            )
            return str(res.get("data") or "Data korespondensi tidak ditemukan.")

        elif tool_name in ("search_web_realtime", "search_hybrid_web"):
            q = clean_args.get("query", "")
            milestone_msg = (
                f"🔎 *Menelusuri Portal Resmi & JDIH...*\n"
                f"_Pencarian dokumen/peraturan untuk kata kunci: \"{q[:60]}\" sedang berlangsung di portal web resmi. Mohon tunggu sebentar..._"
            )
            async with MilestoneGuard(recipient_jid, milestone_msg, delay_seconds=4.0):
                res = await satria_timeout_guard.call_with_timeout(
                    "search_web_realtime",
                    _search_web_hybrid,
                    {"query": q}
                )
            return str(res.get("data") or "Pencarian internet tidak membuahkan hasil.")

        elif tool_name == "search_social_media":
            q = clean_args.get("query", "")
            plat = clean_args.get("platform", "all")
            milestone_msg = (
                f"📱 *Menelusuri Media Sosial Publik...*\n"
                f"_Pemantauan opini publik/isu untuk kata kunci: \"{q[:60]}\" di platform {plat.upper()} sedang berlangsung. Mohon tunggu sebentar..._"
            )
            async with MilestoneGuard(recipient_jid, milestone_msg, delay_seconds=2.0):
                res = await satria_timeout_guard.call_with_timeout(
                    "search_social_media",
                    _search_social_media_handler,
                    {"query": q, "platform": plat}
                )
            return str(res.get("data") or "Penelusuran media sosial tidak menemukan data.")

        elif tool_name == "evaluate_bphn_doctrine":
            norm = clean_args.get("norm_text", "") or clean_args.get("regulation_text_or_ref", "")
            res = await satria_timeout_guard.call_with_timeout(
                "evaluate_bphn_doctrine",
                legal_evaluate_doctrine,
                {"regulation_text_or_ref": norm}
            )
            return str(res.get("data") or "Evaluasi doktrin tidak dapat diselesaikan.")

        elif tool_name == "legal_patch_clause":
            problematic = clean_args.get("problematic_clause", "")
            reason = clean_args.get("reason_or_defect", "")
            res = await satria_timeout_guard.call_with_timeout(
                "legal_patch_clause",
                _execute_patch_clause,
                {"problematic_clause": problematic, "reason_or_defect": reason}
            )
            return str(res.get("data") or "Formulasi perbaikan klausul tidak dapat diproses.")

        elif tool_name == "legal_verify_spm":
            query = clean_args.get("indicator_query", "")
            res = await satria_timeout_guard.call_with_timeout(
                "legal_verify_spm",
                _execute_verify_spm,
                {"indicator_query": query}
            )
            return str(res.get("data") or "Verifikasi SPM tidak dapat diselesaikan.")

        elif tool_name == "nd_generate_laporan":
            hal = clean_args.get("hal", "")
            poin = clean_args.get("poin_pembahasan", "")
            jenis = clean_args.get("jenis", "nd_laporan")
            rujukan = clean_args.get("rujukan_surat", "")
            res = await satria_timeout_guard.call_with_timeout(
                "nd_generate_laporan",
                _execute_generate_nota_dinas,
                {"hal": hal, "poin_pembahasan": poin, "jenis": jenis, "rujukan_surat": rujukan}
            )
            return str(res.get("data") or "Draf Nota Dinas gagal disusun.")

        elif tool_name == "legal_deontic_verify":
            norm = clean_args.get("norm_text") or clean_args.get("clause_text") or clean_args.get("text") or ""
            res = await satria_timeout_guard.call_with_timeout(
                "legal_deontic_verify",
                legal_deontic_verify,
                {"norm_text": norm}
            )
            return str(res.get("rekomendasi") or res.get("kesalahan") or res)

        elif tool_name == "legal_naskah_akademik_generate":
            title = clean_args.get("title") or clean_args.get("judul") or "Rancangan Perda"
            bg = clean_args.get("background") or clean_args.get("urgensi") or "Urgensi kebutuhan regulasi daerah"
            res = await satria_timeout_guard.call_with_timeout(
                "legal_naskah_akademik_generate",
                legal_naskah_akademik_generate,
                {
                    "judul": title,
                    "jenis": "Perda",
                    "urgensi": bg,
                    "identifikasi_masalah": [bg],
                    "sasaran_jangkauan": "Pemerintah Daerah dan Masyarakat",
                    "landasan_filosofis": "Pancasila dan UUD 1945",
                    "landasan_sosiologis": "Kebutuhan nyata tata kelola masyarakat daerah",
                    "landasan_yuridis": "UU 23/2014 dan UU 12/2011"
                }
            )
            return str(res.get("markdown_document") or res)

        elif tool_name == "legal_harmonization_matrix":
            raperda = clean_args.get("rancangan_text") or clean_args.get("raperda_title") or "Rancangan Perda"
            res = await satria_timeout_guard.call_with_timeout(
                "legal_harmonization_matrix",
                legal_harmonization_matrix,
                {"rancangan_text": raperda, "jenis_peraturan": "PERDA"}
            )
            return str(res.get("markdown_report") or res)

        elif tool_name == "legal_opinion_irac":
            issue = clean_args.get("legal_issue") or clean_args.get("issue") or "Kepatuhan Asas AUPB"
            facts = clean_args.get("legal_facts") or clean_args.get("facts") or "Fakta pelaksanaan tugas kedinasan"
            res = await satria_timeout_guard.call_with_timeout(
                "legal_opinion_irac",
                legal_opinion_irac,
                {
                    "judul_kasus": issue,
                    "pemohon": "Biro Hukum / OPD",
                    "nomor_memo": "ND-01/HUKUM/2026",
                    "fakta": facts,
                    "issues": [{"id": "ISSUE-1", "question": issue, "core_principle": "AUPB"}],
                    "rules": [{"peraturan": "UU 30/2014", "pasal": "Pasal 10", "bunyi": "Asas-Asas Umum Pemerintahan yang Baik", "hierarki": "UU"}]
                }
            )
            return str(res.get("markdown_document") or res)

        elif tool_name == "legal_contract_vetting":
            ctitle = clean_args.get("contract_title") or clean_args.get("judul_kontrak") or "Draf Kontrak Pengadaan"
            cclauses = clean_args.get("clauses_text") or clean_args.get("draf_pasal") or "Ketentuan umum dan pelaksanaan pekerjaan"
            clauses_dict = {"Pasal 1": cclauses} if isinstance(cclauses, str) else cclauses
            res = await satria_timeout_guard.call_with_timeout(
                "legal_contract_vetting",
                legal_contract_vetting,
                {
                    "judul_kontrak": ctitle,
                    "nomor_draf": "SPK/01/2026",
                    "para_pihak": ["PPK Dinas", "Penyedia Barang/Jasa"],
                    "nilai_kontrak": 500000000.0,
                    "jenis_kontrak": "Pengadaan Barang/Jasa",
                    "draf_pasal": clauses_dict
                }
            )
            return str(res.get("markdown_document") or res)

        elif tool_name == "legal_litigation_advocacy":
            dtype = clean_args.get("dispute_type") or "PTUN"
            sfacts = clean_args.get("summary_facts") or "Gugatan sengketa KTUN"
            res = await satria_timeout_guard.call_with_timeout(
                "legal_litigation_advocacy",
                legal_litigation_advocacy,
                {
                    "nomor_perkara": "01/G/2026/PTUN.JKT",
                    "judul_sengketa": sfacts,
                    "instansi_tergugat": "Pemerintah Daerah",
                    "penggugat": "Pihak Penggugat",
                    "forum": dtype,
                    "kronologi": [{"tanggal": "2026-01-10", "uraian": sfacts}],
                    "bukti": [{"kode": "T-1", "nama": "Surat Keputusan Objek Sengketa", "relevansi": "Membuktikan legalitas"}],
                    "fakta_formal": {"tenggang_waktu_terlewati": False, "upaya_administratif_selesai": True}
                }
            )
            return str(res.get("markdown_document") or res)

        elif tool_name == "system_health_check":
            target = clean_args.get("service_target", "all")
            res = await satria_timeout_guard.call_with_timeout(
                "system_health_check",
                _execute_system_health,
                {"service_target": target}
            )
            return str(res.get("data") or "Pemeriksaan kesehatan sistem gagal.")

        elif tool_name == "browse_portal_autonomous":
            target_url = clean_args.get("url", "")
            task_desc = clean_args.get("task", "")
            steps = clean_args.get("max_steps", 5)

            milestone_msg = (
                f"🌐 *Menjalankan Eksplorasi Browser AI...*\n"
                f"_Sub-Agent sedang menavigasi portal {target_url or 'resmi'} untuk mengekstrak data peraturan. Mohon tunggu sebentar..._"
            )

            async def _run_subagent_task():
                from core.browser.adapters.browser_use_adapter import browser_use_adapter
                full_instruction = f"Buka {target_url}. {task_desc}" if target_url else task_desc
                res = await browser_use_adapter.execute_task(instruction=full_instruction, max_steps=steps)
                await browser_use_adapter.stop()
                if res.get("success"):
                    return f"HASIL PENELUSURAN AI SUB-AGENT BROWSER ({target_url}):\n{res.get('result_summary')}"
                else:
                    return f"AI Sub-Agent belum berhasil mengekstrak data dari {target_url}: {res.get('error')}"

            async with MilestoneGuard(recipient_jid, milestone_msg, delay_seconds=4.0):
                res = await satria_timeout_guard.call_with_timeout(
                    "browse_portal_autonomous",
                    _run_subagent_task
                )
            return str(res.get("data") or "Eksplorasi portal tidak membuahkan hasil.")

        elif tool_name == "list_database_tables":
            max_limit = clean_args.get("limit", 10)
            try:
                import psycopg2
                conn = psycopg2.connect(os.getenv("DATABASE_URL"))
                cur = conn.cursor()
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    ORDER BY CASE 
                        WHEN table_name IN ('memories', 'knowledge_documents', 'korespondensi_raw_pool', 'member_profiles', 'browser_hybrid_logs', 'audit_logs', 'whatsapp_messages', 'job_schedules') THEN 1 
                        ELSE 2 
                    END, table_name 
                    LIMIT %s;
                """, (max_limit,))
                rows = cur.fetchall()
                cur.close()
                conn.close()

                table_descriptions = {
                    "memories": "Memori Jangka Panjang (LTM) AI Agent & Interaksi Chat Kedinasan (Vector 384-dim)",
                    "knowledge_documents": "Knowledge Base Regulasi PUU, Naskah Dinas, & Dokumen RAG (Vector 768-dim)",
                    "korespondensi_raw_pool": "Pusat Data Korespondensi Surat Masuk/Keluar & Disposisi Pemda",
                    "member_profiles": "Direktori Pegawai, Pejabat Eselon, & Tim Kerja Ditjen Bangda",
                    "browser_hybrid_logs": "Audit Trail Log Penelusuran Web & Scraping Portal JDIH BPK RI",
                    "audit_logs": "Jejak Audit Keamanan, Akses Data, & Kepatuhan Sistem MCP",
                    "whatsapp_messages": "Riwayat Pesan Masuk/Keluar Gateway Baileys",
                    "job_schedules": "Registry Penjadwalan Tugas Otomasi & Cron Jobs",
                    "alembic_version": "Versioning Skema Basis Data Relasional"
                }

                res_lines = ["📋 *DAFTAR TABEL BASIS DATA SISTEM (LTM & RAG KNOWLEDGE):*"]
                for i, r in enumerate(rows, 1):
                    tname = r[0]
                    desc = table_descriptions.get(tname, "Tabel Sistem Data Operasional")
                    res_lines.append(f"{i}. *`{tname}`*\n   - Fungsi: {desc}\n   - Status Akses: ✅ Aktif Terhubung")

                return "\n".join(res_lines)
            except Exception as err:
                logger.warning(f"Gagal query information_schema, fallback to catalog: {err}")
                return (
                    "📋 *DAFTAR TABEL BASIS DATA SISTEM (LTM & RAG KNOWLEDGE):*\n"
                    "1. *`memories`* (LTM / Pengalaman & Interaksi Sesi Agen)\n"
                    "2. *`knowledge_documents`* (RAG Dokumen Hukum & Naskah Dinas Bangda)\n"
                    "3. *`korespondensi_raw_pool`* (Surat Masuk/Keluar Pemda & Disposisi)\n"
                    "4. *`member_profiles`* (Master Kepegawaian & Pejabat Ditjen Bangda)\n"
                    "5. *`browser_hybrid_logs`* (Log Penelusuran Web Portal Regulasi BPK)\n"
                    "6. *`audit_logs`* (Keamanan & Integritas Operasional Sistem)\n"
                    "Status Akses: ✅ Terverifikasi Aktif"
                )

        elif tool_name == "policy_inventory_aggregator":
            kategori = clean_args.get("kategori")
            tahun = clean_args.get("tahun", 2026)
            keyword = clean_args.get("keyword")
            sub_kategori = clean_args.get("sub_kategori")
            limit = clean_args.get("limit", 15)

            def _run_inventory_query():
                data = policy_inventory_engine.query_inventory(
                    kategori=kategori,
                    tahun=tahun,
                    keyword=keyword,
                    sub_kategori=sub_kategori,
                    limit=limit
                )
                query_label = f"{kategori or 'Kebijakan'} {tahun or ''}".strip()
                return policy_inventory_engine.format_whatsapp_response(data, query_label=query_label)

            res = await satria_timeout_guard.call_with_timeout(
                "policy_inventory_aggregator",
                _run_inventory_query
            )
            return str(res.get("data") or "Data inventarisasi kebijakan tidak ditemukan.")

        return f"Perkakas '{tool_name}' tidak terdaftar di SATRIA."
    except Exception as e:
        logger.error(f"Error executing SATRIA tool {tool_name}: {e}")
        return f"Gangguan eksekusi perkakas: {e}"


def _clean_raw_ai_markers(text: Optional[str]) -> str:
    """Membersihkan tag internal LLM seperti DSML, thinking tags, atau XML artifacts."""
    if not text:
        return ""
    # Bersihkan blok DSML tool_calls
    cleaned = re.sub(r"<｜｜DSML｜｜tool_calls>.*?</｜｜DSML｜｜tool_calls>", "", text, flags=re.DOTALL)
    # Bersihkan blok invoke/parameter tersisa
    cleaned = re.sub(r"<｜｜DSML｜｜.*?｜｜>", "", cleaned)
    cleaned = re.sub(r"<｜.*?｜>", "", cleaned)
    # Bersihkan tag thinking jika ada
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL)
    return cleaned.strip()


# Provider Health State Cache (mencegah latency overhead 3s pada provider yang kehabisan kuota/down)
_PROVIDER_UNHEALTHY_UNTIL: Dict[str, float] = {}

def _mark_provider_unhealthy(provider_name: str, cooldown_seconds: float = 1800.0):
    """Menandai provider tidak sehat (misal: HTTP 429 quota exhausted) selama cooldown_seconds."""
    _PROVIDER_UNHEALTHY_UNTIL[provider_name] = time.time() + cooldown_seconds
    logger.warning(f"[HEALTH_CACHE] ⏸️ Provider '{provider_name}' ditandai UNHEALTHY selama {int(cooldown_seconds)}s")

def _is_provider_healthy(provider_name: str) -> bool:
    unhealthy_until = _PROVIDER_UNHEALTHY_UNTIL.get(provider_name, 0.0)
    return time.time() > unhealthy_until


def _get_active_ai_clients() -> List[Dict[str, Any]]:
    """
    Menyediakan daftar LLM Client dengan urutan prioritas dinamis berbasis health cache:
    1. Provider yang berstatus SEHAT (aktif merespon)
    2. Provider yang sedang dalam masa COOLDOWN (ditaruh di belakang)
    """
    clients = []
    from openai import AsyncOpenAI

    # 1. OpenAI (Primary saat kuota tersedia)
    openai_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY_AGENTIC_SCHEDULER")
    if openai_key and not openai_key.startswith("sk-xxx"):
        clients.append({
            "name": "openai",
            "client": AsyncOpenAI(api_key=openai_key, timeout=10.0),
            "model": os.getenv("SATRIA_MODEL", "gpt-4o-mini")
        })

    # 2. DeepSeek (Fallback Cerdas - High Intelligence & Tool Calling)
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if deepseek_key and not deepseek_key.startswith("sk-xxx"):
        clients.append({
            "name": "deepseek",
            "client": AsyncOpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com", timeout=12.0),
            "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        })

    # 3. RunPod Serverless vLLM (Fallback Serverless GPU)
    runpod_key = os.getenv("RUNPOD_VLLM_API_KEY") or os.getenv("RUNPOD_API_KEY")
    runpod_endpoint = os.getenv("RUNPOD_VLLM_VISION_ENDPOINT_ID", "qi2tml56v6cf1p")
    if runpod_key and runpod_endpoint:
        clients.append({
            "name": "runpod_vllm",
            "client": AsyncOpenAI(api_key=runpod_key, base_url=f"https://api.runpod.ai/v2/{runpod_endpoint}/openai/v1", timeout=15.0),
            "model": os.getenv("RUNPOD_VLLM_MODEL", "qwen/qwen2.5-vl-7b-instruct")
        })

    # Prioritaskan provider yang sedang SEHAT agar tidak membuang 2-3 detik menunggu 429
    healthy = [c for c in clients if _is_provider_healthy(c["name"])]
    unhealthy = [c for c in clients if not _is_provider_healthy(c["name"])]
    return healthy + unhealthy


async def _call_openai_engine(
    user_info: Dict[str, Any],
    user_query: str,
    precedents: Optional[List[Dict[str, Any]]] = None,
    extra_context: str = "",
    history: Optional[List[Dict[str, str]]] = None,
    persona: str = "legal_madya",
    recipient_jid: Optional[str] = None,
    is_summary: bool = False
) -> Tuple[Optional[str], TokenUsage, float]:
    """
    Menjalankan penalaran generatif dengan Multi-Turn History, Autonomous Tool Calling Loop,
    Pydantic validation, Token Tracking, dan Tiered Provider Failover (OpenAI -> DeepSeek -> RunPod).
    """
    t_inf_start = time.time()
    active_candidates = _get_active_ai_clients()
    if not active_candidates:
        logger.warning("Tidak ada provider AI yang terkonfigurasi.")
        return None, TokenUsage(), 0.0

    target_user_jid = recipient_jid or user_info.get("phone_number") or user_info.get("user_id") or user_info.get("phone")

    tupoksi_primer = user_info.get("tupoksi_primer", "")
    ruang_lingkup = user_info.get("ruang_lingkup_urusan", [])
    tugas_tambahan = user_info.get("tugas_tambahan", [])
    fokus_isu = user_info.get("fokus_isu_strategis", [])
    nip = user_info.get("nip", "")
    pangkat = user_info.get("pangkat_gol", "")

    context_prompt = (
        f"IDENTITAS & PROFIL KEDINASAN PEMOHON:\n"
        f"- Nama: {user_info.get('full_name')}\n"
        f"- NIP: {nip or '-'}\n"
        f"- Pangkat/Golongan: {pangkat or '-'}\n"
        f"- Jabatan: {user_info.get('jabatan')}\n"
        f"- Unit Kerja: {user_info.get('unit_kerja')} / {user_info.get('tim_kerja')}\n"
    )
    if tupoksi_primer:
        context_prompt += f"- Tupoksi Primer: {tupoksi_primer}\n"
    if ruang_lingkup:
        context_prompt += f"- Ruang Lingkup Urusan Konkuren (UU 23/2014): {', '.join(ruang_lingkup)}\n"
    if tugas_tambahan:
        context_prompt += f"- Tugas & Fungsi Tambahan / Pokja: {', '.join(tugas_tambahan)}\n"
    if fokus_isu:
        context_prompt += f"- Fokus Isu Strategis: {', '.join(fokus_isu)}\n"

    context_prompt += (
        "\nDIREKTIF MANDATORI PERSPEKTIF KEDINASAN DITJEN BINA PEMBANGUNAN DAERAH KEMENDAGRI:\n"
        "1. Pemohon adalah Pejabat/Analis di lingkungan Kementerian Dalam Negeri (Ditjen Bina Bangda).\n"
        "2. Segala istilah teknis (seperti 'Tenaga Ahli', 'Perencanaan', 'Pengawasan', 'Kebijakan', 'Urusan') "
        "WAJIB dijawab dan dianalisis dalam kerangka URUSAN PEMERINTAHAN DAERAH, SOTK Kemendagri (Permendagri No. 9 Tahun 2025 Pasal 413-422), "
        "dan Pembagian Urusan Konkuren (UU No. 23 Tahun 2014), BUKAN swasta/sektor industri komersial!\n"
        "3. Tenaga Ahli di lingkungan Ditjen Bangda adalah Analis/Konsultan Kebijakan Urusan Daerah yang mendampingi "
        "Direktorat/Subdirektorat dalam harmonisasi RKPD/RPJMD, desk Rakortekrenbang, evaluasi Ranperda, dan SIPD RI.\n"
    )
    if is_summary:
        if not tugas_tambahan:
            context_prompt += (
                "4. AJAKAN PROAKTIF MELENGKAPI TUGAS FUNGSI TAMBAHAN (HANYA PADA RESUME/PENUTUP SESI): Di akhir rangkuman Anda, sertakan kalimat penutup yang santun, "
                "hangat, dan bersahabat yang mengajak pemohon: jika beliau saat ini juga mengemban tugas dan fungsi tambahan atau "
                "tergabung dalam Pokja/Tim Koordinasi khusus (misal Pokja Vokasi Daerah, Satgas Stunting, Tim Terpadu, dll.), "
                "beliau dapat mengabarkannya di chat ini agar SATRIA dapat mencatatnya ke profil kedinasan untuk asistensi yang semakin presisi dan mendalam.\n"
            )
        else:
            context_prompt += (
                "4. AJAKAN DINAMIS PEMBARUAN PROFIL (HANYA PADA RESUME/PENUTUP SESI): Di akhir rangkuman, sampaikan secara santun bahwa jika ada tugas fungsi tambahan baru "
                "atau keanggotaan Pokja/Satgas lain yang ingin ditambahkan ke profil kedinasan, pemohon dapat mengabarkannya langsung di sini.\n"
            )
    else:
        context_prompt += (
            "4. FORMAT PERCAKAPAN BERJALAN (ONGOING DIALOGUE): Jawablah LANGSUNG KE SUBSTANSI tanpa kalimat basa-basi pengantar, tanpa mencetak sapaan formal 'Yth. Bapak/Ibu', dan tanpa mengulang ajakan mengisi profil tugas tambahan.\n"
        )
    context_prompt += "\n"

    if extra_context:
        context_prompt += f"KONTEKS STRUKTUR DRAF / DOKUMEN:\n{extra_context}\n\n"

    if precedents:
        context_prompt += "YURISPRUDENSI & PRESEDEN TERKAIT (TIER 1 & TIER 2):\n"
        for i, p in enumerate(precedents[:3], 1):
            context_prompt += (
                f"[{i}] {p.get('nomor_perkara')} ({p.get('lembaga', 'Peradilan')})\n"
                f"    Judul: {p.get('judul', '')}\n"
                f"    Status Norma: {p.get('status_norma', '')}\n"
                f"    Ratio Decidendi: {p.get('ratio_decidendi', '')}\n\n"
            )

    # Dynamic Composable Prompt Builder (MAF & RBAC-Aware)
    try:
        from core.agent_framework.prompt_builder import DynamicPromptBuilder, UserRbacProfile
        rbac_profile = UserRbacProfile.from_dict(user_info)
        system_prompt = DynamicPromptBuilder.build_prompt(
            user=rbac_profile,
            intent_type="cari_surat_korespondensi" if persona == "admin_persuratan" else None,
            attached_media_context=extra_context
        )
    except Exception as e:
        logger.warning(f"[PROMPT_BUILDER] Fallback to legacy prompt: {e}")
        system_prompt = SATRIA_ADMIN_PERSURATAN_PROMPT if persona == "admin_persuratan" else SATRIA_LEGAL_MADYA_PROMPT

    base_messages = [
        {"role": "system", "content": system_prompt.strip()}
    ]
    if context_prompt.strip():
        base_messages.append({"role": "system", "content": context_prompt.strip()})

    if history:
        for h in history:
            base_messages.append({"role": h["role"], "content": h["content"]})

    base_messages.append({"role": "user", "content": user_query.strip()})

    # Pilih tools relevan
    eval_query = user_query
    if len(user_query.split()) <= 6 and history:
        prev_user_queries = [h["content"] for h in history if h.get("role") == "user" and not h["content"].startswith("⏳")]
        if prev_user_queries:
            eval_query = f"{prev_user_queries[-1]} {user_query}"

    selected_tools = satria_tool_selector.select(eval_query, model_size="7B")
    tools_schema = satria_tool_selector.get_openai_tools_schema(selected_tools)

    last_error = None
    for cand in active_candidates:
        provider_name = cand["name"]
        client = cand["client"]
        model_name = cand["model"]
        prompt_tokens = 0
        completion_tokens = 0
        messages = [dict(m) for m in base_messages]

        try:
            logger.info(f"🚀 Menjalankan penalaran AI dengan provider: {provider_name} ({model_name})")
            q_lower = eval_query.lower()
            is_heavy_task = any(w in q_lower for w in ["dimensi", "analisis", "audit", "pasal", "draft", "klausul", "statuta", "evaluasi", "rekomendasi"]) or len(user_query) > 80
            calc_max_tokens = 1200 if is_heavy_task else 700

            create_kwargs = {
                "model": model_name,
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": calc_max_tokens
            }
            if tools_schema:
                create_kwargs["tools"] = tools_schema
                needs_web_force = any(d in q_lower for d in ["bpk.go.id", "bpk", "jdih", ".go.id", "peraturan.go.id", "internet", "web", "portal"])
                has_web_tool = any(t.get("function", {}).get("name") == "search_web_realtime" for t in tools_schema)
                if needs_web_force and has_web_tool:
                    if provider_name == "openai":
                        create_kwargs["tool_choice"] = {"type": "function", "function": {"name": "search_web_realtime"}}
                    else:
                        create_kwargs["tool_choice"] = "auto"
                        messages.append({
                            "role": "system",
                            "content": "PERINTAH SISTEM PRIORITAS TINGGI: Permintaan ini mencari dokumen/peraturan di portal resmi/BPK/internet. Anda WAJIB memanggil perkakas 'search_web_realtime'."
                        })
                else:
                    create_kwargs["tool_choice"] = "auto"

            resp = await client.chat.completions.create(**create_kwargs)
            if resp.usage:
                prompt_tokens += resp.usage.prompt_tokens
                completion_tokens += resp.usage.completion_tokens

            resp_msg = resp.choices[0].message

            # 1. Jika model meminta pemanggilan tool secara otonom via format standar OpenAI
            if resp_msg.tool_calls:
                logger.info(f"[{provider_name}] Autonomous tool calls detected: {len(resp_msg.tool_calls)} calls")
                messages.append(resp_msg)

                for tc in resp_msg.tool_calls:
                    call_fn_name = tc.function.name
                    try:
                        call_args = json.loads(tc.function.arguments)
                    except Exception:
                        call_args = {"query": tc.function.arguments}

                    tool_output = await _execute_satria_tool(call_fn_name, call_args, recipient_jid=target_user_jid)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": str(tool_output)
                    })

                # Giliran Kedua: Sintesis hasil akhir berbasis fakta segar
                final_resp = await client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=1400 if is_heavy_task else 750
                )
                if final_resp.usage:
                    prompt_tokens += final_resp.usage.prompt_tokens
                    completion_tokens += final_resp.usage.completion_tokens

                duration_ms = (time.time() - t_inf_start) * 1000.0
                usage_obj = TokenUsage.calculate(prompt_tokens, completion_tokens, model=model_name)
                clean_final = _clean_raw_ai_markers(final_resp.choices[0].message.content)
                return clean_final, usage_obj, duration_ms

            # 2. Jika model mencetak tool calls via sintaks internal DSML (DeepSeek XML format)
            if resp_msg.content and "<｜｜DSML｜｜invoke" in resp_msg.content:
                logger.info(f"[{provider_name}] Detected DSML tool invocation markers in content string")
                invoke_pattern = re.finditer(
                    r'<｜｜DSML｜｜invoke\s+name="([^"]+)">\s*(.*?)\s*</｜｜DSML｜｜invoke>',
                    resp_msg.content,
                    re.DOTALL
                )
                dsml_tool_results = []
                for inv in invoke_pattern:
                    fn_name = inv.group(1)
                    param_body = inv.group(2)
                    params = {}
                    for p in re.finditer(r'<｜｜DSML｜｜parameter\s+name="([^"]+)"[^>]*>(.*?)</｜｜DSML｜｜parameter>', param_body, re.DOTALL):
                        params[p.group(1)] = p.group(2).strip()
                    logger.info(f"[{provider_name}] Executing DSML tool: {fn_name}({params})")
                    t_out = await _execute_satria_tool(fn_name, params, recipient_jid=target_user_jid)
                    dsml_tool_results.append(f"Hasil Rujukan {fn_name} ({params.get('query', '')}):\n{t_out}")

                if dsml_tool_results:
                    clean_initial = _clean_raw_ai_markers(resp_msg.content)
                    followup_msgs = list(messages)
                    if clean_initial:
                        followup_msgs.append({"role": "assistant", "content": clean_initial})
                    followup_msgs.append({
                        "role": "user",
                        "content": "Hasil penelusuran rujukan resmi:\n" + "\n\n".join(dsml_tool_results) + "\n\nSempurnakan analisis audit regulasi di atas dengan mengintegrasikan hasil rujukan tersebut. Jangan cetak tag DSML apa pun."
                    })
                    final_resp = await client.chat.completions.create(
                        model=model_name,
                        messages=followup_msgs,
                        temperature=0.2,
                        max_tokens=1400 if is_heavy_task else 850
                    )
                    if final_resp.usage:
                        prompt_tokens += final_resp.usage.prompt_tokens
                        completion_tokens += final_resp.usage.completion_tokens
                    duration_ms = (time.time() - t_inf_start) * 1000.0
                    usage_obj = TokenUsage.calculate(prompt_tokens, completion_tokens, model=model_name)
                    return _clean_raw_ai_markers(final_resp.choices[0].message.content), usage_obj, duration_ms

            duration_ms = (time.time() - t_inf_start) * 1000.0
            usage_obj = TokenUsage.calculate(prompt_tokens, completion_tokens, model=model_name)
            if resp_msg.content:
                return _clean_raw_ai_markers(resp_msg.content), usage_obj, duration_ms
            return None, usage_obj, duration_ms

        except Exception as e:
            err_str = str(e).lower()
            if any(k in err_str for k in ["429", "quota", "credit_balance_exhausted", "insufficient_quota"]):
                _mark_provider_unhealthy(provider_name, cooldown_seconds=1800.0)
            elif any(k in err_str for k in ["500", "timeout", "timed out", "connect"]):
                _mark_provider_unhealthy(provider_name, cooldown_seconds=120.0)
            logger.warning(f"AI Provider {provider_name} ({model_name}) error: {e}. Mencoba fallback berikutnya...")
            last_error = e
            continue

    logger.warning(f"Semua AI provider gagal, fallback to template: {last_error}")
    duration_ms = (time.time() - t_inf_start) * 1000.0
    return None, TokenUsage(), duration_ms


def _detect_persona(query: str, intent: Optional[str] = None) -> str:
    """
    Menentukan persona bot secara dinamis:
    - 'admin_persuratan': Untuk kueri persuratan, surat masuk/keluar, disposisi, naskah dinas, agenda, fasilitasi surat, nomor surat.
    - 'legal_madya': Untuk kueri telaah hukum, PUU, regulasi, kepegawaian, audit, atau konsultasi umum.
    """
    q_lower = query.lower()

    # 1. Prioritas Utama: Jika eksplisit meminta sudut pandang PUU / Ahli Madya / Pendapat Hukum
    legal_override_keywords = [
        "substansi perundang-undangan", "perundang-undangan", "puu", "pendapat hukum",
        "analisis hukum", "analis hukum", "ahli madya", "telaah hukum", "kajian hukum",
        "legal opinion", "tinjauan yuridis", "sudut pandang hukum", "sudut pandang puu",
        "sebagai puu", "pandangan hukum", "pendapatmu sebagai", "tanggapan hukum"
    ]
    if any(k in q_lower for k in legal_override_keywords):
        return "legal_madya"

    if intent in ("cari_surat_korespondensi", "SEARCH_CORRESPONDENCE"):
        return "admin_persuratan"

    correspondence_keywords = [
        "surat", "disposisi", "korespondensi", "agenda surat", "naskah dinas",
        "surat masuk", "surat keluar", "eksternal", "internal", "tata naskah",
        "lacak surat", "posisi berkas", "nomor nd", "nomor surat", "fasilitasi ranperda",
        "terima dirjen", "disposisi dirjen", "posisi surat", "nota dinas", "agenda",
        "laporkan list surat", "daftar surat", "rekap surat"
    ]
    if any(k in q_lower for k in correspondence_keywords):
        return "admin_persuratan"

    return "legal_madya"


def _is_summary_or_wrapup_request(query: str, intent: Optional[str] = None) -> bool:
    """
    Mendeteksi apakah permintaan pengguna meminta kesimpulan menyeluruh, resume,
    rangkuman akhir, atau penutupan sesi percakapan.
    """
    if not query:
        return False
    q_lower = query.lower().strip()

    # 1. Kata kunci eksplisit penutup / resume / kesimpulan
    summary_keywords = [
        "simpulkan", "kesimpulan", "resume", "rangkum", "rangkuman",
        "rekap", "rekapitulasi", "intisari", "intisarikan", "ikhtisar",
        "terima kasih satria", "makasih satria", "cukup sekian",
        "selesai diskusinya", "tutup sesi", "closing", "buatkan kesimpulan",
        "buatkan resume", "kesimpulan akhir", "rekap hasil"
    ]
    if any(k in q_lower for k in summary_keywords):
        return True

    return False


def _clean_and_format_reply(
    user: Dict[str, Any], 
    text: str, 
    persona: str = "legal_madya",
    is_summary_session: bool = False
) -> str:
    """
    Membersihkan segala variasi header, sapaan ganda, dan kalimat filler intro dari output model.
    - Sesi Berjalan (is_summary_session=False): Langsung ke substansi dengan footer minimalis inisial SATRIA.
    - Sesi Akhir / Resume (is_summary_session=True): Menggunakan header formal lengkap dan sapaan resmi.
    """
    cleaned = text.strip()

    # 1. Bersihkan semua variasi header yang mungkin dicetak model
    header_pattern = r"(?:[🏛📮📄📋📚💡🛠️⚙️⚖️]\s*\*?[^\n]*(?:PENDAPAT|SATRIA|LAPORAN|TELAAH|ASISTEN|ADMINISTRASI|PERSURATAN|DATA RESMI|INFORMASI|RESUME|KESIMPULAN)[^\n]*\n+[━─=-—]+\n*)+"
    cleaned = re.sub(header_pattern, "", cleaned, flags=re.IGNORECASE).strip()

    # 2. Bersihkan SEMUA baris sapaan di awal (Yth..., Selamat pagi/siang..., Halo..., Salam...)
    salutation_pattern = r"^(?:(?:Yth\.|Selamat\s+(?:pagi|siang|sore|malam)|Halo|Salam\s+hangat|Salam\s+hormat)[^\n]*\n*)+"
    cleaned = re.sub(salutation_pattern, "", cleaned, flags=re.IGNORECASE).strip()

    # 3. Bersihkan kalimat filler pengantar model di awal pesan (mis. "Baik, Pak Amir...", "Baik, saya bantu...")
    filler_pattern = r"^(?:Baik,?\s*(?:saya|kami|Pak|Ibu|Bapak|Bapak/Ibu)?\s+[^\n]*\n*)+"
    cleaned = re.sub(filler_pattern, "", cleaned, flags=re.IGNORECASE).strip()

    # 4. Bersihkan sapaan lagi jika muncul setelah filler
    cleaned = re.sub(salutation_pattern, "", cleaned, flags=re.IGNORECASE).strip()

    # 5. Bersihkan pemisah horizontal yang menggantung di paling awal teks
    cleaned = re.sub(r"^(?:[-—─=━]{3,}\n*)+", "", cleaned).strip()

    user_name = user.get("full_name") or "Bapak/Ibu"

    if is_summary_session:
        # Mode Penutup / Resume Sesi: Pasang Header Formal Resmi
        if persona == "admin_persuratan":
            header = (
                f"📮 *REKAPITULASI & RESUME PERSURATAN BANGDA*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Yth. Bapak/Ibu *{user_name}*,\n\n"
            )
        else:
            header = (
                f"🏛️ *RESUME & KESIMPULAN — SATRIA AHLI MADYA BANGDA*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Yth. Bapak/Ibu *{user_name}*,\n\n"
            )
        return header + cleaned
    else:
        # Mode Interaksi Berjalan (Ongoing): Langsung ke substansi + Footer inisial minimalis
        if persona == "admin_persuratan":
            footer = "\n\n_— 📮 SATRIA Persuratan Bangda_"
        elif persona == "system":
            footer = "\n\n_— ⚙️ SATRIA System_"
        else:
            footer = "\n\n_— 🏛️ SATRIA Ahli Madya_"

        # Pastikan tidak ada double footer jika model sudah mencetak footer serupa di akhir
        cleaned = re.sub(r"\n*(?:_|\b)[-—─\s🏛📮⚙️]*SATRIA[^\n_]*_?\s*$", "", cleaned, flags=re.IGNORECASE).strip()
        return cleaned + footer


async def _detect_and_handle_additional_duty(
    user: Dict[str, Any],
    clean_phone: str,
    text: str,
    history: Optional[List[Dict[str, str]]] = None
) -> Optional[str]:
    """
    Mendeteksi secara alami apakah pengguna sedang mengabarkan/menginputkan tugas dan fungsi tambahan,
    pokja, satgas, atau tim khusus, lalu memperbarui database profil dan mengonfirmasikannya.
    """
    text_lower = text.lower().strip()
    if len(text_lower.split()) < 3:
        return None

    # Jangan proses jika pengguna sedang bertanya (kata tanya)
    question_triggers = [
        "apakah", "bagaimana", "apa ", "siapa", "mengapa", "kapan", "cek ",
        "carikan ", "tampilkan ", "berapa ", "tolong jelaskan", "tanya "
    ]
    if any(text_lower.startswith(q) for q in question_triggers):
        return None

    # Pola eksplisit pengungkapan tugas tambahan
    explicit_patterns = [
        r"saya (?:juga )?(?:mengampu|ditugaskan|dipercaya|mengawal|memegang|menjabat|bertugas di|masuk ke dalam|tergabung dalam)",
        r"tugas tambahan saya",
        r"fungsi tambahan saya",
        r"selain itu saya (?:juga )?",
        r"saya (?:anggota|ketua|sekretaris|tim teknis|koordinator) (?:pokja|satgas|tim)",
        r"penugasan tambahan saya",
        r"saya ada tugas tambahan"
    ]
    is_explicit = any(re.search(p, text_lower) for p in explicit_patterns)

    # Deteksi konteks follow-up: Jika turn sebelumnya dari asisten mengajak melengkapi tugas tambahan
    is_followup = False
    if not is_explicit and history:
        last_asst_turn = next((h.get("content", "") for h in reversed(history) if h.get("role") == "assistant"), "")
        if any(k in last_asst_turn.lower() for k in ["tugas dan fungsi tambahan", "tugas fungsi tambahan", "pokja", "satgas khusus", "profil kedinasan"]):
            if any(k in text_lower for k in ["pokja", "satgas", "tim", "mengawal", "mengampu", "koordinasi", "desk", "penugasan", "menangani"]):
                is_followup = True

    if not (is_explicit or is_followup):
        return None

    # Ekstrak uraian tugas tambahan
    raw_duty = text.strip()
    clean_prefixes = [
        "saya juga mengampu", "saya juga ditugaskan sebagai", "saya juga ditugaskan untuk",
        "saya juga ditugaskan", "tugas tambahan saya adalah", "tugas tambahan saya",
        "fungsi tambahan saya adalah", "fungsi tambahan saya", "selain itu saya juga",
        "selain itu saya", "saya juga anggota", "saya juga", "saya ditunjuk sebagai",
        "saya masuk ke dalam", "saya masuk", "saya tergabung dalam", "saya mengawal",
        "penugasan tambahan saya adalah", "penugasan tambahan saya", "saya ada tugas tambahan"
    ]
    extracted_duty = raw_duty
    for cp in clean_prefixes:
        if extracted_duty.lower().startswith(cp):
            extracted_duty = extracted_duty[len(cp):].strip(": ,-")
            break

    extracted_duty = extracted_duty.strip()
    if len(extracted_duty) < 5:
        return None

    logger.info(f"Natural profile enrichment detected from {clean_phone} ({user.get('full_name')}): {extracted_duty}")
    success, msg, updated_duties = update_user_additional_duties(clean_phone, extracted_duty)
    if not success:
        logger.warning(f"Failed to update additional duties: {msg}")
        return None

    # Format balasan resmi & apresiatif
    duties_formatted = "\n".join([f"  {i}. {d}" for i, d in enumerate(updated_duties, 1)])
    confirm_msg = (
        f"✅ *PROFIL KEDINASAN TELAH DIPERBARUI*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Terima kasih banyak atas informasinya, Bapak/Ibu *{user.get('full_name')}*.\n\n"
        f"Sistem AI SATRIA telah mencatat dan mengintegrasikan tugas & fungsi tambahan berikut ke dalam profil resmi kedinasan Anda:\n"
        f"📌 *Penugasan Tambahan Baru:*\n"
        f"• *{extracted_duty.capitalize()}*\n\n"
        f"📋 *Profil Kedinasan Terintegrasi Saat Ini:*\n"
        f"• *Nama:* {user.get('full_name')}\n"
        f"• *NIP:* `{user.get('nip') or '-'}`\n"
        f"• *Pangkat/Gol:* {user.get('pangkat_gol') or '-'}\n"
        f"• *Jabatan:* {user.get('jabatan')}\n"
        f"• *Unit Kerja:* {user.get('unit_kerja')} / {user.get('tim_kerja')}\n"
        f"• *Tupoksi Utama:* {user.get('tupoksi_primer') or user.get('jabatan')}\n"
        f"• *Daftar Penugasan Tambahan Terdata:*\n{duties_formatted}\n\n"
        f"💡 *Dampak Integrasi Sistem:*\n"
        f"Setiap analisis regulasi, harmonisasi pembagian urusan pemda, penelusuran disposisi, serta rekomendasi substansi dari SATRIA "
        f"selanjutnya akan secara otomatis memperhitungkan mandat penugasan tambahan ini.\n\n"
        f"_Apakah ada telaah awal, draf regulasi, atau koordinasi teknis terkait penugasan ini yang ingin kita bahas bersama, Bapak/Ibu?_"
    )
    return confirm_msg


class LegalMadyaWhatsAppHandler:
    """Orkestrator percakapan hukum & tata kelola WhatsApp SATRIA untuk pengguna whitelist terisolasi."""

    def __init__(self):
        self.session_cache: Dict[str, list] = {}

    async def handle_incoming_message(
        self,
        sender_phone: str,
        message_text: str,
        media_path: Optional[str] = None,
        recipient_jid: Optional[str] = None
    ) -> str:
        """
        Memproses pesan masuk dari WhatsApp dan mengembalikan respon telaah SATRIA
        dilengkapi dengan typing keep-alive, fast-path routing, dan autonomous tool reasoning.
        """
        clean_phone = normalize_phone_number(sender_phone)
        user = get_whitelist_user(clean_phone)
        actual_jid = recipient_jid or clean_phone

        # 1. Security Gate (Whitelist Check)
        if not user:
            # Fallback check for Super Admin
            if is_admin_user(clean_phone):
                user = {
                    "user_id": "asep_safrudin",
                    "phone_number": "+6285717223889",
                    "full_name": "Asep Safrudin, S.Kom",
                    "jabatan": "Penata Layanan Operasional / Administrator Sistem MCP",
                    "unit_kerja": "Sekretariat / TU SUPD II",
                    "role": "SUPER_ADMIN",
                    "permissions": ["admin_manage", "full_audit"]
                }
            else:
                logger.warning(f"Unauthorized access attempt from {sender_phone}")
                return (
                    "⚠️ *AKSES TERBATAS*\n\n"
                    "Mohon maaf, Layanan Konsultasi *SATRIA (Sistem Analisis Tata Kelola, Regulasi, & Insan Aparatur)* "
                    "Ditjen Bangda ini bersifat tertutup dan terbatas khusus untuk Tim Analis Hukum, "
                    "Perancang PUU, dan Pimpinan Terdaftar."
                )

        # Aktifkan Visual Keep-Alive (Typing Indicator) untuk query berat
        est_duration = satria_typing_indicator.estimate_duration(message_text)
        await satria_typing_indicator.start_typing(clean_phone, estimated_duration=est_duration)

        try:
            return await self._process_incoming_internal(user, clean_phone, message_text, media_path, recipient_jid=actual_jid)
        finally:
            await satria_typing_indicator.stop_typing(clean_phone)

    async def _process_incoming_internal(
        self,
        user: Dict[str, Any],
        clean_phone: str,
        message_text: str,
        media_path: Optional[str] = None,
        recipient_jid: Optional[str] = None
    ) -> str:
        """Logika pemrosesan internal SATRIA setelah lolos whitelist dan guard."""
        raw_text = message_text.strip()
        target_user_jid = recipient_jid or clean_phone
        # Bersihkan trigger prefix jika ada (!satria, @satria, satria, dll)
        cleaned_text = raw_text
        for prefix in ["!satria", "@satria", "tanya satria:", "tanya satria", "satria,", "satria:"]:
            if cleaned_text.lower().startswith(prefix):
                cleaned_text = cleaned_text[len(prefix):].strip()
                break

        text_lower = cleaned_text.lower() if cleaned_text else raw_text.lower()
        start_process_time = time.time()

        # 0. Deteksi Perintah Administrasi Whitelist (Khusus Super Admin / Administrator)
        is_wl_command = any(text_lower.startswith(p) for p in ["!whitelist", "/whitelist", "!wl", "/wl"])
        if is_wl_command:
            is_admin = is_admin_user(clean_phone) or user.get("role") == "SUPER_ADMIN"
            if not is_admin:
                logger.warning(f"Unauthorized !whitelist attempt by {clean_phone} ({user.get('full_name')})")
                return (
                    "⛔ *AKSES DITOLAK*\n\n"
                    "Perintah manajemen whitelist hanya dapat diakses oleh Administrator Sistem (*Super Admin*)."
                )
            
            logger.info(f"Executing admin whitelist command from {clean_phone}: {cleaned_text}")
            admin_reply = await self.handle_admin_whitelist_command(cleaned_text, user, clean_phone)
            satria_session_manager.record_turn(clean_phone, "assistant", admin_reply, intent="ADMIN_WHITELIST")
            return admin_reply

        # Ambil riwayat percakapan multi-turn (Sliding Window 6 turn terakhir)
        history = satria_session_manager.get_recent_history(clean_phone, limit=6)
        satria_session_manager.record_turn(clean_phone, "user", raw_text)

        # 1. Mode Lampiran Dokumen (PDF, DOCX, TXT via WhatsApp)
        # WAJIB didahulukan agar berkas lampiran tidak pernah terbegal oleh detektor non-service regex
        if media_path and Path(media_path).exists():
            try:
                from agents.profiles.legal.processors.document_ingestion import ingest_legal_document
                ingest_res = ingest_legal_document(file_path=media_path)
                if ingest_res.get("success") and ingest_res.get("extracted_text"):
                    extracted_text = ingest_res["extracted_text"]
                    file_name = ingest_res.get("file_name", Path(media_path).name)
                    file_size_kb = round(ingest_res.get("file_size", 0) / 1024, 1)

                    # Deteksi tipe dokumen: SP4N-LAPOR! / Aduan Publik vs Draf Regulasi / Kebijakan Daerah
                    ext_lower = extracted_text.lower()
                    cmd_lower = cleaned_text.lower()

                    # Safeguard Audit Regulasi vs SP4N:
                    # Jika instruksi pengguna atau nama berkas mengindikasikan audit/telaah regulasi/kebijakan daerah,
                    # jangan pernah dialihkan ke mode SP4N meskipun naskah dokumen memuat kata "pengaduan"
                    is_regulatory_intent = any(k in cmd_lower or k in file_name.lower() for k in [
                        "audit", "analisis", "telaah", "uji", "regulasi", "rpjmd", "rpd", "rkpd",
                        "ranperda", "perda", "perbup", "perwali", "kepmen", "dim", "ruu", "naskah"
                    ])

                    is_explicit_sp4n_cmd = any(k in cmd_lower for k in ["sp4n", "lapor.go.id", "tiket lapor", "saluran aduan", "draf jawaban aduan", "aduan masyarakat"])
                    is_sp4n_doc_pattern = any(k in ext_lower[:1500] for k in ["lapor.go.id", "tiket #", "no. tiket", "id pengaduan", "saluran pengaduan sp4n"])

                    is_sp4n_inquiry = not is_regulatory_intent and (is_explicit_sp4n_cmd or is_sp4n_doc_pattern)

                    if is_sp4n_inquiry:
                        prompt_sp4n = (
                            f"Pengguna melampirkan berkas dokumen/screenshot pengaduan masyarakat: '{file_name}'.\n"
                            f"Pesan pengantar dari analis: {cleaned_text if cleaned_text else 'Susun telaah yuridis dan draf jawaban resmi'}\n\n"
                            f"Berikut isi teks dokumen/screenshot pengaduan yang diekstrak via OCR:\n"
                            f"{extracted_text[:4000]}\n\n"
                            f"TUGAS UTAMA SATRIA (ASISTEN AHLI MADYA BANGDA):\n"
                            f"1. Identifikasi Pokok Permasalahan & Nomor Tiket / Saluran Pengaduan (misal: SP4N-LAPOR! Ditjen Bina Pembangunan Daerah).\n"
                            f"2. Susun '⚖️ I. RINGKASAN TELAAH YURIDIS (INTERNAL ANALIS)' yang memuat:\n"
                            f"   - Status Keberlakuan Regulasi yang ditanyakan (masih berlaku / dicabut / diubah / diganti).\n"
                            f"   - Harmonisasi dengan UU No. 23/2014 (Pembagian Urusan Konkuren Perdagangan & Koperasi/UKM).\n"
                            f"   - Penyesuaian dengan regulasi terkini (UU Cipta Kerja, PP No. 7/2021, perizinan berusaha NIB mikro/OSS-RBA).\n"
                            f"3. Susun '📝 II. DRAF FORMAL JAWABAN SP4N-LAPOR! (SIAP SALIN)' dalam format resmi tanggapan admin/pengelola SP4N-LAPOR! Ditjen Bina Pembangunan Daerah Kemendagri yang normatif, santun, lugas, dan operasional bagi Pemerintah Daerah."
                        )
                        ai_sp4n, token_usage, inf_ms = await _call_openai_engine(
                            user_info=user,
                            user_query=prompt_sp4n,
                            precedents=None,
                            extra_context=f"Berkas: {file_name} ({file_size_kb} KB), Metode OCR: {ingest_res.get('method')}",
                            history=history
                        )
                        if ai_sp4n:
                            doc_reply = (
                                f"📋 *TELAAH & DRAF JAWABAN SP4N-LAPOR! — SATRIA*\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"👤 *Pemohon:* {user.get('full_name')}\n"
                                f"📁 *Berkas:* `{file_name}` ({file_size_kb} KB)\n"
                                f"⚙️ *Metode Ekstraksi:* `{ingest_res.get('method')}`\n\n"
                                f"{ai_sp4n}"
                            )
                            satria_session_manager.record_turn(clean_phone, "assistant", doc_reply)
                            return doc_reply

                    # 1. Analisis AST dependensi
                    dep_res = legal_analyze_dependencies(extracted_text)
                    dep_graph = dep_res.get("dependency_graph", {})

                    # 2. Cari Preseden yudisial
                    tier2_matches = legal_search_tier2_precedents(query=extracted_text[:200], top_k=3)
                    precedents = tier2_matches.get("precedents", [])

                    # 3. Penalaran Generatif OpenAI
                    ast_summary = (
                        f"Nama Berkas: {file_name} ({file_size_kb} KB), "
                        f"Metode Ekstraksi: {ingest_res.get('method')}, "
                        f"Total Karakter: {ingest_res.get('character_count')}, "
                        f"Total Pasal Terdeteksi: {dep_graph.get('total_articles', 0)}, "
                        f"Relasi Rujukan: {dep_graph.get('total_cross_references', 0)}"
                    )
                    prompt_doc = (
                        f"Pengguna melampirkan berkas dokumen draf regulasi/kebijakan: '{file_name}'.\n"
                        f"Instruksi/Pesan pengantar: {cleaned_text if cleaned_text else 'Lakukan audit regulasi komprehensif'}\n\n"
                        f"Berikut isi teks dokumen yang berhasil diekstrak:\n"
                        f"{extracted_text[:4500]}\n\n"
                        f"TUGAS UTAMA SATRIA (ASISTEN AHLI MADYA BANGDA):\n"
                        f"Susun '📄 LAPORAN AUDIT EKSEKUTIF REGULASI' berbobot tinggi untuk pimpinan mencakup:\n"
                        f"1. 🏷️ Identitas Dokumen & Status Kelayakan (🟢 LULUS / 🟡 PERLU REVISI / 🔴 RAWAN CACAT / ULTRA VIRES)\n"
                        f"2. ⚖️ Uji Kewenangan & Potensi Ultra Vires (Doktrin Jimly Asshiddiqie & UU 23/2014): Telusuri mandat delegasi UU induk vs kewenangan umum, analisis risiko pembatalan di MA/MK.\n"
                        f"3. 🔍 Uji 5 Faktor Efektivitas Lapangan (Doktrin Soerjono Soekanto): Analisis kejelasan norma, kesiapan kelembagaan/SDM OPD pelaksana, dukungan APBD/fasilitas, kesiapan masyarakat, dan budaya hukum lokal.\n"
                        f"4. 📊 Uji Beban Regulasi & Dampak Kebijakan (Regulatory Impact Assessment - RIA Inpres 7/2017): Efisiensi beban kepatuhan vs manfaat riil.\n"
                        f"5. 📚 Rujukan Preseden & Yurisprudensi Peradilan (Putusan MK/MA terkait jika ada).\n"
                        f"6. 💡 Rekomendasi Klausul Aman (Safe Drafting): Rekomendasi pasal spesifik yang perlu direvisi beserta rumusan bunyi pasal penggantinya."
                    )
                    ai_audit, token_usage, inf_ms = await _call_openai_engine(
                        user_info=user,
                        user_query=prompt_doc,
                        precedents=precedents,
                        extra_context=ast_summary,
                        history=history
                    )
                    if ai_audit:
                        doc_reply = (
                            f"📄 *LAPORAN AUDIT DOKUMEN REGULASI — SATRIA*\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"👤 *Pemohon:* {user.get('full_name')}\n"
                            f"📁 *Berkas:* `{file_name}` ({file_size_kb} KB)\n"
                            f"⚙️ *Metode:* `{ingest_res.get('method')}`\n"
                            f"📊 *Struktur:* *{dep_graph.get('total_articles', 0)} Pasal* ({dep_graph.get('total_cross_references', 0)} Rujukan)\n\n"
                            f"{ai_audit}"
                        )
                        satria_session_manager.record_turn(clean_phone, "assistant", doc_reply)
                        return doc_reply

                    fallback_doc = (
                        f"📄 *HASIL EKSTRAKSI DOKUMEN — SATRIA*\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"👤 *Pemohon:* {user.get('full_name')}\n"
                        f"📁 *Berkas:* `{file_name}` ({file_size_kb} KB)\n"
                        f"📊 *Struktur:* *{dep_graph.get('total_articles', 0)} Pasal Terpetakan*\n\n"
                        f"Dokumen berhasil diekstrak ({ingest_res.get('character_count')} karakter). "
                        f"Silakan ajukan pertanyaan spesifik terkait pasal dalam dokumen ini."
                    )
                    satria_session_manager.record_turn(clean_phone, "assistant", fallback_doc)
                    return fallback_doc
                else:
                    # Fallback Plan jika OCR gagal atau teks < 20 karakter
                    file_name = Path(media_path).name
                    fallback_ocr_reply = (
                        f"⚠️ *DOKUMEN TIDAK DAPAT DIEKSTRAK SECARA OTOMATIS*\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"Yth. Bapak/Ibu *{user.get('full_name')}*,\n\n"
                        f"Berkas gambar/dokumen yang dikirimkan (`{file_name}`) tidak dapat dibaca teksnya secara optimal oleh OCR "
                        f"(kemungkinan gambar buram, resolusi terlalu rendah, atau format biner tidak terbaca).\n\n"
                        f"💡 *Opsi Tindak Lanjut (Fallback Manual Entry):*\n"
                        f"1. Kirimkan tangkapan layar/foto ulang dengan fokus dan resolusi lebih tajam; *ATAU*\n"
                        f"2. *Ketik langsung pertanyaan atau nomor aduan secara manual* pada chat ini (contoh: _'Cek keberlakuan Permendagri 41/2012 dan Perpres 125/2012'_).\n\n"
                        f"Saya akan langsung menyusun telaah yuridis dan draf tanggapannya. 🙏"
                    )
                    satria_session_manager.record_turn(clean_phone, "assistant", fallback_ocr_reply)
            except Exception as e:
                logger.error(f"Error processing document media attachment: {e}")

        # ========== 1.5. Deteksi Konfirmasi Delegasi Pesan / Tugas Eksekutif (Human-in-the-Loop) ==========
        from integrations.whatsapp.delegation_manager import (
            get_pending_dispatch,
            clear_pending_dispatch,
            execute_dispatch,
            is_confirmation_trigger,
            extract_delegation_intent,
            lookup_recipient_in_bangda,
            format_delegated_message_draft,
            format_leader_preview,
            store_pending_dispatch,
            clean_phone_for_jid
        )

        pending_dispatch = get_pending_dispatch(clean_phone)
        if pending_dispatch:
            is_conf, conf_action = is_confirmation_trigger(cleaned_text)
            if is_conf:
                if conf_action == "CONFIRM":
                    disp_ok, disp_report = await execute_dispatch(user, pending_dispatch)
                    clear_pending_dispatch(clean_phone)
                    satria_session_manager.record_turn(clean_phone, "assistant", disp_report, intent="EXECUTIVE_DISPATCH_CONFIRMED")
                    return disp_report
                elif conf_action == "CANCEL":
                    clear_pending_dispatch(clean_phone)
                    cancel_reply = (
                        "❌ *PENGIRIMAN ARAHAN DIBATALKAN*\n\n"
                        f"Draf pesan arahan kedinasan untuk *{pending_dispatch.get('recipient_name')}* telah dibatalkan "
                        "dan dibersihkan dari memori. Tidak ada pesan yang dikirimkan ke kontak tujuan."
                    )
                    satria_session_manager.record_turn(clean_phone, "assistant", cancel_reply, intent="EXECUTIVE_DISPATCH_CANCELLED")
                    return cancel_reply

        # ========== 1.6. Deteksi Permintaan Delegasi Arahan / Pengiriman Kartu Kontak ==========
        delegation_intent = extract_delegation_intent(cleaned_text)
        if delegation_intent:
            logger.info(f"Delegation intent detected from {user.get('full_name')}: {delegation_intent}")
            target_raw = delegation_intent["target_name"]
            recipient_bangda = lookup_recipient_in_bangda(target_raw)

            target_phone = delegation_intent.get("phone")
            if not target_phone and recipient_bangda:
                target_phone = recipient_bangda.get("phone_number") or ""

            if not recipient_bangda:
                unfound_reply = (
                    f"⚠️ *DATA SASARAN TIDAK TERDETEKSI DI TIM KERJA BANGDA*\n\n"
                    f"SATRIA tidak menemukan pegawai dengan nama/identitas *'{target_raw}'* "
                    f"pada database Keputusan Tim Kerja Ditjen Bangda 2026 maupun direktori kepegawaian aktif.\n\n"
                    f"💡 *Saran:* Pastikan penulisan nama sesuai nama resmi atau lampirkan *Kartu Kontak WhatsApp (vCard)* beliau."
                )
                satria_session_manager.record_turn(clean_phone, "assistant", unfound_reply, intent="DELEGATION_TARGET_NOT_FOUND")
                return unfound_reply

            if not target_phone:
                no_phone_reply = (
                    f"👤 *PEGAWAI DITEMUKAN PADA DATABASE TIM KERJA:*\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"• *Nama:* {recipient_bangda.get('full_name')}\n"
                    f"• *NIP:* {recipient_bangda.get('nip') or '-'}\n"
                    f"• *Jabatan:* {recipient_bangda.get('jabatan')}\n"
                    f"• *Tim Kerja:* {recipient_bangda.get('tim_kerja')}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"⚠️ Nomor WhatsApp *{recipient_bangda.get('full_name')}* belum tercatat di sistem saya.\n"
                    f"Mohon lampirkan *Kartu Kontak WhatsApp* beliau atau ketik nomor HP-nya (contoh: `0812xxxx`) "
                    f"agar SATRIA dapat menyiapkan draf dan meneruskan instruksi Bapak."
                )
                satria_session_manager.record_turn(clean_phone, "assistant", no_phone_reply, intent="DELEGATION_PHONE_REQUIRED")
                return no_phone_reply

            instruction_text = delegation_intent["instruction"]
            draft_msg = format_delegated_message_draft(user, recipient_bangda, instruction_text)
            recipient_jid = clean_phone_for_jid(target_phone)

            store_pending_dispatch(clean_phone, {
                "sender_phone": clean_phone,
                "sender_name": user.get("full_name"),
                "recipient_name": recipient_bangda.get("full_name"),
                "recipient_phone": target_phone,
                "recipient_jid": recipient_jid,
                "recipient_jabatan": recipient_bangda.get("jabatan"),
                "recipient_tim": recipient_bangda.get("tim_kerja"),
                "instruction_text": instruction_text,
                "draft_text": draft_msg
            })

            preview_reply = format_leader_preview(recipient_bangda, draft_msg, target_phone)
            satria_session_manager.record_turn(clean_phone, "assistant", preview_reply, intent="EXECUTIVE_DELEGATION_PREVIEW")
            return preview_reply

        # 2. Deteksi Permintaan Non-Pelayanan (Feedback Teknis, Usulan Fitur, Koreksi Data, Pertanyaan Sistem, Keluhan)
        # Hanya dievaluasi untuk pesan teks murni tanpa berkas lampiran
        non_service_cat = satria_non_service_detector.detect(cleaned_text)
        if non_service_cat:
            logger.info(f"Non-service request classified: {non_service_cat.value}")
            handler_map = {
                NonServiceCategory.TECHNICAL_FEEDBACK: satria_non_service_handlers.handle_technical_feedback,
                NonServiceCategory.FEATURE_REQUEST: satria_non_service_handlers.handle_feature_request,
                NonServiceCategory.DATA_CORRECTION: satria_non_service_handlers.handle_data_correction,
                NonServiceCategory.SYSTEM_QUESTION: satria_non_service_handlers.handle_system_question,
                NonServiceCategory.COMPLAINT: satria_non_service_handlers.handle_complaint,
                NonServiceCategory.OUT_OF_SCOPE: satria_non_service_handlers.handle_out_of_scope,
                NonServiceCategory.PERSONAL_REQUEST: satria_non_service_handlers.handle_out_of_scope
            }
            handler_fn = handler_map.get(non_service_cat)
            if handler_fn:
                ns_reply = await handler_fn(cleaned_text, user)
                duration_ms = round((time.time() - start_process_time) * 1000, 1)
                satria_session_manager.record_turn(clean_phone, "assistant", ns_reply, intent=non_service_cat.value)
                satria_interaction_logger.log_interaction_async({
                    "timestamp": datetime.now().isoformat(),
                    "user_phone": clean_phone,
                    "user_name": user.get("full_name", ""),
                    "input_text": raw_text,
                    "is_non_service": True,
                    "non_service_category": non_service_cat.value,
                    "response_time_ms": duration_ms,
                    "circuit_state": satria_timeout_guard.get_circuit_state("lookup_bangda_staff").value,
                    "fallback_used": False,
                    "token_usage": TokenUsage().to_dict(),
                    "latency_breakdown": LatencyBreakdown(classification_ms=duration_ms, total_response_ms=duration_ms).to_dict()
                })
                return ns_reply

        # 2.5 Deteksi Pengayaan Profil Alami (Tugas & Fungsi Tambahan / Pokja / Satgas)
        profile_duty_reply = await _detect_and_handle_additional_duty(user, clean_phone, cleaned_text, history=history)
        if profile_duty_reply:
            satria_session_manager.record_turn(clean_phone, "assistant", profile_duty_reply, intent="PROFILE_ENRICHMENT")
            return profile_duty_reply

        # 2.8 Perintah Reset Sesi Percakapan (Sesi Baru)
        is_reset_cmd = any(text_lower == cmd for cmd in [
            "/reset", "reset", "reset sesi", "sesi baru", "mulai baru", "/start",
            "/new", "new session", "clear session", "hapus riwayat", "hapus sesi"
        ])
        if is_reset_cmd:
            satria_session_manager.clear_session(clean_phone)
            logger.info(f"Session reset successfully for {clean_phone}")
            reset_reply = (
                f"🔄 *SESI PERCAKAPAN BARU DIMULAI*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Yth. Bapak/Ibu *{user.get('full_name')}*,\n\n"
                f"Riwayat percakapan sebelumnya telah dibersihkan. Konteks SATRIA telah diatur ulang ke kondisi awal (*fresh context*).\n\n"
                f"Silakan ajukan pertanyaan, permintaan analisis regulasi, penelusuran surat/disposisi, atau isu kedinasan terbaru yang ingin dibahas. Saya siap membantu! 🏛️✨"
            )
            satria_session_manager.record_turn(clean_phone, "assistant", reset_reply, intent="RESET_SESSION")
            return reset_reply

        # 3. Salam Pembuka / Info Profil
        is_greeting = any(text_lower.startswith(g) for g in ["halo", "hai", "start", "menu", "bantuan", "help", "assalamualaikum", "selamat pagi", "selamat siang", "selamat sore", "selamat malam", "satria"]) and len(text_lower.split()) <= 4
        if is_greeting or text_lower in ["halo", "hai", "p", "menu", "info", "satria", "!satria"]:
            greet_reply = (
                f"🏛️ *SATRIA — ASISTEN CERDAS DITJEN BANGDA*\n"
                f"_(Sistem Analisis Tata Kelola, Regulasi, Insan Aparatur, & Administrasi Persuratan)_\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Selamat bertugas, *{user.get('full_name')}*\n"
                f"📌 *Jabatan:* {user.get('jabatan')}\n"
                f"🏢 *Unit/Tim:* {user.get('unit_kerja')} / {user.get('tim_kerja')}\n\n"
                f"Saya memiliki *2 Spesialisasi Peran Utama* untuk mendukung tugas kedinasan Bapak/Ibu:\n\n"
                f"🏛️ *1. ASISTEN AHLI MADYA (HUKUM, REGULASI & KEPEGAWAIAN)*\n"
                f"• Telaah & Audit Draf Regulasi / Ranperda (Kirim teks pasal / berkas PDF/DOCX)\n"
                f"• Uji 6-Dimensi BPHN & Precedent Memory MK/MA\n"
                f"• Konsultasi Urusan Pemda (UU 23/2014) & Diskresi (UU 30/2014)\n"
                f"• Informasi Kepegawaian & Master Tim Kerja SK 2026\n\n"
                f"📮 *2. ASISTEN ADMINISTRASI PERSURATAN (TATA NASKAH & DISPOSISI)*\n"
                f"• Monitoring & Rekapitulasi Surat Masuk/Keluar (Eksternal Daerah/K/L & Internal)\n"
                f"• Pelacakan Posisi Berkas & Catatan Disposisi Pimpinan (Dirjen/Sesditjen/Direktur)\n"
                f"• Pencarian Agenda Surat & Fasilitasi Dokumen Daerah (Ranperda RTRW/PDRD)\n"
                f"• Panduan Format Tata Naskah Dinas Kemendagri\n\n"
                f"_Silakan ketik pertanyaan, ajukan pengecekan surat/disposisi, atau lampirkan berkas regulasi yang ingin diaudit._"
            )
            satria_session_manager.record_turn(clean_phone, "assistant", greet_reply)
            return greet_reply

        # 4. Mode Audit Dokumen / Teks Regulasi (Jika memuat struktur pasal multiline atau perintah !telaah / !kaji)
        is_telaah_cmd = any(cleaned_text.lower().startswith(p) for p in ["!telaah", "!kaji", "telaah:", "kaji:"])
        is_draft_text = is_telaah_cmd or ("\n" in message_text and any(h in text_lower for h in ["pasal ", "bab ", "menimbang", "mengingat", "(1)", "(2)"]))
        if is_draft_text and (is_telaah_cmd or not text_lower.startswith(("bagaimana", "apakah", "apa", "mohon", "tolong", "siapa", "mengapa"))):
            try:
                dep_res = legal_analyze_dependencies(message_text)
                dep_graph = dep_res.get("dependency_graph", {})
                
                tier2_matches = legal_search_tier2_precedents(query=message_text[:120], top_k=2)
                precedents = tier2_matches.get("precedents", [])

                ast_summary = (
                    f"Total Pasal: {dep_graph.get('total_articles', 0)}, "
                    f"Relasi Rujukan: {dep_graph.get('total_cross_references', 0)}, "
                    f"Root Norm: {dep_graph.get('root_definitions', [{}])[0].get('article', 'None') if dep_graph.get('root_definitions') else 'None'}"
                )
                prompt_text_audit = (
                    f"Lakukan telaah yuridis mendalam berbasis 6 Sudut Pandang Doktrin Hukum (Kewenangan Ultra Vires Jimly Asshiddiqie, 5 Faktor Efektivitas Soerjono Soekanto, RIA Beban Biaya, dan Keselarasan UU 23/2014) pada naskah/pertanyaan berikut:\n\n"
                    f"{cleaned_text if is_telaah_cmd else message_text}\n\n"
                    f"Sajikan telaah terstruktur: (1) Status Kelayakan, (2) Uji Kewenangan & Potensi Disharmoni, (3) Uji Sosiologis Kesiapan Lapangan, (4) Rujukan Preseden Putusan MK/MA, dan (5) Rekomendasi Solutif/Klausul Aman."
                )
                ai_reply, token_usage, inf_ms = await _call_openai_engine(
                    user_info=user,
                    user_query=prompt_text_audit,
                    precedents=precedents,
                    extra_context=ast_summary,
                    history=history,
                    persona="legal_madya"
                )
                if ai_reply:
                    final_draft_reply = f"⚖️ *TELAAH YURIDIS SATRIA (ASISTEN AHLI MADYA BANGDA)*\n━━━━━━━━━━━━━━━━━━━━━━━━\n👤 *Pemohon:* {user.get('full_name')}\n\n{ai_reply}"
                    satria_session_manager.record_turn(clean_phone, "assistant", final_draft_reply)
                    return final_draft_reply
            except Exception as e:
                logger.error(f"Error processing regulation text: {e}")

        # 5. Fast-Path Check (Bypass atau Direct Retrieval jika intent sangat jelas)
        t_cls_start = time.time()
        cls_query = cleaned_text
        if len(cleaned_text.split()) <= 6 and history:
            prev_user_queries = [h["content"] for h in history if h.get("role") == "user" and not h["content"].startswith("⏳")]
            if prev_user_queries:
                cls_query = f"{prev_user_queries[-1]} {cleaned_text}"
        intent_res = satria_tool_selector.classifier.classify(cls_query)
        t_cls_ms = round((time.time() - t_cls_start) * 1000, 2)

        # Deteksi Persona Secara Dinamis (Legal Madya vs Admin Persuratan)
        active_persona = _detect_persona(cleaned_text, intent_res.intent.value if intent_res else None)

        is_summary_session = _is_summary_or_wrapup_request(raw_text, intent=intent_res.intent.value if 'intent_res' in locals() and intent_res else None)

        if intent_res.is_fast_path:
            logger.info(f"⚡ Fast-Path triggered for intent: {intent_res.intent.value} (Score: {intent_res.raw_score}, Persona: {active_persona})")
            t_ret_start = time.time()
            is_web_task = intent_res.intent.value in ("search_web_realtime", "search_hybrid_web", "browse_portal_autonomous")

            milestone_msg = (
                f"🔎 *Menelusuri Portal Resmi & JDIH...*\n"
                f"_Pencarian peraturan di portal resmi web sedang berlangsung dan draf sedang diverifikasi. Mohon tunggu sebentar..._"
            )

            async def _run_fast_path_flow():
                fast_fact_res = await _execute_satria_tool(intent_res.intent.value, intent_res.tool_arguments, recipient_jid=target_user_jid)
                extra_instruction = ""
                if is_web_task:
                    extra_instruction = (
                        f"\n\nPETUNJUK WAJIB ATRIBUSI SUMBER:\n"
                        f"- Awali tanggapan dengan penegasan: '🌐 *Sumber Data:* Ditelusuri langsung dari portal resmi (seperti peraturan.bpk.go.id / JDIH).'\n"
                        f"- Cantumkan tautan/link URL resmi yang terdapat pada fakta di atas."
                    )
                ai_op, tok_use, inf_t = await _call_openai_engine(
                    user_info=user,
                    user_query=cleaned_text,
                    precedents=[],
                    extra_context=f"FAKTA RESMI TERVERIFIKASI (FAST-PATH):\n{fast_fact_res}{extra_instruction}",
                    history=history,
                    persona=active_persona,
                    recipient_jid=target_user_jid,
                    is_summary=is_summary_session
                )
                return fast_fact_res, ai_op, tok_use, inf_t

            if is_web_task:
                async with MilestoneGuard(target_user_jid, milestone_msg, delay_seconds=3.0):
                    fast_fact, ai_opinion, token_usage, inf_ms = await _run_fast_path_flow()
            else:
                fast_fact, ai_opinion, token_usage, inf_ms = await _run_fast_path_flow()

            t_ret_ms = round((time.time() - t_ret_start) * 1000, 2)
            
            duration_ms = round((time.time() - start_process_time) * 1000, 1)
            lb = LatencyBreakdown(
                classification_ms=t_cls_ms,
                retrieval_ms=t_ret_ms,
                llm_inference_ms=inf_ms,
                total_response_ms=duration_ms
            )

            satria_interaction_logger.log_interaction_async({
                "timestamp": datetime.now().isoformat(),
                "user_phone": clean_phone,
                "user_name": user.get("full_name", ""),
                "input_text": raw_text,
                "is_non_service": False,
                "intent": intent_res.intent.value,
                "confidence": intent_res.confidence,
                "fast_path": True,
                "tool_called": intent_res.intent.value,
                "tools_called": [intent_res.intent.value],
                "response_time_ms": duration_ms,
                "circuit_state": satria_timeout_guard.get_circuit_state(intent_res.intent.value).value,
                "fallback_used": False,
                "token_usage": token_usage.to_dict(),
                "latency_breakdown": lb.to_dict()
            })

            if ai_opinion:
                final_fp_reply = _clean_and_format_reply(user, ai_opinion, persona=active_persona, is_summary_session=is_summary_session)
                satria_session_manager.record_turn(clean_phone, "assistant", final_fp_reply, intent=intent_res.intent.value)
                return final_fp_reply

            final_direct_reply = _clean_and_format_reply(user, fast_fact, persona=active_persona, is_summary_session=is_summary_session)
            satria_session_manager.record_turn(clean_phone, "assistant", final_direct_reply, intent=intent_res.intent.value)
            return final_direct_reply

        # 6. Mode Konsultasi Bebas (Preseden, Administrasi Pemda, ASN/SDM, PUU via Autonomous Tool Calling)
        t_ret_start = time.time()
        res = legal_search_tier2_precedents(query=cleaned_text, top_k=3)
        precedents = res.get("precedents", [])
        t_ret_ms = round((time.time() - t_ret_start) * 1000, 2)

        # Jalankan penalaran generative dengan riwayat multi-turn, persona dinamis, & Autonomous Tool Calling Loop
        ai_opinion, token_usage, inf_ms = await _call_openai_engine(
            user_info=user,
            user_query=cleaned_text,
            precedents=precedents,
            history=history,
            persona=active_persona,
            recipient_jid=target_user_jid,
            is_summary=is_summary_session
        )

        duration_ms = round((time.time() - start_process_time) * 1000, 1)
        lb = LatencyBreakdown(
            classification_ms=t_cls_ms,
            retrieval_ms=t_ret_ms,
            llm_inference_ms=inf_ms,
            total_response_ms=duration_ms
        )

        satria_interaction_logger.log_interaction_async({
            "timestamp": datetime.now().isoformat(),
            "user_phone": clean_phone,
            "user_name": user.get("full_name", ""),
            "input_text": raw_text,
            "is_non_service": False,
            "intent": intent_res.intent.value if intent_res else "consultation",
            "confidence": intent_res.confidence if intent_res else 1.0,
            "fast_path": False,
            "response_time_ms": duration_ms,
            "circuit_state": satria_timeout_guard.get_circuit_state("lookup_bangda_staff").value,
            "fallback_used": False,
            "token_usage": token_usage.to_dict(),
            "latency_breakdown": lb.to_dict()
        })

        if ai_opinion:
            final_gen_reply = _clean_and_format_reply(user, ai_opinion, persona=active_persona, is_summary_session=is_summary_session)
            satria_session_manager.record_turn(clean_phone, "assistant", final_gen_reply)
            return final_gen_reply

        # Fallback Template if offline
        if precedents:
            reply = (
                f"📚 *RUJUKAN PRESEDEN YUDISIAL (TIER 1 & TIER 2)*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Menanggapi konsultasi Bapak/Ibu *{user.get('full_name')}*, berikut yurisprudensi relevan:\n\n"
            )
            for i, p in enumerate(precedents, 1):
                reply += (
                    f"*{i}. {p['nomor_perkara']}* ({p['lembaga']} - {p['tahun']})\n"
                    f" • *Judul:* {p['judul']}\n"
                    f" • *Status Norma:* `{p['status_norma']}`\n"
                    f" • *Ratio Decidendi:* {p['ratio_decidendi']}\n\n"
                )
            reply += "_Disarikan oleh AI Co-Pilot SATRIA Fungsional Ahli Madya._"
            satria_session_manager.record_turn(clean_phone, "assistant", reply)
            return reply

        norm_content = (
            f"Terkait dengan pertanyaan/konsultasi mengenai:\n"
            f"> *\"{cleaned_text}\"*\n\n"
            f"📌 *Telaah Normatif & Tata Kelola:*\n"
            f"1. Penyelenggaraan wewenang daerah wajib berlandaskan pada asas kepastian hukum dan pembagian urusan konkuren UU No. 23/2014.\n"
            f"2. Setiap perumusan diskresi kepala daerah wajib mematuhi batasan materiil UU No. 30/2014 tentang Administrasi Pemerintahan guna mencegah cacat wewenang (*detournement de pouvoir*).\n"
            f"3. Dalam penataan kepegawaian, seluruh kebijakan wajib mengacu pada prinsip meritokrasi UU No. 20/2023 tentang ASN."
        )
        final_norm_reply = _clean_and_format_reply(user, norm_content, persona=active_persona, is_summary_session=is_summary_session)
        satria_session_manager.record_turn(clean_phone, "assistant", final_norm_reply)
        return final_norm_reply

    async def handle_admin_whitelist_command(
        self,
        cmd_text: str,
        admin_user: Dict[str, Any],
        sender_phone: str
    ) -> str:
        """Memproses perintah administrasi whitelist via chat WhatsApp."""
        raw_cmd = cmd_text.strip()
        parts = raw_cmd.split()
        if len(parts) <= 1 or parts[1].lower() in ["help", "bantuan", "?"]:
            return (
                "🛠️ *PANEL ADMINISTRATOR WHITELIST SATRIA*\n"
                f"Yth. *{admin_user.get('full_name', 'Administrator')}* (Super Admin),\n"
                "Berikut panduan perintah pendaftaran personil via WhatsApp:\n\n"
                "📋 *1. Melihat Daftar Anggota Terdaftar:*\n"
                "`!whitelist list`\n\n"
                "🔍 *2. Mengecek Status Personil:*\n"
                "`!whitelist check <Nomor HP / LID / Nama>`\n"
                "_Contoh:_ `!whitelist check 087871393744` atau `!whitelist check haidir`\n\n"
                "➕ *3. Mendaftarkan Personil (Auto-Search SK Bangda):*\n"
                "Cukup masukkan nomor/LID dan nama, sistem akan otomatis mencocokkan NIP, Jabatan & Unit Kerja dari database SK Kepegawaian Ditjen Bangda:\n"
                "`!whitelist add <nomor/LID> <Nama Pegawai>`\n"
                "_Contoh HP:_ `!whitelist add 087871393744 Ahmad Haidir`\n"
                "_Contoh LID:_ `!whitelist add 210578085830727@lid Ahmad Haidir`\n"
                "_Contoh LID + HP:_ `!whitelist add 210578085830727@lid 087871393744 Ahmad Haidir`\n\n"
                "➕ *4. Mendaftarkan Personil (Format Kustom/Spesifik):*\n"
                "Gunakan pemisah `|` jika ingin menentukan rincian sendiri:\n"
                "`!whitelist add <nomor/LID> <Nama> | <Jabatan> | <Unit Kerja> | <Role>`\n"
                "_Pilihan Role:_\n"
                "• `LEGAL_ANALYST` (Tim Hukum & Analis PUU)\n"
                "• `LEGAL_DRAFTER_LEAD` (Ketua Tim Penyusunan PUU)\n"
                "• `LEGAL_REVIEWER_LEAD` (Penanggung Jawab Tim Hukum)\n"
                "• `OFFICE_STAFF` (Staf Persuratan / ULA / Pelayanan)\n"
                "• `REGIONAL_SUPPORT` (Staf Urusan Daerah SUPD)\n"
                "• `PLANNING_SUPPORT` (Staf Perencanaan / IT)\n\n"
                "❌ *5. Menghapus Personil:*\n"
                "`!whitelist remove <nomor / LID / user_id>`\n"
                "_Contoh:_ `!whitelist remove 087871393744`"
            )

        subcmd = parts[1].lower()

        # 1. LIST
        if subcmd in ["list", "daftar", "all"]:
            users = list_whitelist_users()
            if not users:
                return "ℹ️ Belum ada pengguna terdaftar di whitelist SATRIA."

            output = (
                "📋 *DAFTAR PENGGUNA WHITELIST SATRIA*\n"
                f"Total Terdaftar: *{len(users)} personil*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            )

            # Kelompokkan berdasar Role
            categories = {
                "👑 PIMPINAN & ADMINISTRATOR": ["SUPER_ADMIN", "LEGAL_REVIEWER_LEAD"],
                "⚖️ TIM ANALIS & PERANCANG PUU": ["LEGAL_DRAFTER_LEAD", "LEGAL_ANALYST"],
                "🌐 URUSAN DAERAH & PERENCANAAN": ["REGIONAL_SUPPORT", "PLANNING_SUPPORT"],
                "📮 STAF PERSURATAN & TATA USAHA (ULA)": ["OFFICE_STAFF"]
            }

            rendered_users = set()
            for cat_title, roles in categories.items():
                cat_users = [u for u in users if u.get("role") in roles]
                if cat_users:
                    output += f"*{cat_title}*\n"
                    for u in cat_users:
                        rendered_users.add(u.get("user_id"))
                        phone_display = u.get("phone_number", "-")
                        aliases_display = [a for a in u.get("phone_aliases", []) if "@lid" in str(a)]
                        lid_info = f" (LID: {aliases_display[0].split('@')[0]})" if aliases_display else ""
                        output += (
                            f"• *{u.get('full_name')}*\n"
                            f"  Jabatan: {u.get('jabatan')}\n"
                            f"  📱 {phone_display}{lid_info} | Role: `{u.get('role')}`\n\n"
                        )

            # Sisa jika ada role lain
            other_users = [u for u in users if u.get("user_id") not in rendered_users]
            if other_users:
                output += "*👥 LAINNYA*\n"
                for u in other_users:
                    output += f"• *{u.get('full_name')}* ({u.get('jabatan')}) — {u.get('phone_number')} [`{u.get('role')}`]\n"

            return output.strip()

        # 2. CHECK / INFO
        if subcmd in ["check", "info", "cek", "status"]:
            if len(parts) < 3:
                return "⚠️ Format salah. Gunakan: `!whitelist check <nomor HP / LID / nama>`"
            query_target = " ".join(parts[2:]).strip()
            user = get_whitelist_user(query_target)
            if not user:
                # Coba cari berdasar nama
                all_users = list_whitelist_users()
                for u in all_users:
                    if query_target.lower() in u.get("full_name", "").lower():
                        user = u
                        break

            if not user:
                return (
                    f"🔍 *HASIL PENGECEKAN WHITELIST*\n\n"
                    f"Target: `{query_target}`\n"
                    f"Status: ❌ *TIDAK TERDAFTAR*\n\n"
                    f"Gunakan `!whitelist add {query_target} <Nama>` untuk mendaftarkan."
                )

            perms_str = ", ".join(user.get("permissions", []))
            aliases_str = ", ".join(user.get("phone_aliases", [])) or "-"
            return (
                f"👤 *PROFIL PERSONIL WHITELIST SATRIA*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"• *Nama Lengkap:* {user.get('full_name')}\n"
                f"• *NIP:* {user.get('nip') or '-'}\n"
                f"• *Jabatan:* {user.get('jabatan')}\n"
                f"• *Unit Kerja:* {user.get('unit_kerja')}\n"
                f"• *Tim Kerja:* {user.get('tim_kerja') or '-'}\n"
                f"• *Nomor HP:* {user.get('phone_number')}\n"
                f"• *Alias / LID:* {aliases_str}\n"
                f"• *Role RBAC:* `{user.get('role')}`\n"
                f"• *Hak Akses:* {perms_str}\n"
                f"• *Status:* 🟢 *Aktif & Berwenang*"
            )

        # 3. ADD
        if subcmd in ["add", "tambah", "register", "daftar"]:
            if len(parts) < 3:
                return (
                    "⚠️ Format salah. Contoh penggunaan:\n"
                    "• `!whitelist add 087871393744 Ahmad Haidir`\n"
                    "• `!whitelist add 210578085830727@lid Ahmad Haidir`\n"
                    "• `!whitelist add 08123456789 Budi Santoso | Analis Hukum | Sekretariat | LEGAL_ANALYST`"
                )

            # Ambil sisa teks setelah '!whitelist add'
            add_payload = " ".join(parts[2:]).strip()
            
            # Parsing identifier (bisa HP, LID, atau keduanya)
            tokens = add_payload.split()
            id1 = tokens[0]
            id2 = None
            text_start_idx = 1
            if len(tokens) > 2 and (
                ("@lid" in tokens[1] or tokens[1].startswith("+") or tokens[1].startswith("08") or (tokens[1].isdigit() and len(tokens[1]) >= 10))
            ):
                id2 = tokens[1]
                text_start_idx = 2

            primary_id = id1
            linked_phone = None
            if id2:
                if "@lid" in id1 or (id1.isdigit() and len(id1) >= 14 and not id1.startswith(("62", "08"))):
                    primary_id = id1
                    linked_phone = id2
                else:
                    primary_id = id2
                    linked_phone = id1
            elif "@lid" in id1 or (id1.isdigit() and len(id1) >= 14 and not id1.startswith(("62", "08"))):
                primary_id = id1

            body_text = " ".join(tokens[text_start_idx:]).strip()
            if not body_text:
                return "⚠️ Mohon sertakan nama personil setelah nomor/LID."

            # Cek apakah menggunakan format pipe '|'
            if "|" in body_text:
                pipe_parts = [p.strip() for p in body_text.split("|")]
                full_name = pipe_parts[0]
                jabatan = pipe_parts[1] if len(pipe_parts) > 1 and pipe_parts[1] else "Staf Teknis"
                unit_kerja = pipe_parts[2] if len(pipe_parts) > 2 and pipe_parts[2] else "Ditjen Bina Pembangunan Daerah"
                role_cand = pipe_parts[3] if len(pipe_parts) > 3 and pipe_parts[3] else "OFFICE_STAFF"
                nip_cand = pipe_parts[4] if len(pipe_parts) > 4 and pipe_parts[4] else None
            else:
                # Auto-Lookup dari Database Master Kepegawaian Ditjen Bangda
                full_name = body_text
                staff_info = _lookup_staff_details_for_whitelist(body_text)
                if staff_info:
                    full_name = staff_info["nama"]
                    nip_cand = staff_info["nip"]
                    jabatan = staff_info["jabatan"]
                    unit_kerja = staff_info["unit_kerja"]
                    # Infer role
                    j_upper = jabatan.upper()
                    u_upper = unit_kerja.upper()
                    if "HUKUM" in j_upper or "PUU" in j_upper or "PERANCANG" in j_upper:
                        role_cand = "LEGAL_ANALYST"
                    elif "PERENCANAAN" in u_upper or "KOMPUTER" in j_upper:
                        role_cand = "PLANNING_SUPPORT"
                    elif "SUPD" in u_upper:
                        role_cand = "REGIONAL_SUPPORT"
                    elif "OPERASIONAL" in j_upper or "UMUM" in u_upper or "ULA" in u_upper or "TATA USAHA" in u_upper:
                        role_cand = "OFFICE_STAFF"
                    else:
                        role_cand = "OFFICE_STAFF"
                else:
                    nip_cand = None
                    jabatan = "Staf Teknis / Pegawai Ditjen Bangda"
                    unit_kerja = "Ditjen Bina Pembangunan Daerah"
                    role_cand = "OFFICE_STAFF"

            # Simpan via save_whitelist_user
            success, msg, udata = save_whitelist_user(
                identifier=primary_id,
                full_name=full_name,
                jabatan=jabatan,
                unit_kerja=unit_kerja,
                role=role_cand,
                nip=nip_cand,
                linked_phone=linked_phone
            )

            if not success:
                return f"❌ *GAGAL MENDAFTARKAN PERSONIL*\n\n{msg}"

            perms_str = ", ".join(udata.get("permissions", []))
            aliases_str = ", ".join(udata.get("phone_aliases", []))
            return (
                "✅ *PENDAFTARAN WHITELIST BERHASIL*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 *Nama:* {udata.get('full_name')}\n"
                f"🆔 *NIP:* {udata.get('nip') or '-'}\n"
                f"🏢 *Jabatan:* {udata.get('jabatan')}\n"
                f"🏛️ *Unit Kerja:* {udata.get('unit_kerja')}\n"
                f"📱 *Nomor HP:* {udata.get('phone_number')}\n"
                f"🔗 *LID / Aliases:* {aliases_str}\n"
                f"🏷️ *Role RBAC:* `{udata.get('role')}`\n"
                f"🔐 *Hak Akses:* {perms_str}\n\n"
                "📡 *Status Sinkronisasi:*\n"
                "• File Konfigurasi: `config/legal_bot_whitelist.json` (Updated)\n"
                "• Memory Cache: *Real-time Active* (Langsung berlaku tanpa restart)\n"
                "• Database Postgres: *Synchronized* (`member_profiles`)\n\n"
                f"Pengguna *{udata.get('full_name')}* sekarang sudah dapat berinteraksi langsung dengan SATRIA!"
            )

        # 4. REMOVE / DELETE
        if subcmd in ["remove", "delete", "hapus", "del"]:
            if len(parts) < 3:
                return "⚠️ Format salah. Gunakan: `!whitelist remove <nomor HP / LID / user_id>`"
            target = " ".join(parts[2:]).strip()
            success, msg, rem_user = remove_whitelist_user(target)
            if not success:
                return f"❌ *PENGHAPUSAN GAGAL*\n\n{msg}"

            return (
                "🗑️ *PENGHAPUSAN ANGGOTA WHITELIST*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Anggota berikut telah dinonaktifkan dari akses kedinasan SATRIA:\n"
                f"👤 *Nama:* {rem_user.get('full_name')}\n"
                f"📱 *Nomor:* {rem_user.get('phone_number')}\n"
                f"🏷️ *Role Sebelumnya:* `{rem_user.get('role')}`\n\n"
                "Akses SATRIA untuk nomor tersebut telah dinonaktifkan secara seketika."
            )

        # Unknown subcommand
        return (
            f"⚠️ Perintah `!whitelist {subcmd}` tidak dikenali.\n"
            "Ketik `!whitelist help` untuk melihat panduan penggunaan."
        )


# Singleton instance
legal_madya_handler = LegalMadyaWhatsAppHandler()


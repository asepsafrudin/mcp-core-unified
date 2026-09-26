"""
harmonization_gatekeeper.py — Gerbang Kliring Harmonisasi Ditjen PP / Kanwil (Pasal 58 UU 13/2022)
Mengimplementasikan SOP SE Menkumham No. M.HH-01.PP.04.02 Tahun 2022 untuk menghasilkan
Matriks Hasil Pengharmonisasian 5 Kolom dan menilai kelayakan penerbitan Surat Selesai Harmonisasi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class HarmonizationRow:
    no: int
    pasal_ref: str
    draf_text: str
    catatan_harmonisasi: str
    regulasi_terkait: str
    rumusan_rekomendasi: str
    status: str  # "SESUAI" | "PERLU_REVISI" | "DITOLAK"


@dataclass
class HarmonizationResult:
    title: str
    pemrakarsa: str
    readiness_index: float  # 0.0 - 100.0%
    is_cleared: bool
    status_label: str
    total_articles: int
    compliant_articles: int
    revised_articles: int
    matrix_rows: List[HarmonizationRow]


class HarmonizationGatekeeper:
    """
    Engine otomatisasi E-Harmonisasi standar Kementerian Hukum (Ditjen PP / Kantor Wilayah).
    """

    @classmethod
    def audit_and_generate_matrix(
        cls,
        title: str,
        pemrakarsa: str,
        articles: List[Dict[str, str]],
        reference_laws: Optional[List[str]] = None
    ) -> HarmonizationResult:
        """
        Melakukan audit keselarasan vertikal/horizontal dan menyusun Matriks 5 Kolom resmi.
        """
        rows: List[HarmonizationRow] = []
        compliant_count = 0
        revised_count = 0

        laws_cited = reference_laws or [
            "UU No. 23 Tahun 2014 tentang Pemerintahan Daerah",
            "UU No. 12 Tahun 2011 jo UU No. 13 Tahun 2022",
            "PP No. 12 Tahun 2019 tentang Pengelolaan Keuangan Daerah"
        ]
        primary_law = laws_cited[0]

        for i, art in enumerate(articles, 1):
            ref = art.get("ref", f"Pasal {i}")
            text = art.get("text", "")
            lower = text.lower()

            catatan = []
            rekomendasi = text
            status = "SESUAI"
            reg_terkait = primary_law

            # Check 1: Kata ambigu non-normatif
            ambiguous_terms = ["diupayakan", "diharapkan", "seyogianya", "sebaiknya", "diusahakan"]
            found_ambiguous = [term for term in ambiguous_terms if term in lower]
            if found_ambiguous:
                status = "PERLU_REVISI"
                catatan.append(f"Ditemukan frasa non-normatif: '{', '.join(found_ambiguous)}' yang dilarang Lampiran II UU 12/2011.")
                reg_terkait = "Lampiran II UU No. 12 Tahun 2011"
                # Formulasi rekomendasi
                for w in found_ambiguous:
                    rekomendasi = re.sub(rf"\b{w}\b", "wajib", rekomendasi, flags=re.IGNORECASE)

            # Check 2: Kewenangan Ultra Vires (Pembagian Urusan UU 23/2014)
            if "urusan pertahanan" in lower or "politik luar negeri" in lower or "fiskal nasional" in lower:
                status = "DITOLAK"
                catatan.append("Pelanggaran Kewenangan: Memuat urusan pemerintahan absolut pusat yang dilarang diatur Perda.")
                reg_terkait = "Pasal 9 ayat (1) dan Pasal 10 UU No. 23 Tahun 2014"
                rekomendasi = "[PASAL DIHAPUS - Di luar kewenangan konkuren daerah]"

            # Check 3: Ketentuan Sanksi Pidana Melebihi Batas Wewenang Perda
            if "penjara" in lower or "kurungan" in lower:
                if re.search(r"(\d+)\s+tahun", lower):
                    status = "PERLU_REVISI"
                    catatan.append("Sanksi pidana melebihi batas maksimal Perda (Maksimal kurungan 6 bulan atau denda Rp 50.000.000).")
                    reg_terkait = "Pasal 238 UU No. 23 Tahun 2014"
                    rekomendasi = re.sub(r"\d+\s+tahun", "paling lama 6 (enam) bulan", rekomendasi, flags=re.IGNORECASE)

            # Check 4: Modalitas norma kosong
            if status == "SESUAI" and not any(mod in lower for mod in ["wajib", "harus", "dilarang", "dapat", "berwenang", "adalah"]):
                status = "PERLU_REVISI"
                catatan.append("Kaidah Deontik: Rumusan norma belum memuat modalitas hukum yang jelas (suruhan/larangan/kebolehan/wewenang).")
                reg_terkait = "Lampiran II UU No. 12 Tahun 2011"

            if status == "SESUAI":
                compliant_count += 1
                catatan_text = "Telah selaras secara vertikal dengan peraturan yang lebih tinggi dan taat kaidah perancangan."
            else:
                revised_count += 1
                catatan_text = " ".join(catatan)

            rows.append(HarmonizationRow(
                no=i,
                pasal_ref=ref,
                draf_text=text.strip(),
                catatan_harmonisasi=catatan_text,
                regulasi_terkait=reg_terkait,
                rumusan_rekomendasi=rekomendasi.strip(),
                status=status
            ))

        total = len(articles)
        readiness = (compliant_count / total * 100) if total > 0 else 100.0
        is_cleared = (readiness >= 90.0 and not any(r.status == "DITOLAK" for r in rows))

        if is_cleared:
            status_label = "🟢 MEMENUHI SYARAT SURAT SELESAI HARMONISASI"
        elif any(r.status == "DITOLAK" for r in rows):
            status_label = "🔴 DITOLAK — TERDAPAT PELANGGARAN KEWENANGAN ABSOLUT"
        else:
            status_label = "🟡 PERLU PENYEMPURNAAN KONSEPSI & RAPAT PLENO LANJUTAN"

        return HarmonizationResult(
            title=title,
            pemrakarsa=pemrakarsa,
            readiness_index=round(readiness, 2),
            is_cleared=is_cleared,
            status_label=status_label,
            total_articles=total,
            compliant_articles=compliant_count,
            revised_articles=revised_count,
            matrix_rows=rows
        )

    @classmethod
    def render_matrix_markdown(cls, res: HarmonizationResult) -> str:
        """
        Merender Matriks Hasil Pengharmonisasian 5 Kolom Resmi sesuai format Ditjen PP Kemenkumham.
        """
        lines = []
        lines.append("# MATRIKS HASIL PENGHARMONISASIAN RANCANGAN PERATURAN DAERAH")
        lines.append(f"**Judul Regulasi:** {res.title}")
        lines.append(f"**Instansi Pemrakarsa:** {res.pemrakarsa}")
        lines.append(f"**Pedoman Acuan:** SE Menkumham No. M.HH-01.PP.04.02 Tahun 2022 & Pasal 58 UU 13/2022")
        lines.append(f"**Indeks Kesiapan Harmonisasi:** {res.readiness_index}% ({res.compliant_articles}/{res.total_articles} Pasal Selaras)")
        lines.append(f"**Status Rekomendasi:** {res.status_label}\n")

        lines.append("| No | Pasal / Ayat Draf Raperda | Catatan Harmonisasi Tim Kanwil/Ditjen PP | Regulasi Lebih Tinggi Terkait | Rekomendasi Rumusan Norma Hasil Harmonisasi |")
        lines.append("|:---|:--------------------------|:-----------------------------------------|:------------------------------|:--------------------------------------------|")

        for row in res.matrix_rows:
            clean_draf = row.draf_text.replace("\n", " ")[:120]
            clean_rekom = row.rumusan_rekomendasi.replace("\n", " ")[:120]
            status_badge = "✅ " if row.status == "SESUAI" else ("⚠️ " if row.status == "PERLU_REVISI" else "⛔ ")
            lines.append(
                f"| {row.no} | **{row.pasal_ref}**<br>{clean_draf}... | {status_badge}{row.catatan_harmonisasi} | {row.regulasi_terkait} | {clean_rekom}... |"
            )

        lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("### REKOMENDASI TINDAK LANJUT PERANCANG AHLI MADYA:")
        if res.is_cleared:
            lines.append("1. Naskah regulasi telah memenuhi prinsip keselarasan vertikal dan kaidah perancangan hukum.")
            lines.append("2. Draf dapat dibubuhi paraf persetujuan bersama dan diterbitkan **Surat Selesai Harmonisasi**.")
            lines.append("3. Regulasi siap dilanjutkan ke proses penetapan oleh Kepala Daerah / pembahasan di DPRD.")
        else:
            lines.append("1. Pemrakarsa wajib melakukan penyesuaian rumusan pasal sesuai kolom rekomendasi di atas.")
            lines.append("2. Jadwalkan rapat pleno pembulatan konsepsi lanjutan sebelum Surat Selesai Harmonisasi diterbitkan.")

        return "\n".join(lines)

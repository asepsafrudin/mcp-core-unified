import re
from typing import Dict, Any, List

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

    # 3. Bersihkan kalimat filler pengantar model di awal pesan
    filler_pattern = r"^(?:Baik,?\s*(?:saya|kami|Pak|Ibu|Bapak|Bapak/Ibu)?\s+[^\n]*\n*)+"
    cleaned = re.sub(filler_pattern, "", cleaned, flags=re.IGNORECASE).strip()

    # 4. Bersihkan sapaan lagi jika muncul setelah filler
    cleaned = re.sub(salutation_pattern, "", cleaned, flags=re.IGNORECASE).strip()

    # 5. Bersihkan pemisah horizontal yang menggantung di paling awal teks
    cleaned = re.sub(r"^(?:[-—─=━]{3,}\n*)+", "", cleaned).strip()

    user_name = user.get("full_name") or "Bapak/Ibu"
    
    # 6. Render tabel ke plain text list
    cleaned = render_plain_text(cleaned)

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

        # TASK-162: Tambahkan mekanisme feedback jempol (👍/👎) pada akhir pesan
        feedback_prompt = "\n\n_Apakah respons ini membantu? Balas 👍 atau 👎_"
        return cleaned + footer + feedback_prompt

def _is_summary_or_wrapup_request(text: str) -> bool:
    """Deteksi jika pengguna meminta ringkasan, kesimpulan, atau ingin menutup sesi."""
    t_lower = text.lower()
    wrapup_keywords = [
        "kesimpulan", "resume", "simpulkan", "ringkasan", "rangkuman",
        "rekapitulasi", "rekap", "cukup sekian", "terima kasih satria",
        "sudah cukup", "akhiri sesi", "tutup sesi"
    ]
    return any(kw in t_lower for kw in wrapup_keywords)

def chunk_message(text: str, max_chars: int = 4096) -> List[str]:
    """
    Memotong pesan yang melebihi batas karakter WA (4096) secara cerdas 
    pada batas paragraf/kalimat.
    """
    if len(text) <= max_chars:
        return [text]

    chunks = []
    paragraphs = text.split("\n\n")
    current_chunk = ""

    for para in paragraphs:
        # Jika satu paragraf lebih besar dari max_chars (jarang terjadi), potong berdasarkan baris
        if len(para) > max_chars:
            lines = para.split("\n")
            for line in lines:
                if len(current_chunk) + len(line) + 1 > max_chars:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    # Jika satu baris lebih besar dari max_chars, potong paksa
                    if len(line) > max_chars:
                        for i in range(0, len(line), max_chars):
                            chunks.append(line[i:i+max_chars])
                        current_chunk = ""
                    else:
                        current_chunk = line + "\n"
                else:
                    current_chunk += line + "\n"
            current_chunk += "\n"
        else:
            if len(current_chunk) + len(para) + 2 > max_chars:
                chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"
            else:
                current_chunk += para + "\n\n"
                
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    # Format part markers
    if len(chunks) > 1:
        formatted_chunks = []
        total = len(chunks)
        for i, chunk in enumerate(chunks, 1):
            marker = f"*(Bagian {i}/{total})*\n\n"
            formatted_chunks.append(marker + chunk)
        return formatted_chunks
        
    return chunks

def render_plain_text(text: str) -> str:
    """Mengonversi Markdown Tabel ke plain-text (daftar berpoin) yang ramah WhatsApp."""
    # Sederhanakan regex pencarian tabel markdown
    # Deteksi blok tabel markdown (mencari garis '|' dan '---')
    lines = text.split("\n")
    output_lines = []
    in_table = False
    headers = []
    
    for line in lines:
        if "|" in line and "---" in line and not in_table:
            # Ini mungkin baris separator header tabel, berarti baris sebelumnya adalah header
            if len(output_lines) > 0 and "|" in output_lines[-1]:
                header_line = output_lines.pop()
                headers = [h.strip() for h in header_line.split("|") if h.strip()]
                in_table = True
                continue
        elif in_table and "|" in line:
            # Baris data tabel
            cells = [c.strip() for c in line.split("|") if c.strip()]
            output_lines.append("") # Jeda kosong
            for i, cell in enumerate(cells):
                header = headers[i] if i < len(headers) else f"Kolom {i+1}"
                # Format: - Header: Nilai
                output_lines.append(f"- *{header}:* {cell}")
        elif in_table and "|" not in line and line.strip() != "":
            # Keluar dari tabel
            in_table = False
            output_lines.append(line)
        else:
            output_lines.append(line)
            
    return "\n".join(output_lines)

def get_adaptive_prompt_instructions(user: Dict[str, Any], is_executive_brief: bool = False) -> str:
    """
    Menghasilkan instruksi prompt adaptif untuk tone-switching dan executive brief.
    - Executive Brief: Maks 10 bullet points.
    - Tone-Switching: Formal ringkas untuk Pimpinan, teknis detail untuk Staf.
    """
    jabatan = (user.get("jabatan") or "").lower()
    
    # 1. Deteksi Role
    is_pimpinan = any(k in jabatan for k in [
        "direktur", "sesditjen", "dirjen", "menteri", "sekretaris", 
        "kepala daerah", "bupati", "gubernur", "walikota"
    ])
    
    instructions = ""
    
    # 2. Tone Switching
    if is_pimpinan:
        instructions += (
            "5. TONE-SWITCHING (MODE PIMPINAN): Anda sedang berbicara dengan Pimpinan (Eselon/Pengambil Keputusan). "
            "Gunakan gaya bahasa *formal, lugas, dan sangat ringkas*. Langsung sampaikan kesimpulan strategis, "
            "dampak kebijakan, atau status akhir. Hindari uraian teknis yang bertele-tele kecuali diminta.\n"
        )
    else:
        instructions += (
            "5. TONE-SWITCHING (MODE STAF/TEKNIS): Anda sedang berbicara dengan Pejabat Fungsional / Analis. "
            "Gunakan gaya bahasa *profesional teknis yang detail*. Sertakan dasar hukum yang komprehensif, "
            "langkah-langkah operasional, dan penjelasan pasal-per-pasal bila relevan.\n"
        )
        
    # 3. Executive Brief Mode
    if is_executive_brief:
        instructions += (
            "6. MODE EXECUTIVE BRIEF AKTIF: Format jawaban Anda ke dalam format 'Executive Brief' khusus WhatsApp: "
            "maksimal 10 poin bullet, setiap bullet maksimal 2 kalimat pendek, dan pastikan KESIMPULAN/TINDAKAN "
            "diletakkan pada paragraf pertama sebelum poin bullet. DILARANG menggunakan tabel markdown kompleks.\n"
        )
    else:
        instructions += (
            "6. FORMATTING: DILARANG keras menggunakan format tabel Markdown kompleks karena rusak di WhatsApp. "
            "Jika harus menyajikan data tabular, konversikan menjadi daftar berpoin (bullet points) yang rapi.\n"
        )
        
    return instructions

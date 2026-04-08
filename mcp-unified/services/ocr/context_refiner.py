"""
Context Refiner — LLM-enhanced context understanding untuk pipeline OCR.

Modul ini menyediakan:
1. LLM-based correction suggestion untuk typo yang tidak diketahui
2. Semantic context extraction dari teks
3. Document type classification
4. Field validation menggunakan knowledge LLM

Catatan: Pipeline TETAP BERJALAN tanpa LLM. LLM hanya OPSIONAL untuk:
- Meningkatkan akurasi di dokumen yang kompleks
- Memahami konteks yang ambigu
- Validasi hasil ekstraksi
"""

import os
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# LLM Configuration
LLM_CONFIG = {
    "enabled": os.getenv("OCR_USE_LLM", "false").lower() == "true",
    "provider": os.getenv("OCR_LLM_PROVIDER", "none"),  # "anthropic", "openai", "groq", "local"
    "model": os.getenv("OCR_LLM_MODEL", "claude-3-haiku-20240307"),
    "api_key": os.getenv("GROQ_API_KEY", ""),  # For Groq provider
    "max_tokens": 4000,  # Increased for SPM document extraction
}

# Field templates untuk LLM validation
FIELD_CONTEXT = {
    "nomor_surat": "Nomor surat resmi dengan format: NO/URUT/JABATAN/BULAN/TAHUN",
    "kode_satuan_kerja": "Kode numeric 6 digit untuk identifikasi satuan kerja",
    "nama_satuan_kerja": "Nama lengkap satuan kerja pemerintahan Indonesia",
    "nama_penerima": "Nama lengkap orang Indonesia dengan gelar akademik",
    "uraian": "Deskripsi pembayaran yang dilakukan",
    "jumlah_rp": "Jumlah uang dalam Rupiah",
}


# SPM Document Context Prompt (Production Stable)
SPM_SYSTEM_PROMPT = """Anda adalah analis data keuangan pemerintah Indonesia. Tugas Anda mengekstrak data dari dokumen SPM (Surat Perintah Membayar) / SPTJB ke format JSON.
Akurasi adalah prioritas tertinggi. Substansi data yang harus ditangkap adalah rincian pembayaran per baris.

ATURAN EKSTRAKSI SUBSTANSI:
1. IDENTIFIKASI TABEL:
   - Baris rincian selalu dimulai dengan nomor urut (1, 2, 3...) atau Kode Akun (6 digit, misal: 522111, 521211).
   - Pastikan 'Nama Penerima' dan 'Uraian' digabung jika teksnya terpecah di baris OCR yang berbeda.
   - Kolom yang wajib ada: [No, Akun, Penerima, Uraian, Jumlah_RP, Potongan_RP].

2. NORMALISASI NOMINAL:
   - Hapus titik (.) dan koma (,) sebelum mengubah ke angka (Integer/Float).
   - Contoh: "11:026.000" -> 11026000, "5,000,000" -> 5000000.
   - Jika nominal tidak terbaca jelas, beri nilai 0 dan tambahkan catatan di field 'keterangan'.

3. KOREKSI TEKS PEMERINTAHAN:
   - "I11" -> "III", "IV" -> "IV" (Romawi).
   - "S. KOm" -> "S.Kom", "S.IP" -> "S.IP", "S.H." -> "S.H".
   - "DITJFN" -> "DITJEN".

4. REKONSILIASI (PENTING):
   - Hitung total dari rincian_pembayaran. Jika tidak sama dengan total_jumlah_rp yang tertera di dokumen, catat perbedaannya di field 'keterangan'.

OUTPUT: Hanya JSON valid. Jangan tambahkan penjelasan teks atau tag markdown."""

SPM_USER_PROMPT_TEMPLATE = """Berikut adalah teks hasil OCR dari dokumen SPM. Ekstrak informasinya ke dalam JSON dengan struktur seperti contoh di bawah.

Teks OCR:
\"\"\"
{ocr_text}
\"\"\"

Output JSON yang diharapkan memiliki struktur:
{{
  "jenis_dokumen": "Surat Pernyataan Tanggung Jawab Belanja",
  "nomor": "...",
  "satuan_kerja": {{ "kode": "...", "nama": "..." }},
  "dipa": {{ "tanggal": "...", "nomor": "...", "revisi_ke": "..." }},
  "klasifikasi_belanja": "...",
  "rincian_pembayaran": [
    {{
      "no": 1,
      "akun": "522191",
      "penerima": "...",
      "uraian": "...",
      "jumlah_rp": 5513000,
      "potongan_kehadiran_rp": 0,
      "potongan_pph_rp": 0
    }}
  ],
  "total_jumlah_rp": 0,
  "total_potongan_rp": 0,
  "keterangan": "...",
  "tempat_tanggal": "...",
  "penandatangan": {{
    "jabatan": "...",
    "nama": "...",
    "nip": "..."
  }}
}}

Contoh koreksi OCR:
- "11:026.000" harus menjadi "11.026.000"
- "S. KOm" harus menjadi "S.Kom"
- "DITJFN" harus menjadi "DITJEN"
- "I11" harus menjadi "III" (jika konteks bulan Maret)

Hanya output JSON, tidak ada penjelasan."""

# Few-shot examples untuk SPM (Real World Scenarios)
SPM_FEW_SHOT_EXAMPLES = [
    {
        "input": "1 522111 Budi Santoso, SH\nBiaya Pemeliharaan Gedung\ndan Bangunan Bulan Maret\nJumlah 5.000.000 0",
        "output": {
            "no": 1, 
            "akun": "522111", 
            "penerima": "Budi Santoso, SH", 
            "uraian": "Biaya Pemeliharaan Gedung dan Bangunan Bulan Maret",
            "jumlah_rp": 5000000,
            "potongan_pph_rp": 0
        }
    },
    {
        "input": "2 522192 Ani Susanti, S.Kom\nHonorarium Tim Kerja\nPerundang-undangan RI\n3.500.000 0 175.000",
        "output": {
            "no": 2, 
            "akun": "522192", 
            "penerima": "Ani Susanti, S.Kom", 
            "uraian": "Honorarium Tim Kerja Perundang-undangan RI",
            "jumlah_rp": 3500000,
            "potongan_pph_rp": 175000
        }
    },
]


class ContextRefiner:
    """
    LLM-enhanced context refiner untuk pipeline OCR.
    
    Jika LLM tidak tersedia, modul ini fallback ke rule-based approach.
    
    Contoh penggunaan:
        refiner = ContextRefiner()
        corrected = refiner.correct_typo("DITJFN")
        context = refiner.extract_context("Nomor : 002/F.2/LS/III/2025")
        # Ekstraksi SPM dengan context LLM
        spm = refiner.extract_spm_document(ocr_text)
    """

    def __init__(self):
        self.enabled = LLM_CONFIG["enabled"] and LLM_CONFIG["provider"] != "none"
        self._client = None
        if self.enabled:
            self._initialize_client()

    def _initialize_client(self):
        """Initialize LLM client based on provider."""
        provider = LLM_CONFIG["provider"]
        
        if provider == "anthropic":
            try:
                import anthropic
                self._client = anthropic.Anthropic()
                logger.info("Anthropic LLM client initialized")
            except ImportError:
                logger.warning("anthropic package not installed, falling back to rules")
                self.enabled = False
                
        elif provider == "openai":
            try:
                from openai import OpenAI
                self._client = OpenAI()
                logger.info("OpenAI LLM client initialized")
            except ImportError:
                logger.warning("openai package not installed, falling back to rules")
                self.enabled = False
                
        elif provider == "groq":
            # Groq API (OpenAI-compatible)
            try:
                import requests
                self._client = requests
                self._api_url = "https://api.groq.com/openai/v1/chat/completions"
                self._api_key = LLM_CONFIG["api_key"]
                if not self._api_key:
                    logger.warning("GROQ_API_KEY not set, falling back to rules")
                    self.enabled = False
                else:
                    logger.info(f"Groq LLM client initialized, model: {LLM_CONFIG['model']}")
            except Exception as e:
                logger.warning(f"Failed to initialize Groq LLM: {e}")
                self.enabled = False
                
        elif provider == "local":
            # Local LLM (e.g., ollama)
            try:
                import requests
                self._client = requests
                self._api_url = os.getenv("LOCAL_LLM_URL", "http://localhost:11434/api/generate")
                logger.info(f"Local LLM client initialized at {self._api_url}")
            except Exception as e:
                logger.warning(f"Failed to initialize local LLM: {e}")
                self.enabled = False

    def correct_typo(self, wrong_text: str, context: Optional[str] = None) -> Optional[str]:
        """
        Gunakan LLM untuk memperbaiki typo yang tidak ada di kamus.
        
        Args:
            wrong_text: OCR result yang mungkin salah
            context: Context text untuk membantu LLM
            
        Returns:
            Corrected text atau None jika tidak bisa dikoreksi
        """
        if not self.enabled:
            return self._rule_based_correction(wrong_text, context)
        
        try:
            prompt = f"""
Sebagai ahli bahasa Indonesia dan dokumen pemerintahan, koreksi teks berikut 
yang mungkin salah akibat kesalahan OCR:

Teks OCR: "{wrong_text}"
Konteks: {context or "Dokumen pembayaran pemerintah Indonesia"}

Berikan koreksi yang paling mungkin. Hanya jawab dengan teks yang dikoreksi.
Jika teks sudah benar, jawab dengan teks yang sama.
"""
            result = self._call_llm(prompt)
            return result.strip() if result else wrong_text
        except Exception as e:
            logger.warning(f"LLM correction failed: {e}")
            return self._rule_based_correction(wrong_text, context)

    def extract_context(self, text: str) -> dict:
        """
        Ekstrak konteks dari teks menggunakan LLM.
        
        Args:
            text: OCR text document
            
        Returns:
            Dict dengan context understanding
        """
        if not self.enabled:
            return self._rule_based_context(text)
        
        try:
            prompt = f"""Analisis dokumen pemerintahan Indonesia berikut dan ekstrak informasi konteks:

{text[:1000]}

PENTING: Hanya jawab dengan format JSON murni tanpa penjelasan apapun.
Format JSON yang harus digunakan:
{{"jenis_dokumen": "...", "instansi_terkait": "...", "periode": "...", "tujuan": "...", "bahasa_formalitas": "formal|semi_formal|informal"}}

Jangan tambahkan apapun selain JSON."""
            result = self._call_llm(prompt)
            if result:
                # Bersihkan output dari tag pemikiran dan karakter non-JSON
                import re
                cleaned = re.sub(r'', '', result, flags=re.DOTALL)
                cleaned = cleaned.strip()
                # Cari JSON di antara kurung kurawal
                json_match = re.search(r'\{[^}]+\}', cleaned)
                if json_match:
                    return json.loads(json_match.group())
                return json.loads(cleaned)
        except Exception as e:
            logger.warning(f"LLM context extraction failed: {e}")
        
        return self._rule_based_context(text)

    def validate_field(self, field_name: str, value: str) -> dict:
        """
        Validasi field menggunakan pengetahuan LLM.
        
        Args:
            field_name: Nama field yang divalidasi
            value: Nilai field
            
        Returns:
            Dict dengan validation result
        """
        if not self.enabled:
            return {"valid": True, "confidence": 0.8, "reason": "Rule-based validation"}
        
        try:
            field_context = FIELD_CONTEXT.get(field_name, "Field umum")
            prompt = f"""
Validasi nilai field berikut:
Field: {field_name}
Konteks field: {field_context}
Nilai: {value}

Apakah nilai ini valid untuk field tersebut? 
Jawab dalam format JSON:
{{"valid": true/false, "confidence": 0-1, "reason": "...", "suggestion": "..."}}
"""
            result = self._call_llm(prompt)
            if result:
                return json.loads(result)
        except Exception as e:
            logger.warning(f"LLM validation failed: {e}")
        
        return {"valid": True, "confidence": 0.8, "reason": "Fallback validation"}

    def classify_document(self, text: str) -> str:
        """
        Klasifikasi jenis dokumen.
        
        Args:
            text: OCR text
            
        Returns:
            Document type string
        """
        if not self.enabled:
            return self._rule_based_classification(text)
        
        try:
            prompt = f"""
Klasifikasi jenis dokumen pemerintahan Indonesia berikut. Pilih dari:
- Surat Pernyataan
- SPM (Surat Perintah Membayar)
- DIPA
- Surat Dinas
- Laporan
- Lainnya

Dokumen:
{text[:500]}

Jawab hanya dengan nama jenis dokumen.
"""
            result = self._call_llm(prompt)
            return result.strip() if result else "Tidak diketahui"
        except Exception as e:
            logger.warning(f"LLM classification failed: {e}")
            return self._rule_based_classification(text)

    def extract_spm_document(self, ocr_text: str) -> dict:
        """
        Ekstraksi dokumen SPM menggunakan LLM dengan context khusus.
        
        Args:
            ocr_text: Teks hasil OCR dari dokumen SPM
            
        Returns:
            Dict dengan struktur JSON terstruktur sesuai skema SPM
            
        Example:
            >>> refiner = ContextRefiner()
            >>> spm = refiner.extract_spm_document(ocr_text)
            >>> spm['satuan_kerja']['nama']
            'DITJEN BINA BANGDA KEMENTERIAN DALAM NEGERI'
        """
        if not self.enabled:
            return self._rule_based_spm_extraction(ocr_text)
        
        try:
            # Bangun prompt dengan few-shot examples
            few_shot_examples = ""
            for ex in SPM_FEW_SHOT_EXAMPLES:
                few_shot_examples += f"\nContoh:\nInput: {ex['input']}\nOutput: {json.dumps(ex['output'])}\n"
            
            prompt = f"""{SPM_SYSTEM_PROMPT}
{SPM_USER_PROMPT_TEMPLATE.format(ocr_text=ocr_text)}
Few-shot examples:
{few_shot_examples}

PENTING: Hanya jawab dengan JSON murni, tidak ada tag pikir pikir, tidak ada penjelasan."""
            
            result = self._call_llm(prompt)
            if result:
                # Bersihkan output dari tag pemikiran dan karakter non-JSON
                import re
                cleaned = re.sub(r'', '', result, flags=re.DOTALL)
                cleaned = re.sub(r'```json|```', '', cleaned, flags=re.DOTALL)
                cleaned = cleaned.strip()
                # Cari JSON di antara kurung kurawal
                json_match = re.search(r'\{.*\}', cleaned, flags=re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                return json.loads(cleaned)
        except Exception as e:
            logger.warning(f"LLM SPM extraction failed: {e}")
        
        return self._rule_based_spm_extraction(ocr_text)

    def _rule_based_spm_extraction(self, text: str) -> dict:
        """Rule-based SPM extraction fallback."""
        from .nlp_processor import get_nlp_processor
        nlp = get_nlp_processor()
        entities = nlp.extract_entities(text)
        
        return {
            "jenis_dokumen": "Surat Pernyataan Tanggung Jawab Belanja",
            "nomor": entities.get("nomor_surat", ""),
            "satuan_kerja": {
                "kode": entities.get("kode_satuan_kerja", ""),
                "nama": entities.get("nama_satuan_kerja", ""),
            },
            "dipa": {
                "tanggal": entities.get("tanggal", ""),
                "nomor": entities.get("nomor_dipa", ""),
                "revisi_ke": "",
            },
            "klasifikasi_belanja": "",
            "rincian_pembayaran": [],
            "total_jumlah_rp": 0,
            "total_potongan_rp": 0,
            "keterangan": "",
            "tempat_tanggal": "",
            "penandatangan": {"jabatan": "", "nama": "", "nip": ""},
        }

    def _call_llm(self, prompt: str) -> Optional[str]:
        """Call LLM API."""
        if LLM_CONFIG["provider"] == "anthropic":
            message = self._client.messages.create(
                model=LLM_CONFIG["model"],
                max_tokens=LLM_CONFIG["max_tokens"],
                system="Anda adalah asisten ahli dokumen pemerintahan Indonesia.",
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text
            
        elif LLM_CONFIG["provider"] == "openai":
            response = self._client.chat.completions.create(
                model=LLM_CONFIG.get("model", "gpt-3.5-turbo"),
                messages=[
                    {"role": "system", "content": "Anda adalah asisten ahli dokumen pemerintahan Indonesia."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=LLM_CONFIG["max_tokens"],
                temperature=0.1,
            )
            return response.choices[0].message.content.strip()
            
        elif LLM_CONFIG["provider"] == "groq":
            # Groq API (OpenAI-compatible)
            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": LLM_CONFIG.get("model", "qwen/qwen3-32b"),
                "messages": [
                    {"role": "system", "content": "Anda adalah asisten ahli dokumen pemerintahan Indonesia."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": LLM_CONFIG["max_tokens"],
                "temperature": 0.1,
            }
            resp = self._client.post(self._api_url, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
            
        elif LLM_CONFIG["provider"] == "local":
            import requests
            response = self._client.post(
                self._api_url,
                json={
                    "model": LLM_CONFIG.get("model", "qwen:7b"),
                    "prompt": prompt,
                    "stream": False,
                }
            )
            return response.json().get("response", "")
        
        return None

    # ============================================================
    # Rule-based fallback (saat LLM tidak tersedia)
    # ============================================================

    def _rule_based_correction(self, wrong: str, context: Optional[str] = None) -> Optional[str]:
        """Rule-based typo correction."""
        from .nlp_processor import get_nlp_processor
        nlp = get_nlp_processor()
        return nlp.normalize(wrong) if wrong else None

    def _rule_based_context(self, text: str) -> dict:
        """Rule-based context extraction."""
        from .nlp_processor import get_nlp_processor
        nlp = get_nlp_processor()
        entities = nlp.extract_entities(text)
        
        doc_type = "unknown"
        if "surat pernyataan" in text.lower():
            doc_type = "Surat Pernyataan"
        elif "spm" in text.lower() or "surat perintah" in text.lower():
            doc_type = "SPM"
        
        return {
            "jenis_dokumen": doc_type,
            "instansi_terkait": entities.get("nama_satuan_kerja", ""),
            "periode": entities.get("tanggal", ""),
            "entities": entities,
        }

    def _rule_based_classification(self, text: str) -> str:
        """Rule-based document classification."""
        text_lower = text.lower()
        if "surat pernyataan" in text_lower:
            return "Surat Pernyataan"
        elif "surat perintah" in text_lower:
            return "SPM"
        elif "dipa" in text_lower:
            return "DIPA"
        elif "surat dinas" in text_lower:
            return "Surat Dinas"
        return "Dokumen Pemerintahan"


# ============================================================
# Module Singleton
# ============================================================

_refiner: Optional[ContextRefiner] = None


def get_context_refiner() -> ContextRefiner:
    """Get singleton ContextRefiner instance."""
    global _refiner
    if _refiner is None:
        _refiner = ContextRefiner()
    return _refiner


if __name__ == "__main__":
    refiner = ContextRefiner()
    print(f"LLM enabled: {refiner.enabled}")
    print(f"Provider: {LLM_CONFIG['provider']}")
    
    # Test typo correction
    correction = refiner.correct_typo("DITJFN")
    print(f"Correction for 'DITJFN': {correction}")
    
    # Test context extraction
    context = refiner.extract_context("Nomor : 002/F.2/LS/III/2025")
    print(f"Context: {context}")
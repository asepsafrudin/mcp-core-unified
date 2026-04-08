"""
NLP Processor untuk pipeline OCR PaddleOCR.

Modul ini menggunakan NLP (Natural Language Processing) untuk:
1. Normalisasi teks hasil OCR (typo correction, spacing)
2. Named Entity Recognition (NER) untuk ekstraksi entitas penting
3. Pattern matching untuk field-field spesifik dokumen
4. Confidence scoring untuk kualitas OCR
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ============================================================
# NER Entity Definitions
# ============================================================

ENTITY_PATTERNS = {
    "nomor_surat": {
        "pattern": r'Nomor\s*:\s*([\w\d./\-]+)',
        "group": 1,
    },
    "kode_satuan_kerja": {
        "pattern": r'Kode\s+Satuan\s+Kerja\s*\n?\s*:\s*([\d]+)',
        "group": 1,
    },
    "nama_satuan_kerja": {
        "pattern": r'Nama\s+Satuan\s+Kerja\s*\n?\s*:\s*(.+?)(?:\n|$)',
        "group": 1,
    },
    "nomor_dipa": {
        "pattern": r'(\d[\d./]+/\d+)',
        "group": 1,
    },
    "tanggal": {
        "pattern": r'(\d+\s+(?:Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s+\d{4})',
        "group": 1,
    },
    "nama_penerima": {
        "pattern": r'([A-Z][a-z]+(?:,\s*[A-Z]+\.?\s*(?:[A-Z]+\.?)?)?)',
        "group": 1,
    },
    "nik_nip": {
        "pattern": r'NIP\.?\s*([\d\s]+)',
        "group": 1,
    },
    "jumlah_uang": {
        "pattern": r'(Rp\.?\s*[\d.,]+)',
        "group": 1,
    },
}


# ============================================================
# Known Corrections Database
# ============================================================

# Common OCR typos mapped to correct values
KNOWN_TYPOS = {
    # Department names
    "DITJFN": "DITJEN",
    "DITJEN BINABANGDA": "DITJEN BINA BANGDA",
    "KEMENTERIAN DALAMNEGERI": "KEMENTERIAN DALAM NEGERI",

    # Title/degree abbreviations
    "S. KOm": "S.Kom",
    "S.IP": "S.IP",
    "S.Sos": "S.Sos",
    "S.E": "S.E",
    "S.H": "S.H",
    "SH.": "S.H",
    "S.Hu": "S.Hu",

    # Common words in Indonesian government docs
    "PERUNDANG": "Perundang",
    "FASILITASI": "Fasilitasi",
    "KOORDINASI": "Koordinasi",
    "VERIFIKASI": "Verifikasi",
    "EVALUASI": "Evaluasi",
    "PENYUSUNAN": "Penyusunan",
}

# Digit-to-letter corrections (common OCR errors)
# Pattern-based - applied after name detection
DIGIT_IN_NAME_PATTERNS = [
    (r'([A-Z][a-z]+)(\d)([A-Z])', r'\g<1> \g<2>, \g<3>'),  # "Sisco8H" → "Sisco 8, H"
    (r'(\d)([A-Z])\b', r'\g<1>. \g<2>'),  # "8H" → "8. H"
]

# Known specific corrections for names
SPECIFIC_NAME_CORRECTIONS = {
    "Sisco8H": "Sisco, SH",
    "Sisco 8H": "Sisco, SH",
    "Sisco8, H": "Sisco, SH",
}

# Number normalization
NUMBER_NORMALIZERS = {
    "I11": "III",  # Roman numeral
    "001": "001",
}


class NLPProcessor:
    """
    NLP processor untuk OCR pipeline.

    Contoh penggunaan:
        processor = NLPProcessor()
        corrected_text = processor.normalize(ocr_text)
        entities = processor.extract_entities(ocr_text)
        quality = processor.assess_quality(ocr_result)
    """

    def __init__(self):
        self.typos = dict(KNOWN_TYPOS)  # copy
        self.name_corrections = dict(SPECIFIC_NAME_CORRECTIONS)  # copy
        self.number_normalizers = NUMBER_NORMALIZERS
        self._learned_corrections: dict = {}
        self._apply_learned_corrections()

    def _apply_learned_corrections(self):
        """Apply corrections from learning store."""
        try:
            from .learning_store import get_learning_store
            store = get_learning_store()
            # Merge learned corrections (learned has lower priority than built-in)
            self._learned_corrections = store.get_common_corrections(min_count=1)
            # Apply learned corrections (but built-in takes precedence)
            for wrong, correct in self._learned_corrections.items():
                if wrong.upper() not in self.typos:
                    self.typos[wrong.upper()] = correct.upper()
        except Exception as e:
            logger.debug(f"Could not load learned corrections: {e}")

    def normalize(self, text: str, track_changes: bool = False) -> str:
        """
        Normalize OCR text by applying known corrections.

        Args:
            text: Raw OCR text
            track_changes: If True, return dict with changes instead of string

        Returns:
            Normalized text (or dict if track_changes=True)

        Example:
            >>> processor = NLPProcessor()
            >>> processor.normalize("DITJFN BINABANGDA")
            'DITJEN BINA BANGDA'
        """
        result = text
        changes = {}  # Track {original: corrected}

        # Apply known typo corrections
        for wrong, right in self.typos.items():
            if wrong in result:
                changes[wrong] = right
                result = result.replace(wrong, right)

        # Apply specific name corrections first
        for wrong, right in self.name_corrections.items():
            if wrong in result:
                changes[wrong] = right
                result = result.replace(wrong, right)
        
        # Apply pattern-based digit corrections
        original = result
        for pattern, repl in DIGIT_IN_NAME_PATTERNS:
            result = re.sub(pattern, repl, result)
        if result != original:
            changes["pattern_correction"] = "applied"

        # Apply number normalizations
        for wrong, right in self.number_normalizers.items():
            pattern = r'\b' + re.escape(wrong) + r'\b'
            if re.search(pattern, result):
                changes[wrong] = right
                result = re.sub(pattern, right, result)

        # Fix spacing around colons (OCR often adds spaces)
        result = re.sub(r'\s*:\s*', ': ', result)
        result = re.sub(r'\s*\n\s*', '\n', result)

        # Ensure proper spacing after commas in names
        result = re.sub(r',\s*', ', ', result)

        if track_changes:
            return result.strip(), changes
        return result.strip()

    def extract_entities(self, text: str, context: Optional[dict] = None) -> dict:
        """
        Extract named entities from OCR text.

        Args:
            text: OCR text
            context: Additional context (e.g., document_type)

        Returns:
            Dict of extracted entities

        Example:
            >>> processor = NLPProcessor()
            >>> entities = processor.extract_entities(text)
            >>> entities['nomor_surat']
            '002/F.2/LS/III/2025'
        """
        entities = {}

        for entity_name, config in ENTITY_PATTERNS.items():
            pattern = config["pattern"]
            group = config.get("group", 0)
            match = re.search(pattern, text)
            if match:
                value = match.group(group).strip()
                entities[entity_name] = value

        return entities

    def extract_document_fields(self, text: str) -> dict:
        """
        Extract structured fields from SPM document.

        Returns:
            Dict with normalized field values

        Example:
            >>> processor = NLPProcessor()
            >>> fields = processor.extract_document_fields(text)
            >>> fields['dipa']['tanggal']
            '21 Februari 2025'
        """
        fields = {}

        # Normalize text first
        normalized = self.normalize(text)

        # Extract header fields
        header_match = re.search(
            r'Nomor\s*:\s*(.+)', normalized
        )
        if header_match:
            fields["nomor"] = header_match.group(1).strip()
            # Fix Roman numeral
            fields["nomor"] = re.sub(r'\bI11\b', 'III', fields["nomor"])

        # Extract DIPA date and number
        dipa_match = re.search(
            r'Tgl/No\.\s*DIPA\s+Revisi\s+ke\s+(\d+)\s*\n?\s*:\s*(\d+\s+\w+\s+\d{4})/([\d./]+/\d+)',
            normalized
        )
        if dipa_match:
            fields["dipa"] = {
                "revisi_ke": dipa_match.group(1),
                "tanggal": dipa_match.group(2),
                "nomor": dipa_match.group(3),
            }
        else:
            # Alternative pattern
            dipa_match2 = re.search(
                r'Tgl/No\.\s*DIPA[^:]*:\s*(.+)', normalized
            )
            if dipa_match2:
                dipa_text = dipa_match2.group(1).strip()
                parts = dipa_text.split("/")
                if len(parts) >= 2:
                    fields["dipa"] = {
                        "tanggal": parts[0].strip(),
                        "nomor": "/".join(parts[1:]).strip(),
                        "revisi_ke": "",
                    }

        return fields

    def assess_quality(self, ocr_result: dict) -> dict:
        """
        Assess OCR result quality and suggest improvements.

        Args:
            ocr_result: Dict with 'lines' key containing OCR results

        Returns:
            Dict with quality metrics

        Example:
            >>> processor = NLPProcessor()
            >>> quality = processor.assess_quality(ocr_result)
            >>> quality['low_confidence_lines']
            2
        """
        lines = ocr_result.get("lines", [])
        total_lines = len(lines)

        if total_lines == 0:
            return {
                "total_lines": 0,
                "avg_confidence": 0.0,
                "low_confidence_lines": 0,
                "corrected_lines": 0,
                "quality_score": 0.0,
                "suggestions": ["No text extracted"],
            }

        low_confidence = 0
        corrected = 0
        confidences = []

        for line in lines:
            confidence = line.get("score", 0.0)
            confidences.append(confidence)

            if confidence < 0.90:
                low_confidence += 1

            # Check if text was corrected
            text = line.get("text", "")
            original_text = line.get("original_text", text)
            if text != original_text:
                corrected += 1

        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        quality_score = (
            avg_confidence * 0.6
            + (1 - low_confidence / max(total_lines, 1)) * 0.2
            + (1 - corrected / max(total_lines, 1)) * 0.2
        )

        suggestions = []
        if avg_confidence < 0.90:
            suggestions.append("Low overall confidence - consider image enhancement")
        if low_confidence > total_lines * 0.2:
            suggestions.append("Many low-confidence lines - check image quality")
        if corrected > total_lines * 0.1:
            suggestions.append("Many corrections applied - consider better OCR model")

        return {
            "total_lines": total_lines,
            "avg_confidence": round(avg_confidence, 4),
            "low_confidence_lines": low_confidence,
            "corrected_lines": corrected,
            "quality_score": round(quality_score, 4),
            "suggestions": suggestions,
        }


# ============================================================
# Module Singleton
# ============================================================

_nlp_processor: Optional[NLPProcessor] = None


def get_nlp_processor() -> NLPProcessor:
    """Get singleton NLPProcessor instance."""
    global _nlp_processor
    if _nlp_processor is None:
        _nlp_processor = NLPProcessor()
    return _nlp_processor


def normalize_ocr_text(text: str) -> str:
    """Convenience function to normalize OCR text."""
    return get_nlp_processor().normalize(text)


def extract_entities(text: str) -> dict:
    """Convenience function to extract entities."""
    return get_nlp_processor().extract_entities(text)


if __name__ == "__main__":
    # Test
    processor = NLPProcessor()

    sample = """DITJFN BINABANGDAKEMENTERIAN DALAMNEGERI
    Nomor : 002/F.2/LS/I11/2025
    Yonatan Maryon Sisco8H
    Sesuai SK 800.1.2.5-012/Kep/Bangda/2025"""

    print("Original:")
    print(sample)
    print("\nNormalized:")
    print(processor.normalize(sample))
    print("\nEntities:")
    print(processor.extract_entities(sample))
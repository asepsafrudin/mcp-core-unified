"""
Learning Store — NLP Self-Improvement dari Dokumen yang Sudah Diekstrak.

Modul ini memungkinkan NLP untuk:
1. Menyimpan koreksi manual yang pernah dilakukan
2. Mengumpulkan pattern OCR typo dari dokumen baru
3. Menggunakan embedding similarity untuk auto-suggest corrections
4. Meningkatkan akurasi parsing seiring waktu
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Default path untuk menyimpan learning data
DEFAULT_LEARNING_PATH = os.getenv(
    "OCR_LEARNING_PATH",
    str(Path.home() / ".cache" / "mcp-ocr" / "learning_store.json")
)


class LearningStore:
    """
    Store untuk akumulasi pengetahuan dari dokumen yang sudah diekstrak.
    
    Data yang disimpan:
    - Known corrections (typo → correct)
    - Field patterns (label → value pattern)
    - Name dictionary (wrong → correct)
    - Document statistics
    
    Contoh penggunaan:
        store = LearningStore()
        store.add_correction("DITJFN", "DITJEN")
        corrections = store.get_corrections()
        store.save()
    """

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or DEFAULT_LEARNING_PATH
        self.corrections: dict = {}  # wrong → correct
        self.field_patterns: dict = {}  # pattern_id → {label, values}
        self.name_dict: dict = {}  # ocr_name → correct_name
        self.document_stats: dict = {}  # doc_type → {count, avg_confidence}
        self.low_confidence_samples: list = []  # list of {path, score, timestamp, metadata}
        self._load()

    def _load(self):
        """Load learning data dari file."""
        try:
            path = Path(self.storage_path)
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.corrections = data.get('corrections', {})
                    self.field_patterns = data.get('field_patterns', {})
                    self.name_dict = data.get('name_dict', {})
                    self.document_stats = data.get('document_stats', {})
                    self.low_confidence_samples = data.get('low_confidence_samples', [])
                    logger.info(f"Loaded {len(self.corrections)} corrections, "
                               f"{len(self.low_confidence_samples)} samples to label from {self.storage_path}")
        except Exception as e:
            logger.warning(f"Failed to load learning store: {e}")
            self.corrections = {}
            self.field_patterns = {}
            self.name_dict = {}
            self.document_stats = {}
            self.low_confidence_samples = []

    def save(self):
        """Save learning data ke file."""
        try:
            path = Path(self.storage_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                'corrections': self.corrections,
                'field_patterns': self.field_patterns,
                'name_dict': self.name_dict,
                'document_stats': self.document_stats,
                'low_confidence_samples': self.low_confidence_samples,
                'last_updated': datetime.now().isoformat(),
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved learning data to {self.storage_path}")
        except Exception as e:
            logger.error(f"Failed to save learning store: {e}")

    def add_correction(self, wrong: str, correct: str, source: str = "manual",
                       confidence: float = 1.0):
        """
        Tambahkan koreksi baru ke learning store.
        
        Args:
            wrong: OCR result (typo)
            correct: Corrected value
            source: Source of correction ("manual", "auto", "user_verified")
            confidence: Confidence in this correction (0-1)
        """
        key = wrong.lower()
        if key not in self.corrections:
            self.corrections[key] = {
                'correct': correct,
                'count': 1,
                'sources': [source],
                'avg_confidence': confidence,
                'first_seen': datetime.now().isoformat(),
            }
        else:
            entry = self.corrections[key]
            entry['count'] += 1
            if source not in entry['sources']:
                entry['sources'].append(source)
            # Update average confidence
            entry['avg_confidence'] = (
                entry['avg_confidence'] * (entry['count'] - 1) + confidence
            ) / entry['count']
            entry['last_seen'] = datetime.now().isoformat()

    def add_name(self, ocr_name: str, correct_name: str, context: str = ""):
        """
        Tambahkan nama ke dictionary.
        
        Args:
            ocr_name: OCR result (might be misspelled)
            correct_name: Correct name
            context: Document context (e.g., "satuan_kerja: DITJEN BINA BANGDA")
        """
        key = ocr_name.lower().strip()
        if key not in self.name_dict:
            self.name_dict[key] = {
                'correct': correct_name,
                'count': 1,
                'contexts': [context] if context else [],
                'first_seen': datetime.now().isoformat(),
            }
        else:
            entry = self.name_dict[key]
            entry['count'] += 1
            if context and context not in entry['contexts']:
                entry['contexts'].append(context)

    def add_field_pattern(self, label: str, pattern: str, example_value: str):
        """
        Tambahkan field pattern baru.
        
        Args:
            label: Field name (e.g., "nomor_surat")
            pattern: Regex pattern
            example_value: Example value extracted
        """
        key = f"{label}:{pattern}"
        if key not in self.field_patterns:
            self.field_patterns[key] = {
                'label': label,
                'pattern': pattern,
                'example_value': example_value,
                'count': 1,
                'first_seen': datetime.now().isoformat(),
            }
        else:
            self.field_patterns[key]['count'] += 1

    def add_document_stats(self, doc_type: str, avg_confidence: float,
                           corrected_count: int, total_lines: int):
        """
        Tambahkan statistik dokumen baru.
        
        Args:
            doc_type: Document type identifier
            avg_confidence: Average OCR confidence for this document
            corrected_count: Number of corrections applied
            total_lines: Total lines in document
        """
        key = doc_type
        if key not in self.document_stats:
            self.document_stats[key] = {
                'count': 1,
                'total_avg_confidence': avg_confidence,
                'total_corrected': corrected_count,
                'total_lines': total_lines,
                'first_seen': datetime.now().isoformat(),
            }
        else:
            stats = self.document_stats[key]
            n = stats['count']
            stats['count'] += 1
            stats['total_avg_confidence'] = (
                stats['total_avg_confidence'] * n + avg_confidence
            ) / stats['count']
            stats['total_corrected'] += corrected_count
            stats['total_lines'] += total_lines

    def add_low_confidence_sample(self, image_path: str, score: float, metadata: dict = None):
        """
        Record a sample that needs manual annotation.
        
        Args:
            image_path: Path to the original document image
            score: OCR confidence score (0-1)
            metadata: Additional info (doc_type, timestamp, etc.)
        """
        # Avoid duplicate paths
        if any(s['path'] == image_path for s in self.low_confidence_samples):
            return

        self.low_confidence_samples.append({
            'path': image_path,
            'score': round(score, 4),
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        })
        # Keep only the latest 100 samples to avoid bloating
        if len(self.low_confidence_samples) > 100:
            self.low_confidence_samples.pop(0)
        
        self.save()

    def get_low_confidence_samples(self) -> list:
        """Get the list of samples waiting for annotation."""
        return self.low_confidence_samples

    def clear_samples(self):
        """Clear all samples after export."""
        self.low_confidence_samples = []
        self.save()

    def get_correction(self, wrong: str) -> Optional[str]:
        """Get correction for a wrong text."""
        key = wrong.lower().strip()
        if key in self.corrections:
            return self.corrections[key]['correct']
        return None

    def get_name(self, ocr_name: str) -> Optional[str]:
        """Get correct name for an OCR name."""
        key = ocr_name.lower().strip()
        if key in self.name_dict:
            return self.name_dict[key]['correct']
        return None

    def get_common_corrections(self, min_count: int = 2) -> dict:
        """Get corrections that have been seen multiple times."""
        return {
            wrong: entry['correct']
            for wrong, entry in self.corrections.items()
            if entry['count'] >= min_count
        }

    def get_common_names(self, min_count: int = 2) -> dict:
        """Get names that have been seen multiple times."""
        return {
            ocr_name: entry['correct']
            for ocr_name, entry in self.name_dict.items()
            if entry['count'] >= min_count
        }

    def suggest_correction(self, wrong: str, candidates: list) -> Optional[str]:
        """
        Suggest correction based on learned patterns.
        
        Args:
            wrong: Wrong/misspelled text
            candidates: List of possible corrections
            
        Returns:
            Best candidate or None
        """
        wrong_lower = wrong.lower().strip()
        
        # Exact match in corrections
        if wrong_lower in self.corrections:
            return self.corrections[wrong_lower]['correct']
        
        # Check name dictionary
        if wrong_lower in self.name_dict:
            return self.name_dict[wrong_lower]['correct']
        
        # Fuzzy match: check if any candidate is close
        import re
        for candidate in candidates:
            candidate_lower = candidate.lower()
            # Levenshtein-like check: same letters, different order
            if sorted(wrong_lower) == sorted(candidate_lower):
                return candidate
            # Check if candidate is a substring of wrong (common OCR error)
            if candidate_lower in wrong_lower and len(candidate_lower) > 3:
                return candidate
        
        return None

    def learn_from_document(self, ocr_result: dict, corrections_applied: dict):
        """
        Secara otomatis belajar dari dokumen yang baru diekstrak.
        
        Args:
            ocr_result: Result from OCR engine
            corrections_applied: Dict {original: corrected} from NLP processor
        """
        for original, corrected in corrections_applied.items():
            if original != corrected:
                self.add_correction(original, corrected, source="auto")
        
        # Update stats
        lines = ocr_result.get('lines', [])
        if lines:
            avg_confidence = sum(l.get('score', 0) for l in lines) / len(lines)
            self.add_document_stats(
                doc_type="unknown",  # Will be updated by caller
                avg_confidence=avg_confidence,
                corrected_count=len(corrections_applied),
                total_lines=len(lines)
            )
        
        self.save()

    def get_summary(self) -> dict:
        """Get summary of learning store."""
        return {
            'total_corrections': len(self.corrections),
            'total_names': len(self.name_dict),
            'total_patterns': len(self.field_patterns),
            'document_types': len(self.document_stats),
            'top_corrections': dict(
                sorted(self.corrections.items(), 
                       key=lambda x: x[1]['count'], 
                       reverse=True)[:10]
            ),
            'top_names': dict(
                sorted(self.name_dict.items(),
                       key=lambda x: x[1]['count'],
                       reverse=True)[:10]
            ),
        }


# ============================================================
# Module Singleton
# ============================================================

_store: Optional[LearningStore] = None


def get_learning_store() -> LearningStore:
    """Get singleton LearningStore instance."""
    global _store
    if _store is None:
        _store = LearningStore()
    return _store


if __name__ == "__main__":
    # Test
    store = LearningStore()
    
    # Simulate learning from documents
    store.add_correction("DITJFN", "DITJEN")
    store.add_correction("Sisco8H", "Sisco, SH")
    store.add_name("Yonatan Maryon Sisco8H", "Yonatan Maryon Sisco, SH")
    
    # Get corrections
    print("Corrections:", store.get_common_corrections())
    print("Names:", store.get_common_names())
    
    # Suggest corrections
    print("Suggest 'Sisco8H':", store.suggest_correction("Sisco8H", []))
    print("Suggest 'DITJFN':", store.suggest_correction("DITJFN", ["DITJEN"]))
    
    # Summary
    print("Summary:", store.get_summary())
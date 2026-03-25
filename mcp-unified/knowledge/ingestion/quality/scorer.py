"""
Quality Scorer

Menilai kualitas dokumen berdasarkan:
- Text clarity (OCR quality untuk PDF)
- Structure quality (headers, paragraphs)
- Content completeness
- Duplicate detection
"""

import re
from typing import List, Dict, Any


class QualityScorer:
    """
    Score dokumen 0.0 - 1.0 berdasarkan berbagai faktor kualitas.
    """
    
    def __init__(self):
        """Initialize quality scorer."""
        self.weights = {
            'text_clarity': 0.3,
            'structure': 0.2,
            'completeness': 0.3,
            'readability': 0.2
        }
    
    def score(self, text: str, chunks: List[Dict]) -> float:
        """
        Calculate overall quality score.
        
        Args:
            text: Full extracted text
            chunks: List of chunks
            
        Returns:
            Score 0.0 - 1.0
        """
        if not text or not text.strip():
            return 0.0
        
        scores = {
            'text_clarity': self._score_text_clarity(text),
            'structure': self._score_structure(text, chunks),
            'completeness': self._score_completeness(text, chunks),
            'readability': self._score_readability(text)
        }
        
        # Weighted average
        final_score = sum(
            scores[k] * self.weights[k] for k in scores
        )
        
        return round(final_score, 2)
    
    def _score_text_clarity(self, text: str) -> float:
        """
        Score text clarity (khususnya untuk OCR).
        
        Cek:
        - Ratio karakter readable vs garbled
        - Presence of gibberish characters
        """
        if not text:
            return 0.0
        
        # Normal characters (alphanumeric, common punctuation, whitespace)
        normal_chars = re.compile(r'[\w\s\.,;:\-\(\)\[\]"\'\/\\@\#\$\%\&\*\+\=\<\>\?\!\^\`\~\n]')
        
        total_chars = len(text)
        normal_count = len(normal_chars.findall(text))
        
        if total_chars == 0:
            return 0.0
        
        clarity = normal_count / total_chars
        
        # Penalty untuk excessive special characters
        special_ratio = 1.0 - clarity
        if special_ratio > 0.1:
            clarity -= special_ratio * 0.5
        
        return max(0.0, min(1.0, clarity))
    
    def _score_structure(self, text: str, chunks: List[Dict]) -> float:
        """
        Score document structure.
        
        Cek:
        - Presence of headers/sections
        - Paragraph organization
        - Consistent formatting
        """
        if not text:
            return 0.0
        
        score = 0.5  # Base score
        
        # Check untuk headers (##, ===, dll)
        header_patterns = [
            r'\n##+\s+',  # Markdown headers
            r'\n===+\s*\n',  # Section separators
            r'\n---\s+\w+',  # Page markers
        ]
        
        for pattern in header_patterns:
            if re.search(pattern, text):
                score += 0.15
        
        # Check paragraph structure
        paragraphs = text.split('\n\n')
        if len(paragraphs) > 3:
            score += 0.1
        
        # Check chunk distribution
        if chunks:
            chunk_sizes = [len(c['content']) for c in chunks]
            avg_size = sum(chunk_sizes) / len(chunk_sizes)
            
            # Ideal chunk size: 300-700 chars
            if 200 <= avg_size <= 800:
                score += 0.1
            elif avg_size < 100 or avg_size > 1500:
                score -= 0.1
        
        return max(0.0, min(1.0, score))
    
    def _score_completeness(self, text: str, chunks: List[Dict]) -> float:
        """
        Score content completeness.
        
        Cek:
        - Text length vs expected
        - Truncation indicators
        - Content density
        """
        if not text:
            return 0.0
        
        score = 0.5
        
        # Check text length
        text_len = len(text)
        if text_len < 100:
            score -= 0.3  # Too short
        elif text_len > 1000:
            score += 0.2  # Good length
        
        # Check for truncation indicators
        truncation_indicators = [
            '...', '…', '[truncated]', '(continued)', 
            'page', 'halaman', 'lanjutan'
        ]
        
        for indicator in truncation_indicators:
            if indicator.lower() in text.lower():
                score -= 0.1
        
        # Check word density (kata per karakter)
        words = text.split()
        if len(words) > 0:
            word_density = len(words) / len(text)
            # Normal density: 0.15 - 0.25
            if 0.1 <= word_density <= 0.3:
                score += 0.1
            elif word_density < 0.05:
                score -= 0.2  # Too sparse
        
        # Check chunks coverage
        if chunks:
            total_chunk_content = sum(len(c['content']) for c in chunks)
            if total_chunk_content >= len(text) * 0.9:
                score += 0.1
        
        return max(0.0, min(1.0, score))
    
    def _score_readability(self, text: str) -> float:
        """
        Score text readability.
        
        Cek:
        - Average word length
        - Sentence length
        - Language consistency
        """
        if not text:
            return 0.0
        
        score = 0.5
        
        # Split into sentences (rough approximation)
        sentences = re.split(r'[.!?。！？]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return 0.0
        
        # Average sentence length
        avg_sentence_len = sum(len(s) for s in sentences) / len(sentences)
        
        # Ideal sentence length: 50-150 chars
        if 30 <= avg_sentence_len <= 200:
            score += 0.15
        elif avg_sentence_len > 300:
            score -= 0.2  # Too long
        
        # Average word length
        words = text.split()
        if words:
            avg_word_len = sum(len(w) for w in words) / len(words)
            
            # Ideal word length: 4-8 chars (Indonesian/English)
            if 3 <= avg_word_len <= 10:
                score += 0.15
            elif avg_word_len > 15:
                score -= 0.2  # Gibberish or code
        
        # Check for repeating patterns (gibberish indicator)
        if self._has_repeating_patterns(text):
            score -= 0.3
        
        return max(0.0, min(1.0, score))
    
    def _has_repeating_patterns(self, text: str) -> bool:
        """
        Check jika text memiliki repeating patterns yang
        menandakan OCR error atau gibberish.
        """
        # Check untuk repeating characters
        repeating_pattern = re.compile(r'(.)\1{4,}')  # Same char 5+ times
        if repeating_pattern.search(text):
            return True
        
        # Check untuk repeating short sequences
        words = text.split()
        if len(words) < 10:
            return False
        
        # Check word repetition ratio
        unique_words = set(w.lower() for w in words)
        repetition_ratio = 1 - (len(unique_words) / len(words))
        
        # If more than 70% words are the same, likely gibberish
        return repetition_ratio > 0.7
    
    def get_quality_report(self, text: str, chunks: List[Dict]) -> Dict[str, Any]:
        """
        Get detailed quality report.
        
        Returns:
            Dict dengan breakdown scores dan recommendations
        """
        scores = {
            'text_clarity': self._score_text_clarity(text),
            'structure': self._score_structure(text, chunks),
            'completeness': self._score_completeness(text, chunks),
            'readability': self._score_readability(text)
        }
        
        overall = sum(scores[k] * self.weights[k] for k in scores)
        
        # Generate recommendations
        recommendations = []
        
        if scores['text_clarity'] < 0.5:
            recommendations.append(
                "Text clarity rendah - pertimbangkan untuk menggunakan OCR"
            )
        
        if scores['structure'] < 0.5:
            recommendations.append(
                "Struktur dokumen kurang jelas - periksa formatting"
            )
        
        if scores['completeness'] < 0.5:
            recommendations.append(
                "Konten mungkin tidak lengkap - periksa file source"
            )
        
        if scores['readability'] < 0.5:
            recommendations.append(
                "Readability rendah - dokumen mungkin mengandung error"
            )
        
        return {
            'overall_score': round(overall, 2),
            'scores': scores,
            'weights': self.weights,
            'recommendations': recommendations,
            'text_length': len(text),
            'chunk_count': len(chunks)
        }
"""
4-Level Validator - Validasi komprehensif untuk scraped content.

Berdasarkan Autonomous Knowledge Update System:
- Level 1: Basic Validation
- Level 2: Semantic Validation  
- Level 3: Accuracy Validation
- Level 4: Utility Validation
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ValidationResult:
    """Hasil validasi 4-level."""
    validated: bool
    overall_score: float
    level_results: Dict[str, Dict[str, Any]]
    recommendations: List[str]
    should_store: bool
    requires_human_review: bool
    timestamp: datetime = field(default_factory=datetime.now)


class FourLevelValidator:
    """
    4-Level Quality Validation Pipeline.
    
    Mengimplementasikan konsep dari Autonomous Knowledge Update System
    untuk memastikan kualitas knowledge yang tinggi.
    """
    
    def __init__(
        self,
        min_overall_score: float = 0.75,
        store_threshold: float = 0.70,
        review_threshold: float = 0.75,
        min_content_length: int = 100,
    ):
        """
        Initialize validator.
        
        Args:
            min_overall_score: Minimal overall score untuk validated
            store_threshold: Threshold untuk menyimpan (walaupun perlu review)
            review_threshold: Threshold bawah untuk human review
            min_content_length: Minimal panjang konten
        """
        self.min_overall_score = min_overall_score
        self.store_threshold = store_threshold
        self.review_threshold = review_threshold
        self.min_content_length = min_content_length
        
        # Cache untuk duplicate detection
        self._content_hashes: set = set()
    
    async def validate(self, content: Any, context: Optional[Dict] = None) -> ValidationResult:
        """
        Validasi content dengan 4-level validation.
        
        Args:
            content: Content yang akan divalidasi (ExtractedContent)
            context: Context tambahan untuk validation
            
        Returns:
            ValidationResult
        """
        results = {}
        recommendations = []
        
        # LEVEL 1: Basic Validation
        level1 = await self._validate_basic(content)
        results['basic'] = level1
        
        if level1['score'] < 0.6:
            recommendations.append("Basic validation failed - content may be corrupted")
            return self._create_result(results, recommendations, early_exit=True)
        
        # LEVEL 2: Semantic Validation
        level2 = await self._validate_semantic(content)
        results['semantic'] = level2
        
        if level2['score'] < 0.7:
            recommendations.append("Semantic coherence low - consider rephrasing")
        
        # LEVEL 3: Accuracy Validation
        level3 = await self._validate_accuracy(content, context)
        results['accuracy'] = level3
        
        if level3.get('contradictions'):
            recommendations.append(
                f"Found {len(level3['contradictions'])} contradictions with existing knowledge"
            )
        
        # LEVEL 4: Utility Validation
        level4 = await self._validate_utility(content)
        results['utility'] = level4
        
        if level4['score'] < 0.6:
            recommendations.append("Low utility score - may not answer common queries")
        
        return self._create_result(results, recommendations)
    
    async def _validate_basic(self, content: Any) -> Dict[str, Any]:
        """
        Level 1: Basic Validation.
        
        Checks:
        - Content length
        - Format validation
        - Duplicate detection
        """
        score = 1.0
        issues = []
        
        # Check content exists
        if not content or not content.content:
            return {'score': 0.0, 'issues': ['No content'], 'passed': False}
        
        # Check content length
        content_length = len(content.content)
        if content_length < self.min_content_length:
            score -= 0.3
            issues.append(f"Content too short: {content_length} chars")
        elif content_length < 500:
            score -= 0.1
            issues.append(f"Content relatively short: {content_length} chars")
        
        # Check title
        if not content.title or len(content.title) < 5:
            score -= 0.2
            issues.append("Title missing or too short")
        
        # Check URL
        if not content.url:
            score -= 0.2
            issues.append("URL missing")
        
        # Duplicate detection
        content_hash = hashlib.sha256(content.content.encode()).hexdigest()[:16]
        if content_hash in self._content_hashes:
            score -= 0.5
            issues.append("Duplicate content detected")
        else:
            self._content_hashes.add(content_hash)
        
        # Format validation
        if '\x00' in content.content or any(ord(c) < 32 and c not in '\n\r\t' for c in content.content):
            score -= 0.2
            issues.append("Invalid characters in content")
        
        return {
            'score': max(0, score),
            'issues': issues,
            'passed': score >= 0.6,
            'content_length': content_length,
            'content_hash': content_hash,
        }
    
    async def _validate_semantic(self, content: Any) -> Dict[str, Any]:
        """
        Level 2: Semantic Validation.
        
        Checks:
        - Coherence (readability)
        - Topic relevance
        - Language clarity
        """
        score = 1.0
        analysis = {}
        
        text = content.content
        
        # Check coherence: paragraph structure
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        analysis['paragraph_count'] = len(paragraphs)
        
        if len(paragraphs) < 2:
            score -= 0.2
        
        # Check average paragraph length
        avg_para_length = sum(len(p) for p in paragraphs) / max(len(paragraphs), 1)
        analysis['avg_paragraph_length'] = avg_para_length
        
        if avg_para_length < 100:
            score -= 0.1
        
        # Check sentence structure
        sentences = text.split('.')
        avg_sentence_length = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)
        analysis['avg_sentence_length'] = avg_sentence_length
        
        if avg_sentence_length < 5:
            score -= 0.2  # Too short sentences
        elif avg_sentence_length > 50:
            score -= 0.1  # Too long sentences
        
        # Check word diversity (unique words / total words)
        words = text.lower().split()
        unique_words = set(words)
        diversity = len(unique_words) / max(len(words), 1)
        analysis['word_diversity'] = diversity
        
        if diversity < 0.3:
            score -= 0.15  # Low vocabulary diversity
        
        # Check untuk repetitive content
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        most_common = max(word_freq.values()) if word_freq else 0
        if most_common > len(words) * 0.1:  # Word appears >10% of text
            score -= 0.1
        
        return {
            'score': max(0, score),
            'analysis': analysis,
            'word_count': len(words),
            'unique_words': len(unique_words),
        }
    
    async def _validate_accuracy(self, content: Any, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Level 3: Accuracy Validation.
        
        Checks:
        - Cross-reference dengan existing knowledge
        - Contradiction detection
        - Source verification
        """
        score = 1.0
        contradictions = []
        
        # TODO: Implement cross-reference dengan knowledge base
        # Ini memerlukan akses ke AgentKnowledgeBridge
        
        # Source verification
        if hasattr(content, 'metadata') and content.metadata:
            metadata = content.metadata
            
            # Check source type
            source_type = metadata.get('source_type', 'unknown')
            if source_type == 'unknown':
                score -= 0.1
            
            # Check untuk sources/citations
            if 'sources' in metadata and metadata['sources']:
                score += 0.05  # Bonus untuk content dengan citations
            
            # Check untuk PDF/document references di JDIH
            if source_type == 'jdih':
                if metadata.get('pdf_url'):
                    score += 0.05
                if metadata.get('nomor') and metadata.get('tahun'):
                    score += 0.05
        
        # Check untuk tanggal yang masuk akal
        if hasattr(content, 'published_date') and content.published_date:
            from datetime import datetime
            if content.published_date > datetime.now():
                score -= 0.2  # Future date
                contradictions.append("Publication date is in the future")
            elif content.published_date.year < 1900:
                score -= 0.1  # Very old date
        
        return {
            'score': min(1.0, max(0, score)),
            'contradictions': contradictions,
            'source_type': content.metadata.get('source_type', 'unknown') if hasattr(content, 'metadata') else 'unknown',
        }
    
    async def _validate_utility(self, content: Any) -> Dict[str, Any]:
        """
        Level 4: Utility Validation.
        
        Checks:
        - Usefulness scoring
        - Query coverage analysis
        - Information density
        """
        score = 1.0
        metrics = {}
        
        text = content.content
        
        # Information density: ratio of meaningful content to total
        lines = text.split('\n')
        meaningful_lines = [l for l in lines if len(l.strip()) > 20]
        density = len(meaningful_lines) / max(len(lines), 1)
        metrics['information_density'] = density
        
        if density < 0.3:
            score -= 0.2
        
        # Check untuk structured content (headers, lists, etc.)
        has_headers = bool(re.search(r'^#{1,6}\s', text, re.MULTILINE))
        has_lists = bool(re.search(r'^\s*[-*\d]\.', text, re.MULTILINE))
        
        metrics['has_headers'] = has_headers
        metrics['has_lists'] = has_lists
        
        if has_headers:
            score += 0.05
        if has_lists:
            score += 0.05
        
        # Check untuk question-answer pattern (untuk Q&A content)
        qa_patterns = text.count('?') + text.count('Q:') + text.count('A:')
        metrics['qa_indicators'] = qa_patterns
        
        if qa_patterns > 2:
            score += 0.05  # Likely useful Q&A content
        
        # Check untuk legal-specific content (untuk legal domain)
        legal_keywords = ['pasal', 'ayat', 'undang-undang', 'peraturan', 'hukum', 'uu', 'perpres', 'permen']
        legal_score = sum(1 for keyword in legal_keywords if keyword in text.lower())
        metrics['legal_relevance'] = legal_score
        
        if legal_score >= 2:
            score += 0.05  # Bonus untuk legal content
        
        # Check untuk empty/placeholder content
        placeholder_patterns = ['lorem ipsum', 'coming soon', 'under construction', 'not available']
        for pattern in placeholder_patterns:
            if pattern in text.lower():
                score -= 0.5
                break
        
        return {
            'score': min(1.0, max(0, score)),
            'metrics': metrics,
        }
    
    def _create_result(
        self,
        level_results: Dict[str, Dict],
        recommendations: List[str],
        early_exit: bool = False
    ) -> ValidationResult:
        """Create ValidationResult dari level results."""
        
        if early_exit:
            return ValidationResult(
                validated=False,
                overall_score=0.0,
                level_results=level_results,
                recommendations=recommendations,
                should_store=False,
                requires_human_review=True,
            )
        
        # Calculate weighted overall score
        weights = {
            'basic': 0.20,
            'semantic': 0.30,
            'accuracy': 0.30,
            'utility': 0.20,
        }
        
        overall = sum(
            level_results[level]['score'] * weight
            for level, weight in weights.items()
            if level in level_results
        )
        
        return ValidationResult(
            validated=overall >= self.min_overall_score,
            overall_score=overall,
            level_results=level_results,
            recommendations=recommendations,
            should_store=overall >= self.store_threshold,
            requires_human_review=self.review_threshold <= overall < self.min_overall_score,
        )
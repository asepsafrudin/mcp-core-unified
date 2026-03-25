"""
Vision Storage Configuration Module

Configuration untuk hybrid storage system (LTM + SQL) dengan confidence-based filtering.
Mengikuti best practice enterprise: AWS Textract, Google Document AI patterns.
"""

from typing import Dict, Any
from dataclasses import dataclass, field

# =============================================================================
# CONFIDENCE THRESHOLDS
# =============================================================================

CONFIDENCE_THRESHOLDS = {
    'critical': 0.95,    # Auto-verified, no review needed
    'high': 0.80,        # Save to BOTH LTM and SQL (verified)
    'medium': 0.70,      # Save to LTM only, flag for review
    'low': 0.50,         # Reject, queue for manual processing
    'minimum': 0.30      # Absolute minimum, usually discarded
}

# =============================================================================
# STORAGE POLICIES
# =============================================================================

STORAGE_POLICY = {
    # Which results go to which storage
    'high_confidence_to_sql': True,      # Confidence >= 0.8 → SQL + LTM
    'medium_confidence_to_ltm': True,    # Confidence 0.7-0.8 → LTM only
    'low_confidence_reject': True,       # Confidence < 0.7 → Reject
    
    # Additional filtering
    'minimum_text_length': 50,           # Minimum characters to save
    'require_specific_content': True,    # Must have dates/amounts/etc
    
    # Duplicate handling
    'deduplication_enabled': True,       # Check file_hash
    'update_on_duplicate': True,         # Update existing vs insert new
}

# =============================================================================
# RETENTION POLICIES
# =============================================================================

RETENTION_POLICY = {
    'sql_results_days': 365,             # 1 year for structured data
    'ltm_results_days': 90,              # 3 months for LTM
    'audit_log_days': 2555,              # 7 years for compliance
    'auto_cleanup_enabled': True,        # Enable automatic cleanup
}

# =============================================================================
# PROCESSING CONFIGURATION
# =============================================================================

PROCESSING_CONFIG = {
    'default_model': 'llava',
    'ocr_fallback_enabled': True,
    'max_file_size_mb': 50,
    'max_pages_per_pdf': 50,
    'supported_image_formats': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'],
    'supported_document_formats': ['.pdf'],
}

# =============================================================================
# CONFIDENCE CALCULATION WEIGHTS
# =============================================================================

CONFIDENCE_WEIGHTS = {
    'response_length': 0.30,             # 0.0 - 0.3 based on text length
    'uncertainty_penalty': 0.05,         # -0.05 per uncertainty word
    'specificity_bonus': 0.02,           # +0.02 per specific indicator
    'structure_bonus': 0.10,             # +0.10 if well-structured
}

# Uncertainty indicators (penalize these)
UNCERTAINTY_WORDS = [
    "maybe", "perhaps", "possibly", "might", "could be",
    "unclear", "difficult to tell", "hard to say", "not sure",
    "ambiguous", "vague", "uncertain", "unknown"
]

# Specificity indicators (bonus for these)
SPECIFICITY_INDICATORS = [
    r"\d+",                             # Numbers
    r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}",  # Dates
    r"Rp\s*[\d.,]+",                   # Currency (IDR)
    r"\$[\d.,]+",                       # Currency (USD)
    "left", "right", "top", "bottom", "center",
    "red", "blue", "green", "yellow", "black", "white"
]

# =============================================================================
# DOCUMENT TYPE CLASSIFICATION
# =============================================================================

DOCUMENT_TYPES = {
    'invoice': {
        'keywords': ['invoice', 'bill', 'total', 'amount', 'due', 'payment'],
        'required_entities': ['amount', 'date'],
        'confidence_boost': 0.05
    },
    'receipt': {
        'keywords': ['receipt', 'paid', 'change', 'cash', 'card'],
        'required_entities': ['amount', 'date'],
        'confidence_boost': 0.05
    },
    'form': {
        'keywords': ['form', 'application', 'name', 'address', 'phone'],
        'required_entities': [],
        'confidence_boost': 0.03
    },
    'id_card': {
        'keywords': ['ktp', 'sim', 'passport', 'nik', 'identity'],
        'required_entities': ['id_number'],
        'confidence_boost': 0.05
    },
    'contract': {
        'keywords': ['contract', 'agreement', 'party', 'terms', 'clause'],
        'required_entities': ['date', 'parties'],
        'confidence_boost': 0.03
    },
    'report': {
        'keywords': ['report', 'summary', 'analysis', 'findings'],
        'required_entities': ['date'],
        'confidence_boost': 0.02
    }
}

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

DB_TABLE_CONFIG = {
    'table_name': 'vision_results',
    'schema': 'public',
    'high_confidence_view': 'vision_results_high_confidence',
    'stats_view': 'vision_processing_stats',
}

# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class VisionStorageConfig:
    """Configuration class for vision storage"""
    confidence_thresholds: Dict[str, float] = field(default_factory=lambda: CONFIDENCE_THRESHOLDS)
    storage_policy: Dict[str, Any] = field(default_factory=lambda: STORAGE_POLICY)
    retention_policy: Dict[str, int] = field(default_factory=lambda: RETENTION_POLICY)
    processing_config: Dict[str, Any] = field(default_factory=lambda: PROCESSING_CONFIG)
    
    def get_threshold(self, level: str) -> float:
        """Get confidence threshold by level"""
        return self.confidence_thresholds.get(level, 0.70)
    
    def should_save_to_sql(self, confidence: float) -> bool:
        """Determine if result should be saved to SQL based on confidence"""
        if not self.storage_policy['high_confidence_to_sql']:
            return False
        return confidence >= self.get_threshold('high')
    
    def should_save_to_ltm(self, confidence: float) -> bool:
        """Determine if result should be saved to LTM based on confidence"""
        if not self.storage_policy['medium_confidence_to_ltm']:
            return False
        return confidence >= self.get_threshold('medium')
    
    def get_storage_decision(self, confidence: float) -> str:
        """
        Get storage decision based on confidence score
        Returns: 'sql+ltm', 'ltm_only', 'reject'
        """
        if confidence >= self.get_threshold('high'):
            return 'sql+ltm'
        elif confidence >= self.get_threshold('medium'):
            return 'ltm_only'
        else:
            return 'reject'


@dataclass
class ProcessingResult:
    """Data class for processing result metadata"""
    file_name: str
    file_path: str = ""
    file_hash: str = ""
    file_size_bytes: int = 0
    mime_type: str = ""
    
    extracted_text: str = ""
    confidence_score: float = 0.0
    processing_method: str = ""
    model_used: str = ""
    processing_time_ms: int = 0
    
    document_type: str = ""
    status: str = "pending"
    extracted_entities: Dict = field(default_factory=dict)
    processing_metadata: Dict = field(default_factory=dict)
    
    namespace: str = "default"
    tenant_id: str = "default"
    ltm_key: str = ""


# =============================================================================
# GLOBAL CONFIG INSTANCE
# =============================================================================

vision_config = VisionStorageConfig()


def get_config() -> VisionStorageConfig:
    """Get global vision storage configuration"""
    return vision_config


def update_threshold(level: str, value: float):
    """Update confidence threshold dynamically"""
    global vision_config
    vision_config.confidence_thresholds[level] = value


def reset_to_defaults():
    """Reset configuration to default values"""
    global vision_config
    vision_config = VisionStorageConfig()


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def classify_document_type(text: str) -> tuple:
    """
    Classify document type based on content
    Returns: (document_type, confidence_boost)
    """
    text_lower = text.lower()
    scores = {}
    
    for doc_type, config in DOCUMENT_TYPES.items():
        score = 0
        keywords = config['keywords']
        
        for keyword in keywords:
            if keyword in text_lower:
                score += 1
        
        # Normalize score
        scores[doc_type] = score / len(keywords) if keywords else 0
    
    # Get best match
    if scores:
        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]
        
        if best_score > 0.3:  # Minimum threshold for classification
            boost = DOCUMENT_TYPES[best_type].get('confidence_boost', 0)
            return best_type, boost
    
    return 'unknown', 0.0


def calculate_content_quality(text: str) -> Dict[str, Any]:
    """
    Calculate content quality metrics
    """
    import re
    
    metrics = {
        'text_length': len(text),
        'word_count': len(text.split()),
        'line_count': len(text.split('\n')),
        'has_numbers': bool(re.search(r'\d', text)),
        'has_dates': bool(re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', text)),
        'has_amounts': bool(re.search(r'(Rp|\$|\d+\.\d{2})', text)),
        'has_emails': bool(re.search(r'[\w.-]+@[\w.-]+\.\w+', text)),
        'has_structure': bool(re.search(r'(:|=>|\|)', text))
    }
    
    # Quality score
    quality_score = sum([
        0.2 if metrics['has_numbers'] else 0,
        0.2 if metrics['has_dates'] else 0,
        0.2 if metrics['has_amounts'] else 0,
        0.2 if metrics['has_emails'] else 0,
        0.2 if metrics['has_structure'] else 0
    ])
    
    metrics['quality_score'] = quality_score
    
    return metrics


# =============================================================================
# EXPORT
# =============================================================================

__all__ = [
    'VisionStorageConfig',
    'ProcessingResult',
    'vision_config',
    'get_config',
    'update_threshold',
    'reset_to_defaults',
    'classify_document_type',
    'calculate_content_quality',
    'CONFIDENCE_THRESHOLDS',
    'STORAGE_POLICY',
    'RETENTION_POLICY',
    'PROCESSING_CONFIG',
    'DOCUMENT_TYPES',
    'DB_TABLE_CONFIG',
    'UNCERTAINTY_WORDS',
    'SPECIFICITY_INDICATORS',
]

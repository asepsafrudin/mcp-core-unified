"""
Test Suite untuk Vision Repository Module

Menguji operasi CRUD dan hybrid storage functionality.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

# Import modules to test
from core.vision_config import (
    VisionStorageConfig,
    ProcessingResult,
    get_config,
    classify_document_type,
    calculate_content_quality
)

from memory.vision_repository import (
    save_vision_result,
    get_vision_result_by_id,
    get_high_confidence_results,
    get_results_by_document_type,
    get_processing_stats,
    update_vision_status,
    check_duplicate,
    _row_to_dict
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_processing_result():
    """Create a sample ProcessingResult for testing"""
    return ProcessingResult(
        file_name="test_invoice.pdf",
        file_path="/tmp/test_invoice.pdf",
        file_hash="abc123def456",
        file_size_bytes=1024000,
        mime_type="application/pdf",
        extracted_text="INVOICE #001\nDate: 2024-01-15\nTotal: Rp 1.500.000",
        confidence_score=0.92,
        processing_method="hybrid",
        model_used="llava",
        processing_time_ms=2500,
        document_type="invoice",
        status="success",
        extracted_entities={
            "dates": ["2024-01-15"],
            "amounts": ["Rp 1.500.000"],
            "document_type": "invoice"
        },
        processing_metadata={"test": True},
        namespace="test",
        tenant_id="test_tenant"
    )


@pytest.fixture
def mock_db_pool():
    """Create mock database pool"""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    
    # Setup async context managers
    mock_pool.connection.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.connection.return_value.__aexit__ = AsyncMock(return_value=False)
    
    mock_conn.cursor.return_value.__aenter__ = AsyncMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__aexit__ = AsyncMock(return_value=False)
    
    return mock_pool, mock_conn, mock_cur


# =============================================================================
# CONFIGURATION TESTS
# =============================================================================

class TestVisionConfig:
    """Test untuk vision configuration"""
    
    def test_default_thresholds(self):
        """Test default confidence thresholds"""
        config = VisionStorageConfig()
        
        assert config.get_threshold('high') == 0.80
        assert config.get_threshold('medium') == 0.70
        assert config.get_threshold('low') == 0.50
    
    def test_storage_decision_high_confidence(self):
        """Test storage decision for high confidence"""
        config = VisionStorageConfig()
        
        decision = config.get_storage_decision(0.85)
        assert decision == 'sql+ltm'
        
        assert config.should_save_to_sql(0.85) is True
        assert config.should_save_to_ltm(0.85) is True
    
    def test_storage_decision_medium_confidence(self):
        """Test storage decision for medium confidence"""
        config = VisionStorageConfig()
        
        decision = config.get_storage_decision(0.75)
        assert decision == 'ltm_only'
        
        assert config.should_save_to_sql(0.75) is False
        assert config.should_save_to_ltm(0.75) is True
    
    def test_storage_decision_low_confidence(self):
        """Test storage decision for low confidence"""
        config = VisionStorageConfig()
        
        decision = config.get_storage_decision(0.60)
        assert decision == 'reject'
        
        assert config.should_save_to_sql(0.60) is False
        assert config.should_save_to_ltm(0.60) is False


# =============================================================================
# DOCUMENT CLASSIFICATION TESTS
# =============================================================================

class TestDocumentClassification:
    """Test untuk document type classification"""
    
    def test_classify_invoice(self):
        """Test classification of invoice text"""
        text = "INVOICE #123\nTotal Amount: Rp 1.500.000\nPayment Due: 2024-01-15"
        
        doc_type, boost = classify_document_type(text)
        
        assert doc_type == 'invoice'
        assert boost > 0
    
    def test_classify_receipt(self):
        """Test classification of receipt text"""
        text = "RECEIPT\nPaid: Rp 50.000\nThank you for your purchase!"
        
        doc_type, boost = classify_document_type(text)
        
        assert doc_type == 'receipt'
    
    def test_classify_form(self):
        """Test classification of form text"""
        text = "APPLICATION FORM\nName: John Doe\nAddress: Jakarta"
        
        doc_type, boost = classify_document_type(text)
        
        assert doc_type == 'form'
    
    def test_classify_unknown(self):
        """Test classification of unknown text"""
        text = "Random text without any specific keywords"
        
        doc_type, boost = classify_document_type(text)
        
        assert doc_type == 'unknown'
        assert boost == 0.0


# =============================================================================
# CONTENT QUALITY TESTS
# =============================================================================

class TestContentQuality:
    """Test untuk content quality calculation"""
    
    def test_quality_metrics(self):
        """Test quality metrics calculation"""
        text = """
        Invoice Date: 2024-01-15
        Amount: Rp 1.500.000
        Contact: test@email.com
        """
        
        metrics = calculate_content_quality(text)
        
        assert metrics['text_length'] == len(text)
        assert metrics['has_numbers'] is True
        assert metrics['has_dates'] is True
        assert metrics['has_amounts'] is True
        assert metrics['has_emails'] is True
        assert metrics['quality_score'] > 0.5
    
    def test_quality_low_content(self):
        """Test quality for low-content text"""
        text = "Short text"
        
        metrics = calculate_content_quality(text)
        
        assert metrics['has_numbers'] is False
        assert metrics['has_dates'] is False
        assert metrics['has_emails'] is False
        assert metrics['quality_score'] == 0.0


# =============================================================================
# REPOSITORY TESTS (with mocking)
# =============================================================================

@pytest.mark.asyncio
class TestVisionRepository:
    """Test untuk vision repository operations"""
    
    async def test_save_high_confidence_result(self, sample_processing_result, mock_db_pool):
        """Test saving high confidence result to SQL"""
        mock_pool, mock_conn, mock_cur = mock_db_pool
        
        # Setup mock return values
        mock_cur.fetchone.return_value = ('test-uuid-123',)
        
        # Patch get_pool to return mock
        with patch('memory.vision_repository.get_pool', return_value=mock_pool):
            result = await save_vision_result(sample_processing_result)
        
        assert result['success'] is True
        assert result['saved_to_sql'] is True
        assert result['operation'] == 'insert'
    
    async def test_save_low_confidence_result(self, mock_db_pool):
        """Test that low confidence results are rejected"""
        mock_pool, mock_conn, mock_cur = mock_db_pool
        
        low_confidence_result = ProcessingResult(
            file_name="test.pdf",
            file_path="/tmp/test.pdf",
            confidence_score=0.50,  # Below threshold
            namespace="test"
        )
        
        with patch('memory.vision_repository.get_pool', return_value=mock_pool):
            result = await save_vision_result(low_confidence_result)
        
        assert result['success'] is False
        assert result['saved_to_sql'] is False
        assert result['reason'] == 'confidence_below_threshold'
    
    async def test_get_high_confidence_results(self, mock_db_pool):
        """Test retrieving high confidence results"""
        mock_pool, mock_conn, mock_cur = mock_db_pool
        
        # Setup mock data
        mock_rows = [
            ('uuid-1', 'test1.pdf', 0.90, 'invoice'),
            ('uuid-2', 'test2.pdf', 0.85, 'receipt')
        ]
        mock_cur.fetchall.return_value = mock_rows
        
        # Mock description
        mock_cur.description = [
            MagicMock(name='id'),
            MagicMock(name='file_name'),
            MagicMock(name='confidence_score'),
            MagicMock(name='document_type')
        ]
        
        with patch('memory.vision_repository.get_pool', return_value=mock_pool):
            results = await get_high_confidence_results(min_confidence=0.8)
        
        assert len(results) == 2
        assert all(r['confidence_score'] >= 0.8 for r in results)
    
    async def test_update_vision_status(self, mock_db_pool):
        """Test updating vision result status"""
        mock_pool, mock_conn, mock_cur = mock_db_pool
        
        mock_cur.fetchone.return_value = ('uuid-123',)
        
        with patch('memory.vision_repository.get_pool', return_value=mock_pool):
            result = await update_vision_status('uuid-123', 'verified', 'admin')
        
        assert result['success'] is True
        assert result['new_status'] == 'verified'
    
    async def test_check_duplicate_found(self, mock_db_pool):
        """Test duplicate detection when file exists"""
        mock_pool, mock_conn, mock_cur = mock_db_pool
        
        mock_cur.fetchone.return_value = ('uuid-123', 0.90, datetime.now())
        
        with patch('memory.vision_repository.get_pool', return_value=mock_pool):
            result = await check_duplicate('hash123', 'test')
        
        assert result['exists'] is True
        assert result['confidence_score'] == 0.90
    
    async def test_check_duplicate_not_found(self, mock_db_pool):
        """Test duplicate detection when file doesn't exist"""
        mock_pool, mock_conn, mock_cur = mock_db_pool
        
        mock_cur.fetchone.return_value = None
        
        with patch('memory.vision_repository.get_pool', return_value=mock_pool):
            result = await check_duplicate('hash123', 'test')
        
        assert result['exists'] is False


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

@pytest.mark.asyncio
class TestVisionIntegration:
    """Integration tests untuk vision pipeline dengan hybrid storage"""
    
    async def test_end_to_end_high_confidence(self, sample_processing_result):
        """Test end-to-end flow for high confidence result"""
        # This would be a full integration test with real database
        # For now, just verify the flow logic
        
        config = get_config()
        confidence = sample_processing_result.confidence_score
        
        # Verify confidence is high enough
        assert confidence >= config.get_threshold('high')
        
        # Verify storage decision
        decision = config.get_storage_decision(confidence)
        assert decision == 'sql+ltm'
    
    async def test_end_to_end_medium_confidence(self):
        """Test end-to-end flow for medium confidence result"""
        medium_result = ProcessingResult(
            file_name="test.pdf",
            file_path="/tmp/test.pdf",
            confidence_score=0.75,  # Medium confidence
            namespace="test"
        )
        
        config = get_config()
        decision = config.get_storage_decision(medium_result.confidence_score)
        
        assert decision == 'ltm_only'
    
    async def test_end_to_end_low_confidence(self):
        """Test end-to-end flow for low confidence result"""
        low_result = ProcessingResult(
            file_name="test.pdf",
            file_path="/tmp/test.pdf",
            confidence_score=0.50,  # Low confidence
            namespace="test"
        )
        
        config = get_config()
        decision = config.get_storage_decision(low_result.confidence_score)
        
        assert decision == 'reject'


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================

@pytest.mark.asyncio
class TestPerformance:
    """Performance tests untuk repository operations"""
    
    async def test_batch_save_performance(self, mock_db_pool):
        """Test performance of batch save operations"""
        mock_pool, mock_conn, mock_cur = mock_db_pool
        
        mock_cur.fetchone.return_value = ('uuid-test',)
        
        # Create multiple results
        results = []
        for i in range(10):
            result = ProcessingResult(
                file_name=f"test_{i}.pdf",
                file_path=f"/tmp/test_{i}.pdf",
                confidence_score=0.85 + (i * 0.01),
                namespace="test"
            )
            results.append(result)
        
        # Measure time (just a basic check)
        start = asyncio.get_event_loop().time()
        
        with patch('memory.vision_repository.get_pool', return_value=mock_pool):
            for result in results:
                await save_vision_result(result)
        
        elapsed = asyncio.get_event_loop().time() - start
        
        # Should complete within reasonable time (adjust as needed)
        assert elapsed < 10.0  # 10 seconds max


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

@pytest.mark.asyncio
class TestErrorHandling:
    """Test error handling in repository operations"""
    
    async def test_database_connection_error(self, sample_processing_result):
        """Test handling of database connection errors"""
        
        with patch('memory.vision_repository.get_pool', side_effect=Exception("DB Connection Failed")):
            result = await save_vision_result(sample_processing_result)
        
        assert result['success'] is False
        assert 'error' in result
    
    async def test_invalid_confidence_value(self):
        """Test handling of invalid confidence values"""
        invalid_result = ProcessingResult(
            file_name="test.pdf",
            file_path="/tmp/test.pdf",
            confidence_score=-0.5,  # Invalid negative confidence
            namespace="test"
        )
        
        # Should still process but may be rejected
        config = get_config()
        decision = config.get_storage_decision(invalid_result.confidence_score)
        
        assert decision == 'reject'


# =============================================================================
# EXPORT
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

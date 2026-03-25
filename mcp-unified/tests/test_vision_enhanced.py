"""
Test Suite untuk Enhanced Vision Tools

Run dengan: python -m pytest tests/test_vision_enhanced.py -v
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from PIL import Image
import json

# Import tools yang akan di-test
from execution.tools.vision_enhanced import (
    VisionResult,
    ComparisonResult,
    StructuredExtraction,
    VisionCache,
    _calculate_confidence,
    analyze_image_enhanced,
    analyze_batch,
    compare_images,
    extract_structured_data,
    enhance_image,
    clear_vision_cache,
    get_vision_stats,
    ENHANCED_MODELS,
    BATCH_SIZE,
    CONFIDENCE_THRESHOLD,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_image(tmp_path):
    """Create a sample image untuk testing"""
    img_path = tmp_path / "test_image.jpg"
    img = Image.new('RGB', (100, 100), color='red')
    img.save(img_path)
    return str(img_path)


@pytest.fixture
def sample_images(tmp_path):
    """Create multiple sample images untuk testing"""
    paths = []
    colors = ['red', 'blue', 'green', 'yellow']
    
    for i, color in enumerate(colors):
        img_path = tmp_path / f"test_image_{i}.jpg"
        img = Image.new('RGB', (100, 100), color=color)
        img.save(img_path)
        paths.append(str(img_path))
    
    return paths


@pytest.fixture
def mock_vision_response():
    """Mock response dari Ollama vision model"""
    return {
        "response": "This is a test image showing a red square. "
                   "It appears to be a solid color with dimensions 100x100 pixels."
    }


# =============================================================================
# TEST: Data Classes
# =============================================================================

class TestDataClasses:
    """Test untuk VisionResult, ComparisonResult, StructuredExtraction"""
    
    def test_vision_result_creation(self):
        """Test VisionResult dataclass"""
        result = VisionResult(
            success=True,
            content="Test content",
            confidence=0.85,
            model="llava",
            processing_time=2.5,
            image_path="/tmp/test.jpg",
            metadata={"cached": False}
        )
        
        assert result.success is True
        assert result.confidence == 0.85
        assert result.error is None
    
    def test_vision_result_with_error(self):
        """Test VisionResult dengan error"""
        result = VisionResult(
            success=False,
            content="",
            confidence=0.0,
            model="llava",
            processing_time=0.0,
            image_path="/tmp/test.jpg",
            metadata={},
            error="Path outside allowed directories"
        )
        
        assert result.success is False
        assert result.error == "Path outside allowed directories"
    
    def test_comparison_result(self):
        """Test ComparisonResult dataclass"""
        result = ComparisonResult(
            similarities=["Images are similar"],
            differences=["Color differs"],
            confidence=0.75,
            recommendation=None
        )
        
        assert len(result.similarities) == 1
        assert len(result.differences) == 1
        assert result.confidence == 0.75
    
    def test_structured_extraction(self):
        """Test StructuredExtraction dataclass"""
        result = StructuredExtraction(
            success=True,
            data={"field1": "value1", "field2": "value2"},
            raw_text='{"field1": "value1"}',
            confidence=0.9,
            missing_fields=[]
        )
        
        assert result.success is True
        assert "field1" in result.data
        assert len(result.missing_fields) == 0


# =============================================================================
# TEST: Confidence Calculation
# =============================================================================

class TestConfidenceCalculation:
    """Test untuk confidence scoring algorithm"""
    
    def test_confidence_high_quality_response(self):
        """Test confidence untuk response dengan detail tinggi"""
        text = ("The image shows a large red building with 5 windows on the left side "
                "and 3 doors at the center. The roof is blue and there is a green garden "
                "in the front with approximately 10 trees.")
        
        confidence = _calculate_confidence(text, "Describe this image")
        
        # Should have high confidence due to length, numbers, colors, positions
        assert confidence > 0.6
    
    def test_confidence_uncertainty_words(self):
        """Test confidence penalty untuk uncertainty words"""
        text = "Maybe this is a building, possibly red, but I'm not sure."
        
        confidence = _calculate_confidence(text, "Describe this image")
        
        # Should have lower confidence due to uncertainty words
        assert confidence < 0.5
    
    def test_confidence_short_response(self):
        """Test confidence untuk response pendek"""
        text = "Red square."
        
        confidence = _calculate_confidence(text, "Describe this image")
        
        # Should have base confidence (0.5) + minimal bonus
        assert 0.4 < confidence < 0.7
    
    def test_confidence_bounds(self):
        """Test confidence stays within 0-1 bounds"""
        # Very long text dengan banyak uncertainty
        text = "maybe " * 100 + "possibly " * 100
        confidence = _calculate_confidence(text, "Describe")
        
        assert 0.0 <= confidence <= 1.0


# =============================================================================
# TEST: Vision Cache
# =============================================================================

class TestVisionCache:
    """Test untuk VisionCache"""
    
    def test_cache_set_and_get(self):
        """Test cache set dan get operations"""
        cache = VisionCache(ttl_seconds=3600)
        
        # Set cache
        cache.set("/tmp/image.jpg", "Describe this", "llava", {
            "description": "A test image",
            "confidence": 0.85
        })
        
        # Get cache
        result = cache.get("/tmp/image.jpg", "Describe this", "llava")
        
        assert result is not None
        assert result["description"] == "A test image"
        assert result["confidence"] == 0.85
    
    def test_cache_miss_different_params(self):
        """Test cache miss dengan parameter berbeda"""
        cache = VisionCache(ttl_seconds=3600)
        
        cache.set("/tmp/image.jpg", "Describe this", "llava", {"desc": "test"})
        
        # Different path
        assert cache.get("/tmp/other.jpg", "Describe this", "llava") is None
        # Different prompt
        assert cache.get("/tmp/image.jpg", "Other prompt", "llava") is None
        # Different model
        assert cache.get("/tmp/image.jpg", "Describe this", "moondream") is None
    
    def test_cache_expiration(self):
        """Test cache expiration"""
        cache = VisionCache(ttl_seconds=0.01)  # Very short TTL
        
        cache.set("/tmp/image.jpg", "Describe", "llava", {"desc": "test"})
        
        # Should return None after TTL expires
        import time
        time.sleep(0.02)
        
        result = cache.get("/tmp/image.jpg", "Describe", "llava")
        assert result is None
    
    def test_cache_clear(self):
        """Test cache clear"""
        cache = VisionCache(ttl_seconds=3600)
        
        cache.set("/tmp/1.jpg", "Describe", "llava", {"desc": "test1"})
        cache.set("/tmp/2.jpg", "Describe", "llava", {"desc": "test2"})
        
        cache.clear()
        
        assert cache.get("/tmp/1.jpg", "Describe", "llava") is None
        assert cache.get("/tmp/2.jpg", "Describe", "llava") is None
        assert len(cache._cache) == 0


# =============================================================================
# TEST: Image Enhancement
# =============================================================================

class TestImageEnhancement:
    """Test untuk enhance_image function"""
    
    @pytest.mark.asyncio
    async def test_enhance_image_success(self, sample_image):
        """Test successful image enhancement"""
        result = await enhance_image(
            image_path=sample_image,
            enhancements=["contrast", "sharpness"]
        )
        
        assert result["success"] is True
        assert "enhanced_path" in result
        assert "contrast" in result["enhancements_applied"]
        assert "sharpness" in result["enhancements_applied"]
        
        # Cleanup
        if Path(result["enhanced_path"]).exists():
            Path(result["enhanced_path"]).unlink()
    
    @pytest.mark.asyncio
    async def test_enhance_image_with_output_path(self, sample_image, tmp_path):
        """Test enhancement dengan specified output path"""
        output_path = str(tmp_path / "enhanced_output.jpg")
        
        result = await enhance_image(
            image_path=sample_image,
            enhancements=["contrast"],
            output_path=output_path
        )
        
        assert result["success"] is True
        assert result["enhanced_path"] == output_path
        assert Path(output_path).exists()
    
    @pytest.mark.asyncio
    async def test_enhance_image_invalid_path(self):
        """Test enhancement dengan invalid path"""
        result = await enhance_image(
            image_path="/nonexistent/path.jpg",
            enhancements=["contrast"]
        )
        
        assert result["success"] is False
        assert "error" in result


# =============================================================================
# TEST: Vision Stats
# =============================================================================

class TestVisionStats:
    """Test untuk get_vision_stats function"""
    
    @pytest.mark.asyncio
    async def test_get_vision_stats(self):
        """Test get vision stats"""
        stats = await get_vision_stats()
        
        assert "cache_entries" in stats
        assert "cache_ttl_seconds" in stats
        assert "batch_size" in stats
        assert "confidence_threshold" in stats
        assert "available_models" in stats
        assert "default_model" in stats
        
        # Check model profiles exist
        assert "fast" in stats["available_models"]
        assert "balanced" in stats["available_models"]
        assert "quality" in stats["available_models"]


# =============================================================================
# TEST: Configuration Constants
# =============================================================================

class TestConfiguration:
    """Test untuk configuration constants"""
    
    def test_enhanced_models_structure(self):
        """Test ENHANCED_MODELS dictionary"""
        assert "fast" in ENHANCED_MODELS
        assert "balanced" in ENHANCED_MODELS
        assert "quality" in ENHANCED_MODELS
        assert "ocr" in ENHANCED_MODELS
        
        # All should have string values
        for key, value in ENHANCED_MODELS.items():
            assert isinstance(value, str)
            assert len(value) > 0
    
    def test_batch_size(self):
        """Test BATCH_SIZE constant"""
        assert isinstance(BATCH_SIZE, int)
        assert BATCH_SIZE > 0
        assert BATCH_SIZE <= 10  # Reasonable limit
    
    def test_confidence_threshold(self):
        """Test CONFIDENCE_THRESHOLD constant"""
        assert isinstance(CONFIDENCE_THRESHOLD, float)
        assert 0.0 <= CONFIDENCE_THRESHOLD <= 1.0


# =============================================================================
# TEST: Async Functions (with mocking)
# =============================================================================

class TestAsyncFunctions:
    """Test untuk async functions dengan mocking"""
    
    @pytest.mark.asyncio
    @patch('execution.tools.vision_enhanced._call_ollama_vision')
    @patch('execution.tools.vision_enhanced.is_safe_path')
    @patch('execution.tools.vision_enhanced._image_to_base64')
    async def test_analyze_image_enhanced_success(
        self, mock_base64, mock_safe, mock_ollama, sample_image
    ):
        """Test successful enhanced image analysis"""
        mock_safe.return_value = True
        mock_base64.return_value = "base64encodedstring"
        mock_ollama.return_value = "This is a detailed description of the image."
        
        result = await analyze_image_enhanced(
            image_path=sample_image,
            prompt="Describe this image",
            use_cache=False
        )
        
        assert result.success is True
        assert result.content == "This is a detailed description of the image."
        assert result.confidence > 0
        assert result.processing_time >= 0
    
    @pytest.mark.asyncio
    @patch('execution.tools.vision_enhanced.is_safe_path')
    async def test_analyze_image_enhanced_unsafe_path(self, mock_safe, sample_image):
        """Test analysis dengan unsafe path"""
        mock_safe.return_value = False
        
        result = await analyze_image_enhanced(
            image_path="/etc/passwd",
            prompt="Describe this"
        )
        
        assert result.success is False
        assert "Path outside allowed directories" in result.error
    
    @pytest.mark.asyncio
    @patch('execution.tools.vision_enhanced.analyze_image_enhanced')
    async def test_analyze_batch(self, mock_analyze, sample_images):
        """Test batch analysis"""
        mock_analyze.return_value = VisionResult(
            success=True,
            content="Test description",
            confidence=0.85,
            model="llava",
            processing_time=1.0,
            image_path="/tmp/test.jpg",
            metadata={}
        )
        
        results = await analyze_batch(
            image_paths=sample_images[:2],
            prompt="Describe",
            max_parallel=2
        )
        
        assert len(results) == 2
        assert all(r.success for r in results)
    
    @pytest.mark.asyncio
    @patch('execution.tools.vision_enhanced.analyze_batch')
    async def test_compare_images(self, mock_batch, sample_images):
        """Test image comparison"""
        mock_batch.return_value = [
            VisionResult(
                success=True,
                content="Red square image with dimensions 100x100",
                confidence=0.9,
                model="llava",
                processing_time=1.0,
                image_path=sample_images[0],
                metadata={}
            ),
            VisionResult(
                success=True,
                content="Blue square image with dimensions 100x100",
                confidence=0.9,
                model="llava",
                processing_time=1.0,
                image_path=sample_images[1],
                metadata={}
            )
        ]
        
        result = await compare_images(
            image_paths=[sample_images[0], sample_images[1]]
        )
        
        assert isinstance(result, ComparisonResult)
        assert result.confidence > 0
        # Should detect difference in color
        assert len(result.differences) > 0 or len(result.similarities) > 0
    
    @pytest.mark.asyncio
    @patch('execution.tools.vision_enhanced.analyze_image_enhanced')
    async def test_extract_structured_data_success(self, mock_analyze, sample_image):
        """Test successful structured data extraction"""
        mock_analyze.return_value = VisionResult(
            success=True,
            content='```json\n{"name": "John", "age": 30}\n```',
            confidence=0.9,
            model="llava",
            processing_time=1.0,
            image_path=sample_image,
            metadata={}
        )
        
        schema = {
            "name": "Person's name",
            "age": "Person's age"
        }
        
        result = await extract_structured_data(
            image_path=sample_image,
            schema=schema
        )
        
        assert result.success is True
        assert "name" in result.data
        assert result.confidence > 0
    
    @pytest.mark.asyncio
    @patch('execution.tools.vision_enhanced.analyze_image_enhanced')
    async def test_extract_structured_data_invalid_json(self, mock_analyze, sample_image):
        """Test structured extraction dengan invalid JSON response"""
        mock_analyze.return_value = VisionResult(
            success=True,
            content="This is not valid JSON",
            confidence=0.5,
            model="llava",
            processing_time=1.0,
            image_path=sample_image,
            metadata={}
        )
        
        schema = {"field1": "Description"}
        
        result = await extract_structured_data(
            image_path=sample_image,
            schema=schema
        )
        
        assert result.success is False
        assert len(result.missing_fields) > 0


# =============================================================================
# TEST: Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests untuk vision pipeline"""
    
    @pytest.mark.asyncio
    async def test_full_pipeline_cached_result(self, sample_image):
        """Test full pipeline dengan caching"""
        # Clear cache
        clear_vision_cache()
        
        # First call should not be cached
        with patch('execution.tools.vision_enhanced.is_safe_path', return_value=True), \
             patch('execution.tools.vision_enhanced._image_to_base64', return_value="base64"), \
             patch('execution.tools.vision_enhanced._call_ollama_vision', return_value="Description"):
            
            result1 = await analyze_image_enhanced(
                image_path=sample_image,
                prompt="Test",
                use_cache=True
            )
            
            assert result1.metadata.get("cached") is False
        
        # Second call should be cached
        result2 = await analyze_image_enhanced(
            image_path=sample_image,
            prompt="Test",
            use_cache=True
        )
        
        assert result2.metadata.get("cached") is True
        assert result2.processing_time == 0


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

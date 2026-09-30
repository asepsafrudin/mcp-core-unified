"""Unit tests for shared.embedding_client"""

import pytest
from unittest.mock import patch, MagicMock

from shared.embedding_client import get_embedding, OLLAMA_ENDPOINT


class TestEmbeddingClient:
    """Test cases for embedding_client.py"""

    def test_get_embedding_success(self):
        """Test successful embedding retrieval"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
        mock_response.raise_for_status.return_value = None

        with patch("shared.embedding_client.requests.post", return_value=mock_response) as mock_post:
            result = get_embedding("Hello world")
            
            assert result == [0.1, 0.2, 0.3]
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[1]["json"]["prompt"] == "Hello world"
            assert call_args[1]["json"]["model"] == "all-minilm"

    def test_get_embedding_custom_model(self):
        """Test embedding with custom model"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": [0.4, 0.5, 0.6]}
        mock_response.raise_for_status.return_value = None

        with patch("shared.embedding_client.requests.post", return_value=mock_response) as mock_post:
            result = get_embedding("Test text", model="custom-model")
            
            assert result == [0.4, 0.5, 0.6]
            call_args = mock_post.call_args
            assert call_args[1]["json"]["model"] == "custom-model"

    def test_get_embedding_http_error(self):
        """Test handling of HTTP errors"""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("HTTP 500")

        with patch("shared.embedding_client.requests.post", return_value=mock_response):
            with pytest.raises(Exception, match="HTTP 500"):
                get_embedding("Test")

    def test_get_embedding_missing_key(self):
        """Test handling of missing embedding key in response"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [0.1, 0.2]}
        mock_response.raise_for_status.return_value = None

        with patch("shared.embedding_client.requests.post", return_value=mock_response):
            result = get_embedding("Test")
            assert result == []  # Should return empty list when key missing

    def test_ollama_endpoint_default(self):
        """Test default Ollama endpoint"""
        assert OLLAMA_ENDPOINT == "http://localhost:11434"
"""Unit tests for shared.cache"""

from unittest.mock import patch, MagicMock

from shared.cache import get, set, REDIS_URL


class TestCache:
    """Test cases for cache.py"""

    def test_get_key_exists(self):
        """Test get returns value when key exists"""
        mock_redis = MagicMock()
        mock_redis.get.return_value = b"test_value"

        with patch("shared.cache._redis_client", mock_redis):
            result = get("test_key")
            assert result == b"test_value"
            mock_redis.get.assert_called_once_with("test_key")

    def test_get_key_not_exists(self):
        """Test get returns None when key doesn't exist"""
        mock_redis = MagicMock()
        mock_redis.get.return_value = None

        with patch("shared.cache._redis_client", mock_redis):
            result = get("nonexistent_key")
            assert result is None

    def test_set_without_ttl(self):
        """Test set without TTL"""
        mock_redis = MagicMock()
        mock_redis.set.return_value = True

        with patch("shared.cache._redis_client", mock_redis):
            result = set("key", "value")
            assert result is True
            mock_redis.set.assert_called_once_with(name="key", value="value", ex=None)

    def test_set_with_ttl(self):
        """Test set with TTL"""
        mock_redis = MagicMock()
        mock_redis.set.return_value = True

        with patch("shared.cache._redis_client", mock_redis):
            result = set("key", "value", ttl=3600)
            assert result is True
            mock_redis.set.assert_called_once_with(name="key", value="value", ex=3600)

    def test_set_failure(self):
        """Test set returns False on failure"""
        mock_redis = MagicMock()
        mock_redis.set.return_value = False

        with patch("shared.cache._redis_client", mock_redis):
            result = set("key", "value")
            assert result is False

    def test_redis_url_default(self):
        """Test default Redis URL"""
        assert REDIS_URL == "redis://localhost:6379/0"
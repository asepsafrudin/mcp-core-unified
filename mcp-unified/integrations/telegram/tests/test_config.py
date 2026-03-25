"""
Tests untuk config module.
"""

import os
import pytest
from datetime import datetime
from pathlib import Path

from ..config import TelegramConfig, AIConfig, TelegramMode, AIProvider


class TestTelegramConfig:
    """Test cases untuk TelegramConfig."""
    
    def test_config_from_env_success(self, monkeypatch):
        """Test loading config dari environment variables."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
        monkeypatch.setenv("TELEGRAM_MODE", "polling")
        monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
        
        config = TelegramConfig.from_env()
        
        assert config.bot_token == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        assert config.mode == TelegramMode.POLLING
        assert config.ai.groq_api_key == "test-groq-key"
    
    def test_config_missing_token(self, monkeypatch):
        """Test error ketika token missing."""
        # Skip test jika ada .env file (akan auto-load token)
        env_file = Path(__file__).parent.parent / ".env"
        if env_file.exists():
            pytest.skip("Skipped: .env file exists with token")
        
        # Clear all env vars yang terkait
        for key in list(os.environ.keys()):
            if 'TELEGRAM' in key or 'GROQ' in key or 'GEMINI' in key:
                monkeypatch.delenv(key, raising=False)
        
        with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
            TelegramConfig.from_env()
    
    def test_config_invalid_token(self):
        """Test error ketika token invalid."""
        with pytest.raises(ValueError, match="Invalid bot token"):
            TelegramConfig(bot_token="invalid-token")
    
    def test_is_user_allowed_empty_whitelist(self):
        """Test user allowed ketika whitelist kosong."""
        from ..config.settings import SecurityConfig
        
        config = TelegramConfig(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            security=SecurityConfig(allowed_users=[])
        )
        
        assert config.is_user_allowed(123456) is True
    
    def test_is_user_allowed_with_whitelist(self):
        """Test user allowed dengan whitelist."""
        from ..config.settings import SecurityConfig
        
        config = TelegramConfig(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            security=SecurityConfig(allowed_users=[123456, 789012])
        )
        
        assert config.is_user_allowed(123456) is True
        assert config.is_user_allowed(999999) is False


class TestAIConfig:
    """Test cases untuk AIConfig."""
    
    def test_default_provider(self):
        """Test default AI provider."""
        config = AIConfig()
        assert config.provider == AIProvider.GROQ
    
    def test_custom_provider(self):
        """Test custom AI provider."""
        config = AIConfig(provider=AIProvider.GEMINI)
        assert config.provider == AIProvider.GEMINI

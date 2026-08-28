"""Tests for core configuration and validators."""

import pytest
from pydantic import ValidationError

from core.config import Settings


class TestRedisUrlValidator:
    """Tests for Settings.REDIS_URL validation."""

    def test_valid_localhost_without_password(self):
        settings = Settings(REDIS_URL="redis://localhost:6379/0")
        assert settings.REDIS_URL == "redis://localhost:6379/0"

    def test_valid_with_password(self):
        settings = Settings(REDIS_URL="redis://:secret@localhost:6379/0")
        assert settings.REDIS_URL == "redis://:secret@localhost:6379/0"

    def test_valid_rediss(self):
        settings = Settings(REDIS_URL="rediss://localhost:6380/0")
        assert settings.REDIS_URL == "rediss://localhost:6380/0"

    def test_invalid_scheme(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(REDIS_URL="http://localhost:6379/0")
        assert "redis://" in str(exc_info.value)
        assert "rediss://" in str(exc_info.value)

    def test_invalid_port_too_high(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(REDIS_URL="redis://localhost:70000/0")
        assert "port" in str(exc_info.value).lower()

    def test_invalid_port_zero(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(REDIS_URL="redis://localhost:0/0")
        assert "port" in str(exc_info.value).lower()

    def test_empty_url(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(REDIS_URL="")
        assert "cannot be empty" in str(exc_info.value).lower()

    def test_missing_host(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(REDIS_URL="redis:///0")
        assert "host" in str(exc_info.value).lower()

    def test_non_localhost_without_password_warns(self, caplog):
        import logging
        caplog.set_level(logging.WARNING)
        settings = Settings(REDIS_URL="redis://redis.example.com:6379/0")
        assert settings.REDIS_URL == "redis://redis.example.com:6379/0"
        assert any(
            "redis_url_security_warning" in record.message
            for record in caplog.records
        )

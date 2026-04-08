"""
Unit tests untuk OpenHands integration — config dan schemas.

Menutup subtask 034-H: Unit test schemas & config.
"""

import sys
from pathlib import Path

# Add mcp-unified ke sys.path
MCP_UNIFIED_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MCP_UNIFIED_ROOT))

import pytest
from plugins.openhands.config import OpenHandsConfig
from plugins.openhands.schemas import (
    CodingTaskRequest,
    TaskResult,
    TaskStatus,
    TaskStatusResponse,
    ActiveTaskInfo,
    ListActiveTasksResponse,
)


class TestOpenHandsConfig:
    """Test untuk OpenHandsConfig class."""

    def test_default_values(self, monkeypatch):
        """Test bahwa default values sesuai expected."""
        # Clear env vars agar default digunakan
        for key in [
            "OPENHANDS_LLM_MODEL", "LLM_API_KEY", "LLM_API_BASE",
            "OPENHANDS_WORKSPACE", "OPENHANDS_TIMEOUT", "OPENHANDS_MAX_AGENTS",
            "OPENHANDS_REDIS_PREFIX", "OPENHANDS_REDIS_URL", "REDIS_URL",
            "OPENHANDS_USE_SANDBOX", "OPENHANDS_SANDBOX_IMAGE", "OPENHANDS_DEBUG",
        ]:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

        config = OpenHandsConfig()
        assert config.llm_model == "anthropic/claude-sonnet-4-5-20250929"
        assert config.llm_api_key == ""
        assert config.workspace_base == "/tmp/openhands_workspaces"
        assert config.task_timeout_seconds == 1800
        assert config.max_concurrent_agents == 3
        assert config.redis_prefix == "openhands:task:"
        assert config.use_sandbox is True
        assert config.sandbox_image == "python:3.12-slim"
        assert config.debug_logging is False

    def test_env_override(self, monkeypatch):
        """Test bahwa env vars mengoverride default."""
        import importlib
        from plugins.openhands import config as config_module
        # Set env vars
        monkeypatch.setenv("OPENHANDS_LLM_MODEL", "openai/gpt-4o")
        monkeypatch.setenv("LLM_API_KEY", "test-key")
        monkeypatch.setenv("OPENHANDS_WORKSPACE", "/custom/workspace")
        monkeypatch.setenv("OPENHANDS_TIMEOUT", "3600")
        monkeypatch.setenv("OPENHANDS_MAX_AGENTS", "5")

        # Reload module agar env vars baru dibaca
        importlib.reload(config_module)

        assert config_module.config.llm_model == "openai/gpt-4o"
        assert config_module.config.llm_api_key == "test-key"
        assert config_module.config.workspace_base == "/custom/workspace"
        assert config_module.config.task_timeout_seconds == 3600
        assert config_module.config.max_concurrent_agents == 5

        # Restore singleton untuk test berikutnya (opsional)
        monkeypatch.delenv("OPENHANDS_LLM_MODEL")
        monkeypatch.delenv("LLM_API_KEY")
        monkeypatch.delenv("OPENHANDS_WORKSPACE")
        monkeypatch.delenv("OPENHANDS_TIMEOUT")
        monkeypatch.delenv("OPENHANDS_MAX_AGENTS")
        importlib.reload(config_module)

    def test_validate_empty_model(self):
        """Test validasi error jika llm_model kosong."""
        config = OpenHandsConfig()
        # Set llm_model kosong
        config.llm_model = ""
        config.llm_api_key = ""
        errors = config.validate()
        assert "OPENHANDS_LLM_MODEL must be set" in errors

    def test_validate_missing_api_key(self):
        """Test validasi error jika api_key dan api_base kosong."""
        config = OpenHandsConfig()
        config.llm_model = "test/model"
        config.llm_api_key = ""
        config.llm_api_base = None
        errors = config.validate()
        assert "LLM_API_KEY or LLM_API_BASE must be set" in errors

    def test_validate_invalid_max_agents(self):
        """Test validasi error jika max_concurrent_agents < 1."""
        config = OpenHandsConfig()
        config.llm_model = "test/model"
        config.llm_api_key = "key"
        config.max_concurrent_agents = 0
        errors = config.validate()
        assert "OPENHANDS_MAX_AGENTS must be >= 1" in errors

    def test_validate_invalid_timeout(self):
        """Test validasi error jika timeout < 60 detik."""
        config = OpenHandsConfig()
        config.llm_model = "test/model"
        config.llm_api_key = "key"
        config.task_timeout_seconds = 30
        errors = config.validate()
        assert "OPENHANDS_TIMEOUT must be >= 60 seconds" in errors

    def test_validate_pass(self):
        """Test validasi pass ketika semua values valid."""
        config = OpenHandsConfig()
        config.llm_model = "test/model"
        config.llm_api_key = "key"
        config.max_concurrent_agents = 3
        config.task_timeout_seconds = 600
        errors = config.validate()
        assert len(errors) == 0


class TestCodingTaskRequest:
    """Test untuk CodingTaskRequest model."""

    def test_minimal_request(self):
        """Test request dengan minimal fields."""
        req = CodingTaskRequest(
            task_description="Buatkan CRUD API untuk tabel user",
            expected_output="File: models.py, routers/user.py, schemas.py",
        )
        assert req.task_description == "Buatkan CRUD API untuk tabel user"
        assert req.expected_output == "File: models.py, routers/user.py, schemas.py"
        assert req.context == ""
        assert req.requested_by == "mcp_orchestrator"
        assert req.priority == "medium"
        assert req.timeout_minutes == 30
        assert req.provided_files == []

    def test_full_request(self):
        """Test request dengan semua fields."""
        req = CodingTaskRequest(
            task_description="Buatkan REST API",
            expected_output="Working API",
            context="Project FastAPI",
            requested_by="telegram_bot",
            priority="high",
            timeout_minutes=60,
            provided_files=["src/config.py", "src/models.py"],
        )
        assert req.priority == "high"
        assert req.requested_by == "telegram_bot"
        assert len(req.provided_files) == 2

    def test_invalid_priority(self):
        """Test bahwa priority harus high/medium/low."""
        with pytest.raises(Exception):
            CodingTaskRequest(
                task_description="Test",
                expected_output="Test",
                priority="urgent",  # Invalid
            )

    def test_task_description_too_short(self):
        """Test bahwa task_description minimal 10 chars."""
        with pytest.raises(Exception):
            CodingTaskRequest(
                task_description="Short",
                expected_output="Test",
            )

    def test_timeout_bounds(self):
        """Test timeout_minutes harus 1-120."""
        # Terlalu kecil
        with pytest.raises(Exception):
            CodingTaskRequest(
                task_description="Test task description",
                expected_output="Test",
                timeout_minutes=0,
            )
        # Terlalu besar
        with pytest.raises(Exception):
            CodingTaskRequest(
                task_description="Test task description",
                expected_output="Test",
                timeout_minutes=121,
            )


class TestTaskResult:
    """Test untuk TaskResult model."""

    def test_pending_factory(self):
        """Test factory method untuk PENDING status."""
        result = TaskResult.pending(task_id="abc123", workspace_path="/tmp/test")
        assert result.task_id == "abc123"
        assert result.status == TaskStatus.PENDING
        assert result.workspace_path == "/tmp/test"
        assert result.started_at is not None

    def test_to_dict_from_dict(self):
        """Test serialisasi/deserialisasi."""
        result = TaskResult.pending(task_id="test1", workspace_path="/tmp/ws")
        result.status = TaskStatus.SUCCESS
        result.summary = "Done"
        result.files_created = ["file1.py", "file2.py"]

        data = result.to_dict()
        restored = TaskResult.from_dict(data)
        assert restored.task_id == result.task_id
        assert restored.status == TaskStatus.SUCCESS
        assert restored.summary == "Done"
        assert restored.files_created == ["file1.py", "file2.py"]


class TestTaskStatusResponse:
    """Test untuk TaskStatusResponse model."""

    def test_from_task_result(self):
        """Test conversion dari TaskResult."""
        result = TaskResult.pending(task_id="t1", workspace_path="/tmp/w1")
        result.status = TaskStatus.SUCCESS
        result.summary = "Complete"
        result.files_created = ["a.py"]

        response = TaskStatusResponse.from_task_result(result)
        assert response.task_id == "t1"
        assert response.status == TaskStatus.SUCCESS
        assert response.summary == "Complete"
        assert response.files_created == ["a.py"]

    def test_with_progress(self):
        """Test progress message."""
        result = TaskResult.pending(task_id="t1")
        response = TaskStatusResponse.from_task_result(
            result, progress="Agent sedang menulis kode..."
        )
        assert response.progress == "Agent sedang menulis kode..."
"""Unit tests for shared.config_loader"""

import os
import tempfile
import json
import yaml
from pathlib import Path

import pytest

from shared.config_loader import load_config


class TestConfigLoader:
    """Test cases for config_loader.py"""

    def setup_method(self):
        """Set up test fixtures"""
        # Save original environment
        self.original_env = dict(os.environ)

    def teardown_method(self):
        """Restore original environment"""
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_load_yaml_config(self):
        """Test loading a YAML configuration file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config"
            config_path.mkdir()

            test_config = {"key1": "value1", "key2": 42, "key3": True}
            yaml_file = config_path / "test.yaml"
            with open(yaml_file, "w") as f:
                yaml.dump(test_config, f)

            # Temporarily patch CONFIG_ROOT
            import shared.config_loader as cl
            original_root = cl.CONFIG_ROOT
            cl.CONFIG_ROOT = config_path

            try:
                result = load_config("test.yaml")
                assert result == test_config
            finally:
                cl.CONFIG_ROOT = original_root

    def test_load_json_config(self):
        """Test loading a JSON configuration file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config"
            config_path.mkdir()

            test_config = {"key1": "value1", "key2": 42, "key3": False}
            json_file = config_path / "test.json"
            with open(json_file, "w") as f:
                json.dump(test_config, f)

            import shared.config_loader as cl
            original_root = cl.CONFIG_ROOT
            cl.CONFIG_ROOT = config_path

            try:
                result = load_config("test.json")
                assert result == test_config
            finally:
                cl.CONFIG_ROOT = original_root

    def test_env_override_string(self):
        """Test environment variable override for string values"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config"
            config_path.mkdir()

            test_config = {"database_url": "postgresql://localhost/db"}
            yaml_file = config_path / "test.yaml"
            with open(yaml_file, "w") as f:
                yaml.dump(test_config, f)

            os.environ["DATABASE_URL"] = "postgresql://prod/db"

            import shared.config_loader as cl
            original_root = cl.CONFIG_ROOT
            cl.CONFIG_ROOT = config_path

            try:
                result = load_config("test.yaml")
                assert result["database_url"] == "postgresql://prod/db"
            finally:
                cl.CONFIG_ROOT = original_root

    def test_env_override_json_value(self):
        """Test environment variable override with JSON-parsable values"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config"
            config_path.mkdir()

            test_config = {"port": 8080, "debug": False, "tags": ["a", "b"]}
            yaml_file = config_path / "test.yaml"
            with open(yaml_file, "w") as f:
                yaml.dump(test_config, f)

            os.environ["PORT"] = "9090"
            os.environ["DEBUG"] = "true"
            os.environ["TAGS"] = '["x", "y", "z"]'

            import shared.config_loader as cl
            original_root = cl.CONFIG_ROOT
            cl.CONFIG_ROOT = config_path

            try:
                result = load_config("test.yaml")
                assert result["port"] == 9090
                assert result["debug"] is True
                assert result["tags"] == ["x", "y", "z"]
            finally:
                cl.CONFIG_ROOT = original_root

    def test_file_not_found(self):
        """Test FileNotFoundError for missing config file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config"
            config_path.mkdir()

            import shared.config_loader as cl
            original_root = cl.CONFIG_ROOT
            cl.CONFIG_ROOT = config_path

            try:
                with pytest.raises(FileNotFoundError):
                    load_config("nonexistent.yaml")
            finally:
                cl.CONFIG_ROOT = original_root

    def test_unsupported_extension(self):
        """Test ValueError for unsupported file extension"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config"
            config_path.mkdir()

            txt_file = config_path / "test.txt"
            txt_file.write_text("content")

            import shared.config_loader as cl
            original_root = cl.CONFIG_ROOT
            cl.CONFIG_ROOT = config_path

            try:
                with pytest.raises(ValueError, match="Unsupported config file type"):
                    load_config("test.txt")
            finally:
                cl.CONFIG_ROOT = original_root
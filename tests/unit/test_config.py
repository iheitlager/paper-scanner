#!/usr/bin/env python3

"""Unit tests for config module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from paper_scanner.web.config import Config, ConfigManager, get_config


class TestConfig:
    """Tests for Config dataclass."""

    def test_initialization_with_defaults(self):
        """Test Config initialization with default values."""
        config = Config()
        assert config.database_url == "postgresql://pdfuser:pdfpass@localhost:5432/pdfdb"
        assert config.env == "local"
        assert config.host == "0.0.0.0"
        assert config.port == 8080
        assert config.debug is False
        assert config.log_level == "INFO"

    def test_initialization_with_custom_values(self):
        """Test Config initialization with custom values."""
        config = Config(
            database_url="postgresql://custom@localhost/db",
            env="docker",
            port=9000,
            debug=True,
            log_level="DEBUG",
        )
        assert config.database_url == "postgresql://custom@localhost/db"
        assert config.env == "docker"
        assert config.port == 9000
        assert config.debug is True
        assert config.log_level == "DEBUG"

    def test_invalid_environment(self):
        """Test that invalid environment raises ValueError."""
        with pytest.raises(ValueError, match="ENV must be one of"):
            Config(env="invalid")

    def test_invalid_port(self):
        """Test that invalid port raises ValueError."""
        with pytest.raises(ValueError, match="PORT must be between"):
            Config(port=70000)

        with pytest.raises(ValueError, match="PORT must be between"):
            Config(port=0)

    def test_invalid_log_level(self):
        """Test that invalid log level raises ValueError."""
        with pytest.raises(ValueError, match="LOG_LEVEL must be one of"):
            Config(log_level="INVALID")

    def test_valid_log_levels(self):
        """Test all valid log levels."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            config = Config(log_level=level)
            assert config.log_level == level

    def test_valid_environments(self):
        """Test all valid environments."""
        for env in ["local", "docker", "production"]:
            config = Config(env=env)
            assert config.env == env

    def test_to_dict(self):
        """Test conversion to dictionary."""
        config = Config(
            database_url="postgresql://user:pass@localhost/db",
            port=5000,
            debug=True,
        )
        config_dict = config.to_dict()

        assert isinstance(config_dict, dict)
        assert config_dict["database_url"] == config.database_url
        assert config_dict["port"] == 5000
        assert config_dict["debug"] is True

    def test_repr_masks_database_url(self):
        """Test that __repr__ masks sensitive database URL."""
        config = Config(database_url="postgresql://user:pass@localhost/db")
        repr_str = repr(config)

        assert "postgresql://" in repr_str
        assert "user:pass" not in repr_str
        assert "***" in repr_str

    def test_debug_warning_in_non_local(self):
        """Test that debug warning is logged for non-local environments."""
        with patch("paper_scanner.web.config.logger") as mock_logger:
            Config(env="production", debug=True)
            mock_logger.warning.assert_called_once()

    def test_pdf_base_dir_expansion(self):
        """Test that PDF base directory is expanded and resolved."""
        config = Config(pdf_base_dir="~/test")
        assert "~" not in config.pdf_base_dir
        assert config.pdf_base_dir.startswith("/")


class TestConfigManager:
    """Tests for ConfigManager class."""

    def test_initialization(self):
        """Test ConfigManager initialization."""
        manager = ConfigManager()
        assert manager.env_file == ".env"

    def test_initialization_with_custom_env_file(self):
        """Test ConfigManager initialization with custom env file."""
        manager = ConfigManager(env_file="/custom/.env")
        assert manager.env_file == "/custom/.env"

    def test_load_without_env_file(self):
        """Test loading config without .env file."""
        manager = ConfigManager(env_file="/nonexistent/.env")
        config = manager.load()

        assert isinstance(config, Config)
        assert config.port == 8080

    def test_load_with_defaults(self):
        """Test loading config with default values."""
        manager = ConfigManager(env_file="/nonexistent/.env")
        config = manager.load()

        assert config.database_url == "postgresql://pdfuser:pdfpass@localhost:5432/pdfdb"
        assert config.env == "local"
        assert config.host == "0.0.0.0"

    def test_load_with_environment_variables(self):
        """Test loading config respects environment variables."""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://test@localhost/testdb",
            "ENV": "docker",
            "PORT": "9000",
        }):
            manager = ConfigManager(env_file="/nonexistent/.env")
            config = manager.load()

            assert config.database_url == "postgresql://test@localhost/testdb"
            assert config.env == "docker"
            assert config.port == 9000

    def test_load_with_function_arguments(self):
        """Test that function arguments take precedence over environment variables."""
        with patch.dict(os.environ, {
            "PORT": "9000",
        }):
            manager = ConfigManager(env_file="/nonexistent/.env")
            config = manager.load(port=5000, env="production")

            assert config.port == 5000
            assert config.env == "production"

    def test_load_caching(self):
        """Test that loaded config is cached."""
        manager = ConfigManager(env_file="/nonexistent/.env")
        config1 = manager.load()
        config2 = manager.load()

        # Should be the same cached instance
        assert config1 is config2

    def test_get_bool_env(self):
        """Test boolean environment variable parsing."""
        manager = ConfigManager()

        with patch.dict(os.environ, {"TEST_VAR": "true"}):
            assert manager._get_bool_env("TEST_VAR") is True

        with patch.dict(os.environ, {"TEST_VAR": "false"}):
            assert manager._get_bool_env("TEST_VAR") is False

        with patch.dict(os.environ, {"TEST_VAR": "1"}):
            assert manager._get_bool_env("TEST_VAR") is True

        with patch.dict(os.environ, {"TEST_VAR": "0"}):
            assert manager._get_bool_env("TEST_VAR") is False

        with patch.dict(os.environ, {}, clear=True):
            assert manager._get_bool_env("NONEXISTENT", default=True) is True

    def test_get_int_env(self):
        """Test integer environment variable parsing."""
        manager = ConfigManager()

        with patch.dict(os.environ, {"PORT": "8080"}):
            assert manager._get_int_env("PORT") == 8080

        with patch.dict(os.environ, {"PORT": "invalid"}):
            assert manager._get_int_env("PORT", default=5000) == 5000

        with patch.dict(os.environ, {}, clear=True):
            assert manager._get_int_env("NONEXISTENT", default=9000) == 9000

    def test_get_without_load(self):
        """Test that get() raises error if config not loaded."""
        manager = ConfigManager()
        with pytest.raises(RuntimeError, match="Configuration not loaded"):
            manager.get()

    def test_get_after_load(self):
        """Test that get() returns loaded config."""
        manager = ConfigManager(env_file="/nonexistent/.env")
        manager.load()
        config = manager.get()

        assert isinstance(config, Config)

    def test_reload(self):
        """Test reloading configuration."""
        manager = ConfigManager(env_file="/nonexistent/.env")
        config1 = manager.load(port=8080)
        manager.reload()
        config2 = manager.load(port=9000)

        # Should be different instances
        assert config1 is not config2
        assert config1.port != config2.port


class TestGetConfigFunction:
    """Tests for get_config helper function."""

    def test_get_config_basic(self):
        """Test basic get_config usage."""
        config = get_config()
        assert isinstance(config, Config)

    def test_get_config_with_arguments(self):
        """Test get_config with custom arguments."""
        config = get_config(
            database_url="postgresql://custom@localhost/db",
            env="production",
            port=3000,
        )

        assert config.database_url == "postgresql://custom@localhost/db"
        assert config.env == "production"
        assert config.port == 3000

    def test_get_config_caching(self):
        """Test that get_config returns cached instance."""
        config1 = get_config()
        config2 = get_config()

        assert config1 is config2

    def test_get_config_environment_variables(self):
        """Test get_config respects environment variables."""
        with patch.dict(os.environ, {
            "ENV": "docker",
            "DEBUG": "true",
        }):
            # Need to reload to pick up new env vars
            from paper_scanner.web import config as config_module
            config_module._config_manager.reload()

            cfg = get_config()
            assert cfg.env == "docker"
            assert cfg.debug is True


class TestConfigIntegration:
    """Integration tests for config system."""

    def test_full_precedence_chain(self):
        """Test full configuration precedence: args > env > defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("PORT=7000\nLOG_LEVEL=DEBUG\n")

            with patch.dict(os.environ, {
                "PORT": "8000",
                "DEBUG": "true",
            }):
                manager = ConfigManager(env_file=str(env_file))

                # Function args should take precedence
                config = manager.load(port=9000)

                assert config.port == 9000  # From function arg
                assert config.debug is True  # From env var
                assert config.log_level == "DEBUG"  # From .env file

    def test_missing_env_file_warning(self):
        """Test that missing .env file is handled gracefully."""
        manager = ConfigManager(env_file="/nonexistent/.env")
        with patch("paper_scanner.web.config.logger") as mock_logger:
            config = manager.load()
            # Should still load config
            assert isinstance(config, Config)

    def test_config_validation_on_load(self):
        """Test that config validation happens during load."""
        manager = ConfigManager(env_file="/nonexistent/.env")

        with pytest.raises(ValueError):
            manager.load(env="invalid_env")

        with pytest.raises(ValueError):
            manager.load(port=99999)

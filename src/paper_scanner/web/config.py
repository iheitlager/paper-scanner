"""
Configuration management for PDF Browser application.

Supports configuration from multiple sources with the following precedence:
1. Command-line arguments (highest priority)
2. Environment variables
3. .env file
4. Default values (lowest priority)
"""

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Configuration for PDF Browser application.

    Attributes:
        database_url: PostgreSQL connection URL
        pdf_base_dir: Base directory for PDF files
        env: Environment mode ('local', 'docker', 'production')
        host: Host to bind to
        port: Port to bind to
        debug: Enable debug mode
        log_level: Logging level
    """

    database_url: str = "postgresql://pdfuser:pdfpass@localhost:5432/pdfdb"
    pdf_base_dir: str = "/Users/iheitlager/wc/papers"
    env: str = "local"
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False
    log_level: str = "INFO"

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        # Validate environment
        valid_envs = ("local", "docker", "production")
        if self.env not in valid_envs:
            raise ValueError(f"ENV must be one of {valid_envs}, got '{self.env}'")

        # Validate port
        if not 1 <= self.port <= 65535:
            raise ValueError(f"PORT must be between 1 and 65535, got {self.port}")

        # Validate log level
        valid_levels = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        if self.log_level not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}, got '{self.log_level}'")

        # Validate and expand pdf_base_dir
        pdf_path = Path(self.pdf_base_dir).expanduser()
        if not pdf_path.exists():
            logger.warning(f"PDF_BASE_DIR does not exist: {pdf_path}")
        self.pdf_base_dir = str(pdf_path.resolve())

        # Debug mode only in local environment
        if self.debug and self.env != "local":
            logger.warning("Debug mode only recommended for local environment")

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary.

        Returns:
            Dictionary representation of configuration
        """
        return {
            "database_url": self.database_url,
            "pdf_base_dir": self.pdf_base_dir,
            "env": self.env,
            "host": self.host,
            "port": self.port,
            "debug": self.debug,
            "log_level": self.log_level,
        }

    def __repr__(self) -> str:
        """String representation of configuration (sensitive data masked)."""
        db_display = self.database_url.replace(
            self.database_url.split("@")[0].split("://")[1] if "@" in self.database_url else "",
            "***",
        ) if "@" in self.database_url else "***"

        return (
            f"Config(database_url='{db_display}', pdf_base_dir='{self.pdf_base_dir}', "
            f"env='{self.env}', host='{self.host}', port={self.port}, "
            f"debug={self.debug}, log_level='{self.log_level}')"
        )


class ConfigManager:
    """Manages application configuration from multiple sources.

    Configuration sources (in priority order):
    1. Command-line arguments
    2. Environment variables
    3. .env file
    4. Default values
    """

    def __init__(self, env_file: Optional[str] = None) -> None:
        """Initialize configuration manager.

        Args:
            env_file: Path to .env file (default: .env in current directory)
        """
        self.env_file = env_file or ".env"
        self._config: Optional[Config] = None

    def _load_env_file(self) -> None:
        """Load environment variables from .env file."""
        env_path = Path(self.env_file)
        if not env_path.exists():
            logger.debug(f"No .env file found at {env_path}")
            return

        try:
            from dotenv import load_dotenv
            load_dotenv(str(env_path))
            logger.info(f"Loaded environment from {env_path}")
        except ImportError:
            logger.warning("python-dotenv not installed, skipping .env file")

    def _get_int_env(self, key: str, default: Optional[int] = None) -> Optional[int]:
        """Get integer environment variable.

        Args:
            key: Environment variable name
            default: Default value if not found

        Returns:
            Integer value or default
        """
        value = os.getenv(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            logger.warning(f"Invalid integer value for {key}: {value}, using default")
            return default

    def _get_bool_env(self, key: str, default: bool = False) -> bool:
        """Get boolean environment variable.

        Args:
            key: Environment variable name
            default: Default value if not found

        Returns:
            Boolean value
        """
        value = os.getenv(key, "").lower()
        if value in ("true", "1", "yes", "on"):
            return True
        if value in ("false", "0", "no", "off"):
            return False
        return default

    @lru_cache(maxsize=1)
    def load(
        self,
        database_url: Optional[str] = None,
        pdf_base_dir: Optional[str] = None,
        env: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        debug: Optional[bool] = None,
        log_level: Optional[str] = None,
    ) -> Config:
        """Load and cache configuration from multiple sources.

        Configuration priority (highest to lowest):
        1. Function arguments
        2. Environment variables
        3. .env file
        4. Default values

        Args:
            database_url: PostgreSQL connection URL
            pdf_base_dir: Base directory for PDF files
            env: Environment mode
            host: Host to bind to
            port: Port to bind to
            debug: Enable debug mode
            log_level: Logging level

        Returns:
            Config instance with loaded configuration
        """
        # Load .env file first
        self._load_env_file()

        # Build config with priority: args > env vars > defaults
        config = Config(
            database_url=database_url or os.getenv("DATABASE_URL", "postgresql://pdfuser:pdfpass@localhost:5432/pdfdb"),
            pdf_base_dir=pdf_base_dir or os.getenv("PDF_BASE_DIR", "/Users/iheitlager/wc/papers"),
            env=env or os.getenv("ENV", "local"),
            host=host or os.getenv("HOST", "0.0.0.0"),
            port=port or self._get_int_env("PORT", 8080),
            debug=debug if debug is not None else self._get_bool_env("DEBUG", False),
            log_level=log_level or os.getenv("LOG_LEVEL", "INFO"),
        )

        self._config = config
        logger.debug(f"Configuration loaded: {config}")
        return config

    def get(self) -> Config:
        """Get loaded configuration.

        Returns:
            Config instance

        Raises:
            RuntimeError: If configuration not yet loaded
        """
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call load() first.")
        return self._config

    def reload(self) -> None:
        """Clear cached configuration to allow fresh load."""
        self._config = None
        # Clear LRU cache
        self.load.cache_clear()


# Global configuration manager instance
_config_manager = ConfigManager()


def get_config(
    database_url: Optional[str] = None,
    pdf_base_dir: Optional[str] = None,
    env: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    debug: Optional[bool] = None,
    log_level: Optional[str] = None,
) -> Config:
    """Get application configuration (cached).
    
    First call will load configuration, subsequent calls return cached config.
    
    Args:
        database_url: PostgreSQL connection URL
        pdf_base_dir: Base directory for PDF files
        env: Environment mode
        host: Host to bind to
        port: Port to bind to
        debug: Enable debug mode
        log_level: Logging level
        
    Returns:
        Config instance
    """
    return _config_manager.load(
        database_url=database_url,
        pdf_base_dir=pdf_base_dir,
        env=env,
        host=host,
        port=port,
        debug=debug,
        log_level=log_level,
    )

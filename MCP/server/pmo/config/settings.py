"""
Configuration management for PMO MCP Server.

This module loads configuration from YAML files and environment variables,
providing a centralized settings object for the entire application.
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, field


# Get the base directory (pmo_refactored root)
BASE_DIR = Path(__file__).parent.parent.absolute()
CONFIG_DIR = BASE_DIR / "config"


@dataclass
class APIConfig:
    """API-related configuration."""
    base_url: str = "http://localhost:5000"
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: int = 1


@dataclass
class ServerConfig:
    """Server-related configuration."""
    name: str = "PMO"
    version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"


@dataclass
class MetadataConfig:
    """Metadata-related configuration."""
    directory: str = "metadata"
    cache_enabled: bool = True
    auto_reload: bool = False


@dataclass
class ValidationConfig:
    """Validation-related configuration."""
    strict_mode: bool = True
    date_format: str = "%Y-%m-%d"
    allowed_intervals: list = field(default_factory=lambda: ["Weekly", "Monthly", "Quarterly"])


@dataclass
class PromptsConfig:
    """Prompts-related configuration."""
    directory: str = "config/prompts"
    enable_hot_reload: bool = False
    default_language: str = "en"


@dataclass
class LoggingConfig:
    """Logging-related configuration."""
    enabled: bool = True
    file: str = "logs/pmo_mcp_server.log"
    max_file_size_mb: int = 10
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class PerformanceConfig:
    """Performance-related configuration."""
    enable_caching: bool = True
    cache_ttl_seconds: int = 300
    max_concurrent_requests: int = 10


class Settings:
    """
    Main settings class that loads configuration from YAML and environment variables.

    Priority order (highest to lowest):
    1. Environment variables (PMO_*)
    2. Config YAML file
    3. Default values
    """

    def __init__(self, config_file: Optional[Path] = None):
        """
        Initialize settings.

        Args:
            config_file: Path to config YAML file. Defaults to config/config.yaml
        """
        self.config_file = config_file or CONFIG_DIR / "config.yaml"
        self.config_data = self._load_yaml_config()

        # Initialize configuration sections
        self.api = self._init_api_config()
        self.server = self._init_server_config()
        self.metadata = self._init_metadata_config()
        self.validation = self._init_validation_config()
        self.prompts = self._init_prompts_config()
        self.logging = self._init_logging_config()
        self.performance = self._init_performance_config()

    def _load_yaml_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if not self.config_file.exists():
            print(f"Warning: Config file not found at {self.config_file}, using defaults")
            return {}

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Warning: Error loading config file: {e}, using defaults")
            return {}

    def _get_env(self, key: str, default: Any = None) -> Any:
        """Get environment variable with PMO_ prefix."""
        env_key = f"PMO_{key.upper()}"
        value = os.getenv(env_key)

        if value is None:
            return default

        # Convert string to appropriate type based on default
        if isinstance(default, bool):
            return value.lower() in ('true', '1', 'yes', 'on')
        elif isinstance(default, int):
            try:
                return int(value)
            except ValueError:
                return default
        elif isinstance(default, float):
            try:
                return float(value)
            except ValueError:
                return default

        return value

    def _init_api_config(self) -> APIConfig:
        """Initialize API configuration."""
        api_data = self.config_data.get('api', {})
        return APIConfig(
            base_url=self._get_env('API_BASE_URL', api_data.get('base_url', "http://localhost:5000")),
            timeout=self._get_env('API_TIMEOUT', api_data.get('timeout', 30)),
            retry_attempts=self._get_env('API_RETRY_ATTEMPTS', api_data.get('retry_attempts', 3)),
            retry_delay=self._get_env('API_RETRY_DELAY', api_data.get('retry_delay', 1))
        )

    def _init_server_config(self) -> ServerConfig:
        """Initialize server configuration."""
        server_data = self.config_data.get('server', {})
        return ServerConfig(
            name=self._get_env('SERVER_NAME', server_data.get('name', "PMO")),
            version=self._get_env('SERVER_VERSION', server_data.get('version', "1.0.0")),
            debug=self._get_env('SERVER_DEBUG', server_data.get('debug', False)),
            log_level=self._get_env('LOG_LEVEL', server_data.get('log_level', "INFO"))
        )

    def _init_metadata_config(self) -> MetadataConfig:
        """Initialize metadata configuration."""
        metadata_data = self.config_data.get('metadata', {})
        return MetadataConfig(
            directory=self._get_env('METADATA_DIR', metadata_data.get('directory', "metadata")),
            cache_enabled=self._get_env('CACHE_ENABLED', metadata_data.get('cache_enabled', True)),
            auto_reload=self._get_env('METADATA_AUTO_RELOAD', metadata_data.get('auto_reload', False))
        )

    def _init_validation_config(self) -> ValidationConfig:
        """Initialize validation configuration."""
        validation_data = self.config_data.get('validation', {})
        return ValidationConfig(
            strict_mode=self._get_env('VALIDATION_STRICT_MODE', validation_data.get('strict_mode', True)),
            date_format=self._get_env('VALIDATION_DATE_FORMAT', validation_data.get('date_format', "%Y-%m-%d")),
            allowed_intervals=validation_data.get('allowed_intervals', ["Weekly", "Monthly", "Quarterly"])
        )

    def _init_prompts_config(self) -> PromptsConfig:
        """Initialize prompts configuration."""
        prompts_data = self.config_data.get('prompts', {})
        return PromptsConfig(
            directory=self._get_env('PROMPTS_DIR', prompts_data.get('directory', "config/prompts")),
            enable_hot_reload=self._get_env('PROMPTS_HOT_RELOAD', prompts_data.get('enable_hot_reload', False)),
            default_language=self._get_env('PROMPTS_LANGUAGE', prompts_data.get('default_language', "en"))
        )

    def _init_logging_config(self) -> LoggingConfig:
        """Initialize logging configuration."""
        logging_data = self.config_data.get('logging', {})
        return LoggingConfig(
            enabled=self._get_env('LOGGING_ENABLED', logging_data.get('enabled', True)),
            file=self._get_env('LOG_FILE', logging_data.get('file', "logs/pmo_mcp_server.log")),
            max_file_size_mb=self._get_env('LOG_MAX_SIZE_MB', logging_data.get('max_file_size_mb', 10)),
            backup_count=self._get_env('LOG_BACKUP_COUNT', logging_data.get('backup_count', 5)),
            format=self._get_env('LOG_FORMAT', logging_data.get('format', "%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        )

    def _init_performance_config(self) -> PerformanceConfig:
        """Initialize performance configuration."""
        performance_data = self.config_data.get('performance', {})
        return PerformanceConfig(
            enable_caching=self._get_env('CACHE_ENABLED', performance_data.get('enable_caching', True)),
            cache_ttl_seconds=self._get_env('CACHE_TTL', performance_data.get('cache_ttl_seconds', 300)),
            max_concurrent_requests=self._get_env('MAX_CONCURRENT_REQUESTS', performance_data.get('max_concurrent_requests', 10))
        )

    def get_metadata_path(self, filename: str) -> Path:
        """Get full path to a metadata file."""
        return BASE_DIR / self.metadata.directory / filename

    def get_prompts_file(self) -> Path:
        """Get path to prompts configuration file."""
        return BASE_DIR / "config" / "prompts.yaml"

    def reload(self):
        """Reload configuration from files."""
        self.config_data = self._load_yaml_config()
        self.api = self._init_api_config()
        self.server = self._init_server_config()
        self.metadata = self._init_metadata_config()
        self.validation = self._init_validation_config()
        self.prompts = self._init_prompts_config()
        self.logging = self._init_logging_config()
        self.performance = self._init_performance_config()


# Global settings instance
settings = Settings()


# Convenience function to get settings
def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings

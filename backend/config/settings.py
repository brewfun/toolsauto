#!/usr/bin/env python3
"""
Configuration settings for K8s Auto Installer
Centralizes all application settings with environment-specific overrides
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Environment(Enum):
    """Application environments"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"

class LogLevel(Enum):
    """Logging levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

@dataclass
class DatabaseConfig:
    """Database configuration"""
    url: str = "sqlite:///k8s_installer.db"
    echo: bool = False
    pool_size: int = 10
    max_overflow: int = 20

@dataclass
class RedisConfig:
    """Redis configuration for caching and sessions"""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    socket_timeout: int = 30

@dataclass
class FlaskConfig:
    """Flask application configuration"""
    secret_key: str = "dev-secret-key-change-in-production"
    debug: bool = False
    testing: bool = False
    host: str = "0.0.0.0"
    port: int = 5000
    max_content_length: int = 16 * 1024 * 1024  # 16MB

@dataclass
class WebSocketConfig:
    """WebSocket configuration for real-time logs"""
    enabled: bool = True
    host: str = "localhost"
    port: int = 8765
    max_connections: int = 100

@dataclass
class K8sConfig:
    """Kubernetes installation defaults"""
    # Supported versions
    supported_versions: List[str] = None
    default_version: str = "1.30"
    
    # Network configuration
    default_pod_cidr: str = "10.10.0.0/16"
    default_service_cidr: str = "10.96.0.0/12"
    
    # CNI options
    supported_cnis: List[str] = None
    default_cni: str = "cilium"
    
    # Timeouts (seconds)
    api_server_timeout: int = 300
    pod_ready_timeout: int = 600
    installation_timeout: int = 1800
    
    # Retry configuration
    max_retries: int = 3
    retry_delay: int = 5
    
    def __post_init__(self):
        if self.supported_versions is None:
            self.supported_versions = ["1.28", "1.29", "1.30", "1.31"]
        if self.supported_cnis is None:
            self.supported_cnis = ["cilium", "calico", "flannel"]

@dataclass
class SSHConfig:
    """SSH connection defaults"""
    default_user: str = "ubuntu"
    connection_timeout: int = 30
    command_timeout: int = 300
    max_connections: int = 50
    keep_alive_interval: int = 60

@dataclass
class SecurityConfig:
    """Security configuration"""
    enable_rbac: bool = True
    enable_network_policies: bool = True
    enable_pod_security_policies: bool = False
    jwt_secret_key: str = "jwt-secret-change-in-production"
    jwt_expiration_hours: int = 24
    
    # Rate limiting
    rate_limit_per_minute: int = 60
    rate_limit_burst: int = 100

@dataclass
class MonitoringConfig:
    """Monitoring and observability configuration"""
    enable_metrics: bool = True
    enable_health_checks: bool = True
    enable_prometheus: bool = False
    
    # Metrics collection
    metrics_port: int = 9090
    health_check_interval: int = 30
    
    # Log retention
    log_retention_days: int = 30
    max_log_files: int = 10
    max_log_size_mb: int = 100

@dataclass
class StorageConfig:
    """Storage configuration"""
    # Local storage
    logs_directory: str = str(BASE_DIR / "logs")
    temp_directory: str = str(BASE_DIR / "temp")
    backup_directory: str = str(BASE_DIR / "backups")
    
    # File upload limits
    max_upload_size: int = 50 * 1024 * 1024  # 50MB
    allowed_extensions: List[str] = None
    
    def __post_init__(self):
        if self.allowed_extensions is None:
            self.allowed_extensions = ['.yaml', '.yml', '.json', '.pem', '.key']
        
        # Ensure directories exist
        for directory in [self.logs_directory, self.temp_directory, self.backup_directory]:
            Path(directory).mkdir(parents=True, exist_ok=True)

class Settings:
    """Main settings class with environment-specific configurations"""
    
    def __init__(self):
        self.environment = Environment(os.getenv("ENVIRONMENT", "development"))
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        
        # Initialize configurations
        self.flask = self._get_flask_config()
        self.database = self._get_database_config()
        self.redis = self._get_redis_config()
        self.websocket = self._get_websocket_config()
        self.k8s = K8sConfig()
        self.ssh = SSHConfig()
        self.security = self._get_security_config()
        self.monitoring = self._get_monitoring_config()
        self.storage = StorageConfig()
        
        # Logging configuration
        self.log_level = LogLevel(os.getenv("LOG_LEVEL", "INFO"))
        self.log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        self.log_file = os.path.join(self.storage.logs_directory, "app.log")
    
    def _get_flask_config(self) -> FlaskConfig:
        """Get Flask configuration based on environment"""
        config = FlaskConfig()
        
        if self.environment == Environment.PRODUCTION:
            config.secret_key = os.getenv("SECRET_KEY", config.secret_key)
            config.debug = False
            config.host = os.getenv("FLASK_HOST", "0.0.0.0")
            config.port = int(os.getenv("FLASK_PORT", "5000"))
        elif self.environment == Environment.DEVELOPMENT:
            config.debug = True
            config.host = os.getenv("FLASK_HOST", "127.0.0.1")
            config.port = int(os.getenv("FLASK_PORT", "5000"))
        elif self.environment == Environment.TESTING:
            config.testing = True
            config.secret_key = "testing-secret-key"
        
        return config
    
    def _get_database_config(self) -> DatabaseConfig:
        """Get database configuration"""
        config = DatabaseConfig()
        
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            config.url = db_url
        elif self.environment == Environment.TESTING:
            config.url = "sqlite:///:memory:"
        elif self.environment == Environment.PRODUCTION:
            config.url = os.getenv(
                "DATABASE_URL",
                f"sqlite:///{BASE_DIR}/data/production.db"
            )
        else:
            config.url = f"sqlite:///{BASE_DIR}/data/development.db"
        
        config.echo = self.debug and self.environment == Environment.DEVELOPMENT
        
        return config
    
    def _get_redis_config(self) -> RedisConfig:
        """Get Redis configuration"""
        return RedisConfig(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            password=os.getenv("REDIS_PASSWORD"),
        )
    
    def _get_websocket_config(self) -> WebSocketConfig:
        """Get WebSocket configuration"""
        return WebSocketConfig(
            enabled=os.getenv("WEBSOCKET_ENABLED", "true").lower() == "true",
            host=os.getenv("WEBSOCKET_HOST", "localhost"),
            port=int(os.getenv("WEBSOCKET_PORT", "8765")),
        )
    
    def _get_security_config(self) -> SecurityConfig:
        """Get security configuration"""
        config = SecurityConfig()
        
        if self.environment == Environment.PRODUCTION:
            config.jwt_secret_key = os.getenv("JWT_SECRET_KEY", config.jwt_secret_key)
            config.enable_rbac = os.getenv("ENABLE_RBAC", "true").lower() == "true"
            config.rate_limit_per_minute = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
        
        return config
    
    def _get_monitoring_config(self) -> MonitoringConfig:
        """Get monitoring configuration"""
        config = MonitoringConfig()
        
        config.enable_metrics = os.getenv("ENABLE_METRICS", "true").lower() == "true"
        config.enable_prometheus = os.getenv("ENABLE_PROMETHEUS", "false").lower() == "true"
        config.metrics_port = int(os.getenv("METRICS_PORT", "9090"))
        
        return config
    
    def get_env_vars(self) -> Dict[str, Any]:
        """Get all configuration as environment variables dictionary"""
        return {
            "ENVIRONMENT": self.environment.value,
            "DEBUG": str(self.debug),
            "FLASK_HOST": self.flask.host,
            "FLASK_PORT": str(self.flask.port),
            "DATABASE_URL": self.database.url,
            "REDIS_HOST": self.redis.host,
            "REDIS_PORT": str(self.redis.port),
            "LOG_LEVEL": self.log_level.value,
            "WEBSOCKET_ENABLED": str(self.websocket.enabled),
            "ENABLE_METRICS": str(self.monitoring.enable_metrics),
        }
    
    def validate(self) -> List[str]:
        """Validate configuration and return any errors"""
        errors = []
        
        # Validate required directories
        for directory in [self.storage.logs_directory, self.storage.temp_directory]:
            if not os.path.exists(directory):
                try:
                    Path(directory).mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    errors.append(f"Cannot create directory {directory}: {e}")
        
        # Validate Flask secret key in production
        if (self.environment == Environment.PRODUCTION and 
            self.flask.secret_key == "dev-secret-key-change-in-production"):
            errors.append("SECRET_KEY must be set in production environment")
        
        # Validate JWT secret key in production
        if (self.environment == Environment.PRODUCTION and 
            self.security.jwt_secret_key == "jwt-secret-change-in-production"):
            errors.append("JWT_SECRET_KEY must be set in production environment")
        
        # Validate K8s configuration
        if self.k8s.default_version not in self.k8s.supported_versions:
            errors.append(f"Default K8s version {self.k8s.default_version} not in supported versions")
        
        if self.k8s.default_cni not in self.k8s.supported_cnis:
            errors.append(f"Default CNI {self.k8s.default_cni} not in supported CNIs")
        
        return errors
    
    def __str__(self) -> str:
        """String representation of settings"""
        return f"Settings(environment={self.environment.value}, debug={self.debug})"

# Global settings instance
settings = Settings()

# Validation on import
validation_errors = settings.validate()
if validation_errors and settings.environment == Environment.PRODUCTION:
    raise RuntimeError(f"Configuration validation failed: {'; '.join(validation_errors)}")

# Export commonly used configs
__all__ = [
    'settings',
    'BASE_DIR',
    'Environment',
    'LogLevel',
    'DatabaseConfig',
    'RedisConfig',
    'FlaskConfig',
    'WebSocketConfig',
    'K8sConfig',
    'SSHConfig',
    'SecurityConfig',
    'MonitoringConfig',
    'StorageConfig',
    'Settings'
]
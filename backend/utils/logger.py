#!/usr/bin/env python3
"""
Advanced logging framework for K8s Auto Installer
Provides structured logging with real-time streaming capabilities
"""

import logging
import logging.handlers
import sys
import json
import time
import threading
import queue
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Union
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, asdict
import asyncio
import websockets

from ..config.settings import settings

class LogLevel(Enum):
    """Log levels with numeric values"""
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50

class LogCategory(Enum):
    """Log categories for better organization"""
    SYSTEM = "system"
    INSTALLATION = "installation"
    NETWORKING = "networking"
    SECURITY = "security"
    API = "api"
    DATABASE = "database"
    WEBSOCKET = "websocket"

@dataclass
class LogEntry:
    """Structured log entry"""
    timestamp: float
    level: str
    category: str
    component: str
    message: str
    step: Optional[str] = None
    installation_id: Optional[str] = None
    host: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), default=str)

class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_entry = LogEntry(
            timestamp=record.created,
            level=record.levelname,
            category=getattr(record, 'category', LogCategory.SYSTEM.value),
            component=record.name,
            message=record.getMessage(),
            step=getattr(record, 'step', None),
            installation_id=getattr(record, 'installation_id', None),
            host=getattr(record, 'host', None),
            extra=getattr(record, 'extra', {}) if self.include_extra else None
        )
        
        return log_entry.to_json()

class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output"""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green  
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors and sys.stdout.isatty()
        
        self.format_string = (
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    
    def format(self, record: logging.LogRecord) -> str:
        """Format with colors if enabled"""
        if self.use_colors:
            color = self.COLORS.get(record.levelname, '')
            reset = self.COLORS['RESET']
            
            # Add step info if available
            step_info = ""
            if hasattr(record, 'step') and record.step:
                step_info = f" [{record.step}]"
            
            # Add installation ID if available
            install_info = ""
            if hasattr(record, 'installation_id') and record.installation_id:
                install_info = f" ({record.installation_id[:8]})"
            
            formatted = (
                f"{color}%(asctime)s{reset} - "
                f"%(name)s{install_info}{step_info} - "
                f"{color}%(levelname)s{reset} - "
                f"%(message)s"
            )
            
            formatter = logging.Formatter(formatted)
            return formatter.format(record)
        else:
            formatter = logging.Formatter(self.format_string)
            return formatter.format(record)

class WebSocketHandler(logging.Handler):
    """Log handler that streams logs via WebSocket"""
    
    def __init__(self, websocket_url: Optional[str] = None):
        super().__init__()
        self.websocket_url = websocket_url
        self.clients = set()
        self.log_queue = queue.Queue()
        self.running = False
        self.worker_thread = None
    
    def add_client(self, websocket):
        """Add WebSocket client"""
        self.clients.add(websocket)
    
    def remove_client(self, websocket):
        """Remove WebSocket client"""
        self.clients.discard(websocket)
    
    def emit(self, record: logging.LogRecord):
        """Emit log record to WebSocket clients"""
        if not self.clients:
            return
        
        try:
            log_entry = LogEntry(
                timestamp=record.created,
                level=record.levelname,
                category=getattr(record, 'category', LogCategory.SYSTEM.value),
                component=record.name,
                message=record.getMessage(),
                step=getattr(record, 'step', None),
                installation_id=getattr(record, 'installation_id', None),
                host=getattr(record, 'host', None),
                extra=getattr(record, 'extra', {})
            )
            
            self.log_queue.put(log_entry.to_json())
            
        except Exception:
            self.handleError(record)
    
    def start_streaming(self):
        """Start streaming thread"""
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(target=self._stream_worker, daemon=True)
            self.worker_thread.start()
    
    def stop_streaming(self):
        """Stop streaming thread"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
    
    def _stream_worker(self):
        """Worker thread for streaming logs"""
        while self.running:
            try:
                # Get log entry with timeout
                try:
                    log_json = self.log_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                # Send to all connected clients
                disconnected_clients = set()
                for client in self.clients.copy():
                    try:
                        asyncio.run(client.send(log_json))
                    except Exception:
                        disconnected_clients.add(client)
                
                # Remove disconnected clients
                for client in disconnected_clients:
                    self.clients.discard(client)
                    
            except Exception as e:
                # Log streaming errors to file handler only
                file_logger = logging.getLogger('websocket_handler')
                file_logger.error(f"Error in log streaming: {e}")

class InstallationLogger:
    """Enhanced logger for installation processes"""
    
    def __init__(self, 
                 installation_id: str,
                 component: str = "installer",
                 websocket_handler: Optional[WebSocketHandler] = None):
        self.installation_id = installation_id
        self.component = component
        self.websocket_handler = websocket_handler
        self.current_step = None
        self.current_host = None
        
        # Create logger instance
        self.logger = logging.getLogger(f"{component}.{installation_id}")
        
        # Don't propagate to avoid duplicate logs
        self.logger.propagate = False
        
        # Setup handlers if not already configured
        if not self.logger.handlers:
            self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup log handlers for this installation"""
        # Console handler with colors
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(ColoredFormatter())
        console_handler.setLevel(logging.INFO)
        self.logger.addHandler(console_handler)
        
        # File handler for this installation
        log_file = Path(settings.storage.logs_directory) / f"installation_{self.installation_id}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(JSONFormatter())
        file_handler.setLevel(logging.DEBUG)
        self.logger.addHandler(file_handler)
        
        # WebSocket handler if provided
        if self.websocket_handler:
            self.websocket_handler.setLevel(logging.INFO)
            self.logger.addHandler(self.websocket_handler)
        
        # Set logger level
        self.logger.setLevel(logging.DEBUG)
    
    def _add_context(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add context information to log record"""
        context = {
            'installation_id': self.installation_id,
            'category': LogCategory.INSTALLATION.value,
        }
        
        if self.current_step:
            context['step'] = self.current_step
        
        if self.current_host:
            context['host'] = self.current_host
        
        if extra:
            context.update(extra)
        
        return context
    
    def set_step(self, step: str):
        """Set current installation step"""
        self.current_step = step
    
    def set_host(self, host: str):
        """Set current host being configured"""
        self.current_host = host
    
    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log debug message"""
        self.logger.debug(message, extra=self._add_context(extra))
    
    def info(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log info message"""
        self.logger.info(message, extra=self._add_context(extra))
    
    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log warning message"""
        self.logger.warning(message, extra=self._add_context(extra))
    
    def error(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log error message"""
        self.logger.error(message, extra=self._add_context(extra))
    
    def critical(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log critical message"""
        self.logger.critical(message, extra=self._add_context(extra))
    
    def step_start(self, step: str, description: str = ""):
        """Log step start"""
        self.set_step(step)
        message = f"🚀 Starting: {step}"
        if description:
            message += f" - {description}"
        self.info(message)
    
    def step_success(self, step: str, duration: Optional[float] = None):
        """Log step success"""
        message = f"✅ Completed: {step}"
        if duration:
            message += f" ({duration:.2f}s)"
        self.info(message)
    
    def step_error(self, step: str, error: str, duration: Optional[float] = None):
        """Log step error"""
        message = f"❌ Failed: {step} - {error}"
        if duration:
            message += f" (after {duration:.2f}s)"
        self.error(message)
    
    def step_warning(self, step: str, warning: str):
        """Log step warning"""
        message = f"⚠️ Warning in {step}: {warning}"
        self.warning(message)
    
    def command_executed(self, command: str, success: bool, output: str = "", duration: Optional[float] = None):
        """Log command execution"""
        status = "✅" if success else "❌"
        message = f"{status} Command: {command}"
        
        extra = {
            'command': command,
            'success': success,
            'output': output[:500] if output else "",  # Truncate long output
        }
        
        if duration:
            extra['duration'] = duration
            message += f" ({duration:.2f}s)"
        
        if success:
            self.debug(message, extra=extra)
        else:
            self.error(message, extra=extra)
    
    def host_start(self, host: str):
        """Log host configuration start"""
        self.set_host(host)
        self.info(f"🖥️ Configuring host: {host}")
    
    def host_success(self, host: str):
        """Log host configuration success"""
        self.info(f"✅ Host configured successfully: {host}")
        self.current_host = None
    
    def host_error(self, host: str, error: str):
        """Log host configuration error"""
        self.error(f"❌ Host configuration failed: {host} - {error}")
        self.current_host = None

class LogManager:
    """Global log manager"""
    
    def __init__(self):
        self.websocket_handler: Optional[WebSocketHandler] = None
        self.installation_loggers: Dict[str, InstallationLogger] = {}
        self._setup_root_logger()
    
    def _setup_root_logger(self):
        """Setup root logger configuration"""
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, settings.log_level.value))
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(ColoredFormatter())
        console_handler.setLevel(logging.INFO)
        root_logger.addHandler(console_handler)
        
        # Main log file
        main_log_file = Path(settings.storage.logs_directory) / "app.log"
        file_handler = logging.handlers.RotatingFileHandler(
            main_log_file,
            maxBytes=settings.monitoring.max_log_size_mb * 1024 * 1024,
            backupCount=settings.monitoring.max_log_files
        )
        file_handler.setFormatter(JSONFormatter())
        file_handler.setLevel(logging.DEBUG)
        root_logger.addHandler(file_handler)
        
        # Error log file
        error_log_file = Path(settings.storage.logs_directory) / "error.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=settings.monitoring.max_log_size_mb * 1024 * 1024,
            backupCount=settings.monitoring.max_log_files
        )
        error_handler.setFormatter(JSONFormatter())
        error_handler.setLevel(logging.ERROR)
        root_logger.addHandler(error_handler)
        
        # WebSocket handler if enabled
        if settings.websocket.enabled:
            self.websocket_handler = WebSocketHandler()
            self.websocket_handler.setLevel(logging.INFO)
            root_logger.addHandler(self.websocket_handler)
            self.websocket_handler.start_streaming()
    
    def get_installation_logger(self, installation_id: str, component: str = "installer") -> InstallationLogger:
        """Get or create installation logger"""
        key = f"{component}.{installation_id}"
        
        if key not in self.installation_loggers:
            self.installation_loggers[key] = InstallationLogger(
                installation_id=installation_id,
                component=component,
                websocket_handler=self.websocket_handler
            )
        
        return self.installation_loggers[key]
    
    def cleanup_installation_logger(self, installation_id: str, component: str = "installer"):
        """Cleanup installation logger"""
        key = f"{component}.{installation_id}"
        if key in self.installation_loggers:
            logger = self.installation_loggers[key]
            # Close handlers
            for handler in logger.logger.handlers:
                handler.close()
            del self.installation_loggers[key]
    
    def add_websocket_client(self, websocket):
        """Add WebSocket client for log streaming"""
        if self.websocket_handler:
            self.websocket_handler.add_client(websocket)
    
    def remove_websocket_client(self, websocket):
        """Remove WebSocket client"""
        if self.websocket_handler:
            self.websocket_handler.remove_client(websocket)
    
    def shutdown(self):
        """Shutdown log manager"""
        if self.websocket_handler:
            self.websocket_handler.stop_streaming()
        
        # Cleanup all installation loggers
        for key in list(self.installation_loggers.keys()):
            installation_id = key.split('.')[1]
            component = key.split('.')[0]
            self.cleanup_installation_logger(installation_id, component)

# Global log manager instance
log_manager = LogManager()

def get_logger(name: str) -> logging.Logger:
    """Get logger with proper configuration"""
    return logging.getLogger(name)

def get_installation_logger(installation_id: str, component: str = "installer") -> InstallationLogger:
    """Get installation logger"""
    return log_manager.get_installation_logger(installation_id, component)

# Export main functions and classes
__all__ = [
    'LogLevel', 'LogCategory', 'LogEntry',
    'InstallationLogger', 'LogManager',
    'get_logger', 'get_installation_logger',
    'log_manager'
]
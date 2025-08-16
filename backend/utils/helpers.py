#!/usr/bin/env python3
"""
Utility functions and helpers for K8s Auto Installer
Common functionality used across the application
"""

import os
import sys
import time
import json
import yaml
import hashlib
import secrets
import subprocess
import ipaddress
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple, Callable
from functools import wraps
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# ===============================
# System & Environment Utilities
# ===============================

def is_root() -> bool:
    """Check if running with root privileges"""
    return os.geteuid() == 0

def get_system_info() -> Dict[str, str]:
    """Get system information"""
    info = {}
    
    try:
        # OS Information
        if os.path.exists('/etc/os-release'):
            with open('/etc/os-release', 'r') as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        info[key.lower()] = value.strip('"')
    
        # Python version
        info['python_version'] = sys.version.split()[0]
        
        # Architecture
        info['architecture'] = os.uname().machine
        
        # Kernel version
        info['kernel'] = os.uname().release
        
    except Exception as e:
        logger.warning(f"Could not get full system info: {e}")
    
    return info

def check_command_exists(command: str) -> bool:
    """Check if a command exists in PATH"""
    try:
        subprocess.run(['which', command], 
                      capture_output=True, 
                      check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def run_command(
    command: str, 
    timeout: int = 300, 
    capture_output: bool = True,
    shell: bool = True,
    check: bool = False,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None
) -> Tuple[bool, str, str]:
    """
    Run system command with comprehensive error handling
    
    Args:
        command: Command to execute
        timeout: Command timeout in seconds
        capture_output: Whether to capture stdout/stderr
        shell: Whether to use shell
        check: Whether to raise exception on non-zero exit
        cwd: Working directory
        env: Environment variables
    
    Returns:
        Tuple of (success, stdout, stderr)
    """
    try:
        logger.debug(f"Executing command: {command}")
        
        result = subprocess.run(
            command,
            shell=shell,
            capture_output=capture_output,
            text=True,
            timeout=timeout,
            check=check,
            cwd=cwd,
            env=env
        )
        
        success = result.returncode == 0
        stdout = result.stdout.strip() if result.stdout else ""
        stderr = result.stderr.strip() if result.stderr else ""
        
        if success:
            logger.debug(f"Command succeeded: {command}")
        else:
            logger.error(f"Command failed (exit {result.returncode}): {command}")
            if stderr:
                logger.error(f"Error output: {stderr}")
        
        return success, stdout, stderr
        
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout}s: {command}")
        return False, "", f"Command timed out after {timeout} seconds"
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with exit code {e.returncode}: {command}")
        return False, e.stdout or "", e.stderr or ""
        
    except Exception as e:
        logger.error(f"Unexpected error running command '{command}': {e}")
        return False, "", str(e)

# ===============================
# Network & Validation Utilities
# ===============================

def validate_ip_address(ip: str) -> bool:
    """Validate IP address format"""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def validate_cidr(cidr: str) -> bool:
    """Validate CIDR notation"""
    try:
        ipaddress.ip_network(cidr, strict=False)
        return True
    except ValueError:
        return False

def validate_port(port: Union[str, int]) -> bool:
    """Validate port number"""
    try:
        port_num = int(port)
        return 1 <= port_num <= 65535
    except (ValueError, TypeError):
        return False

def validate_hostname(hostname: str) -> bool:
    """Validate hostname format"""
    if len(hostname) > 255:
        return False
    
    # Remove trailing dot
    if hostname.endswith('.'):
        hostname = hostname[:-1]
    
    # Check each label
    allowed = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$')
    return all(allowed.match(label) for label in hostname.split('.'))

def is_port_open(host: str, port: int, timeout: int = 5) -> bool:
    """Check if port is open on host"""
    import socket
    
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, socket.error):
        return False

def ping_host(host: str, count: int = 3, timeout: int = 5) -> bool:
    """Ping host to check connectivity"""
    success, _, _ = run_command(
        f"ping -c {count} -W {timeout} {host}",
        timeout=timeout + 5
    )
    return success

# ===============================
# File & Configuration Utilities
# ===============================

def ensure_directory(path: Union[str, Path], mode: int = 0o755) -> bool:
    """Ensure directory exists with proper permissions"""
    try:
        Path(path).mkdir(parents=True, exist_ok=True, mode=mode)
        return True
    except Exception as e:
        logger.error(f"Failed to create directory {path}: {e}")
        return False

def read_file(file_path: Union[str, Path], encoding: str = 'utf-8') -> Optional[str]:
    """Read file content safely"""
    try:
        with open(file_path, 'r', encoding=encoding) as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to read file {file_path}: {e}")
        return None

def write_file(
    file_path: Union[str, Path], 
    content: str, 
    encoding: str = 'utf-8',
    mode: int = 0o644
) -> bool:
    """Write file content safely"""
    try:
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding=encoding) as f:
            f.write(content)
        
        os.chmod(file_path, mode)
        return True
    except Exception as e:
        logger.error(f"Failed to write file {file_path}: {e}")
        return False

def load_yaml(file_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
    """Load YAML file safely"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load YAML {file_path}: {e}")
        return None

def save_yaml(
    data: Dict[str, Any], 
    file_path: Union[str, Path],
    mode: int = 0o644
) -> bool:
    """Save data as YAML file"""
    try:
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, indent=2)
        
        os.chmod(file_path, mode)
        return True
    except Exception as e:
        logger.error(f"Failed to save YAML {file_path}: {e}")
        return False

def load_json(file_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
    """Load JSON file safely"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load JSON {file_path}: {e}")
        return None

def save_json(
    data: Dict[str, Any], 
    file_path: Union[str, Path],
    indent: int = 2,
    mode: int = 0o644
) -> bool:
    """Save data as JSON file"""
    try:
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        
        os.chmod(file_path, mode)
        return True
    except Exception as e:
        logger.error(f"Failed to save JSON {file_path}: {e}")
        return False

# ===============================
# String & Data Utilities
# ===============================

def generate_random_string(length: int = 16, use_symbols: bool = False) -> str:
    """Generate random string for secrets, tokens, etc."""
    import string
    
    chars = string.ascii_letters + string.digits
    if use_symbols:
        chars += "!@#$%^&*"
    
    return ''.join(secrets.choice(chars) for _ in range(length))

def hash_string(text: str, algorithm: str = 'sha256') -> str:
    """Hash string using specified algorithm"""
    hash_obj = hashlib.new(algorithm)
    hash_obj.update(text.encode('utf-8'))
    return hash_obj.hexdigest()

def slugify(text: str) -> str:
    """Convert string to URL-safe slug"""
    # Convert to lowercase and replace spaces/special chars with hyphens
    slug = re.sub(r'[^\w\s-]', '', text.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')

def format_bytes(bytes_value: int) -> str:
    """Format bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"

def format_duration(seconds: float) -> str:
    """Format duration in seconds to human readable format"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"

def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate string to maximum length"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix

# ===============================
# Kubernetes Utilities
# ===============================

def validate_k8s_name(name: str) -> bool:
    """Validate Kubernetes resource name"""
    # DNS-1123 subdomain format
    if not name or len(name) > 63:
        return False
    
    pattern = re.compile(r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$')
    return pattern.match(name) is not None

def validate_k8s_version(version: str) -> bool:
    """Validate Kubernetes version format"""
    pattern = re.compile(r'^\d+\.\d+(\.\d+)?$')
    return pattern.match(version) is not None

def parse_k8s_version(version: str) -> Optional[Tuple[int, int, int]]:
    """Parse Kubernetes version string to tuple"""
    try:
        parts = version.split('.')
        major = int(parts[0])
        minor = int(parts[1])
        patch = int(parts[2]) if len(parts) > 2 else 0
        return (major, minor, patch)
    except (ValueError, IndexError):
        return None

def compare_k8s_versions(version1: str, version2: str) -> int:
    """
    Compare Kubernetes versions
    Returns: -1 if version1 < version2, 0 if equal, 1 if version1 > version2
    """
    v1 = parse_k8s_version(version1)
    v2 = parse_k8s_version(version2)
    
    if v1 is None or v2 is None:
        raise ValueError("Invalid version format")
    
    if v1 < v2:
        return -1
    elif v1 > v2:
        return 1
    else:
        return 0

# ===============================
# Decorators & Context Managers
# ===============================

def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Retry decorator with exponential backoff
    
    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay between attempts
        backoff: Backoff multiplier
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt == max_attempts - 1:
                        logger.error(f"Function {func.__name__} failed after {max_attempts} attempts")
                        raise last_exception
                    
                    logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}")
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            # This should never be reached, but just in case
            raise last_exception
        
        return wrapper
    return decorator

def timeout(seconds: int):
    """Timeout decorator for functions"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError(f"Function {func.__name__} timed out after {seconds} seconds")
            
            # Set up signal handler
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(seconds)
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                # Restore old handler and cancel alarm
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
        
        return wrapper
    return decorator

class temp_directory:
    """Context manager for temporary directory"""
    
    def __init__(self, prefix: str = "k8s-installer-", cleanup: bool = True):
        self.prefix = prefix
        self.cleanup = cleanup
        self.path = None
    
    def __enter__(self) -> Path:
        import tempfile
        self.path = Path(tempfile.mkdtemp(prefix=self.prefix))
        return self.path
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cleanup and self.path and self.path.exists():
            import shutil
            try:
                shutil.rmtree(self.path)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp directory {self.path}: {e}")

# ===============================
# Time & Date Utilities
# ===============================

def get_timestamp() -> str:
    """Get current timestamp in ISO format"""
    return datetime.now().isoformat()

def get_unix_timestamp() -> int:
    """Get current Unix timestamp"""
    return int(time.time())

def format_timestamp(timestamp: Union[int, float, datetime], format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format timestamp to string"""
    if isinstance(timestamp, (int, float)):
        dt = datetime.fromtimestamp(timestamp)
    else:
        dt = timestamp
    
    return dt.strftime(format_str)

def parse_timestamp(timestamp_str: str, format_str: str = "%Y-%m-%d %H:%M:%S") -> datetime:
    """Parse timestamp string to datetime"""
    return datetime.strptime(timestamp_str, format_str)

# ===============================
# Error Handling Utilities
# ===============================

class K8sInstallerError(Exception):
    """Base exception for K8s installer"""
    pass

class ConfigurationError(K8sInstallerError):
    """Configuration related errors"""
    pass

class ValidationError(K8sInstallerError):
    """Validation related errors"""
    pass

class SSHError(K8sInstallerError):
    """SSH related errors"""
    pass

class InstallationError(K8sInstallerError):
    """Installation related errors"""
    pass

def safe_execute(func: Callable, *args, **kwargs) -> Tuple[bool, Any, Optional[Exception]]:
    """
    Safely execute function and return success status, result, and exception
    
    Returns:
        Tuple of (success, result, exception)
    """
    try:
        result = func(*args, **kwargs)
        return True, result, None
    except Exception as e:
        logger.error(f"Function {func.__name__} failed: {e}")
        return False, None, e

# ===============================
# Logging Utilities
# ===============================

def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    format_string: Optional[str] = None
) -> logging.Logger:
    """Setup logging configuration"""
    
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Create formatter
    formatter = logging.Formatter(format_string)
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        ensure_directory(Path(log_file).parent)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    return root_logger

class LogContext:
    """Context manager for adding context to logs"""
    
    def __init__(self, logger: logging.Logger, context: str):
        self.logger = logger
        self.context = context
        self.old_name = logger.name
    
    def __enter__(self):
        self.logger.name = f"{self.old_name}[{self.context}]"
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.name = self.old_name

# ===============================
# Performance Monitoring
# ===============================

import functools
from contextlib import contextmanager

def measure_time(func: Callable) -> Callable:
    """Decorator to measure function execution time"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.debug(f"Function {func.__name__} took {execution_time:.2f} seconds")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Function {func.__name__} failed after {execution_time:.2f} seconds: {e}")
            raise
    return wrapper

@contextmanager
def timer(description: str = "Operation"):
    """Context manager for timing operations"""
    start_time = time.time()
    try:
        yield
    finally:
        execution_time = time.time() - start_time
        logger.info(f"{description} took {format_duration(execution_time)}")

def profile_memory(func: Callable) -> Callable:
    """Decorator to profile memory usage (requires psutil)"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            memory_before = process.memory_info().rss
            
            result = func(*args, **kwargs)
            
            memory_after = process.memory_info().rss
            memory_diff = memory_after - memory_before
            
            logger.debug(f"Function {func.__name__} used {format_bytes(memory_diff)} memory")
            return result
            
        except ImportError:
            logger.warning("psutil not available, memory profiling disabled")
            return func(*args, **kwargs)
    
    return wrapper

# ===============================
# Data Structures & Collections
# ===============================

class ThreadSafeDict:
    """Thread-safe dictionary implementation"""
    
    def __init__(self):
        self._dict = {}
        self._lock = threading.Lock()
    
    def __getitem__(self, key):
        with self._lock:
            return self._dict[key]
    
    def __setitem__(self, key, value):
        with self._lock:
            self._dict[key] = value
    
    def __delitem__(self, key):
        with self._lock:
            del self._dict[key]
    
    def __contains__(self, key):
        with self._lock:
            return key in self._dict
    
    def get(self, key, default=None):
        with self._lock:
            return self._dict.get(key, default)
    
    def keys(self):
        with self._lock:
            return list(self._dict.keys())
    
    def values(self):
        with self._lock:
            return list(self._dict.values())
    
    def items(self):
        with self._lock:
            return list(self._dict.items())
    
    def clear(self):
        with self._lock:
            self._dict.clear()

class LRUCache:
    """Simple LRU Cache implementation"""
    
    def __init__(self, max_size: int = 100):
        from collections import OrderedDict
        self.max_size = max_size
        self.cache = OrderedDict()
    
    def get(self, key: str) -> Any:
        if key in self.cache:
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            return self.cache[key]
        return None
    
    def set(self, key: str, value: Any) -> None:
        if key in self.cache:
            # Update existing key
            self.cache.move_to_end(key)
        else:
            # Add new key
            if len(self.cache) >= self.max_size:
                # Remove least recently used
                self.cache.popitem(last=False)
        
        self.cache[key] = value
    
    def clear(self) -> None:
        self.cache.clear()
    
    def size(self) -> int:
        return len(self.cache)

# ===============================
# Export all utilities
# ===============================

__all__ = [
    # System utilities
    'is_root', 'get_system_info', 'check_command_exists', 'run_command',
    
    # Network utilities
    'validate_ip_address', 'validate_cidr', 'validate_port', 'validate_hostname',
    'is_port_open', 'ping_host',
    
    # File utilities
    'ensure_directory', 'read_file', 'write_file', 'load_yaml', 'save_yaml',
    'load_json', 'save_json',
    
    # String utilities
    'generate_random_string', 'hash_string', 'slugify', 'format_bytes',
    'format_duration', 'truncate_string',
    
    # Kubernetes utilities
    'validate_k8s_name', 'validate_k8s_version', 'parse_k8s_version',
    'compare_k8s_versions',
    
    # Decorators
    'retry', 'timeout', 'measure_time', 'profile_memory',
    
    # Context managers
    'temp_directory', 'timer', 'LogContext',
    
    # Error handling
    'safe_execute', 'K8sInstallerError', 'ConfigurationError', 'ValidationError',
    'SSHError', 'InstallationError',
    
    # Logging
    'setup_logging',
    
    # Time utilities
    'get_timestamp', 'get_unix_timestamp', 'format_timestamp', 'parse_timestamp',
    
    # Data structures
    'ThreadSafeDict', 'LRUCache'
]
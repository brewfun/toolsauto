#!/usr/bin/env python3
"""
SSH Manager for K8s Auto Installer
Handles SSH connections, command execution, and file transfers
"""

import os
import time
import threading
import paramiko
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any
from dataclasses import dataclass
from enum import Enum
import socket
import logging

from ..config.settings import settings
from ..utils.helpers import (
    validate_ip_address, validate_hostname, retry, 
    K8sInstallerError, safe_execute, format_duration
)
from ..utils.logger import get_logger

logger = get_logger(__name__)

class SSHAuthMethod(Enum):
    """SSH authentication methods"""
    PASSWORD = "password"
    KEY = "key"
    AGENT = "agent"

class ConnectionStatus(Enum):
    """SSH connection status"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"

@dataclass
class SSHConfig:
    """SSH connection configuration"""
    host: str
    port: int = 22
    username: str = "ubuntu"
    password: Optional[str] = None
    key_path: Optional[str] = None
    key_passphrase: Optional[str] = None
    auth_method: SSHAuthMethod = SSHAuthMethod.KEY
    
    # Connection settings
    timeout: int = 30
    keepalive: int = 60
    compression: bool = True
    
    # Security settings
    allow_host_key_policy: bool = True  # For development, set False in production
    
    def validate(self) -> List[str]:
        """Validate SSH configuration"""
        errors = []
        
        # Validate host
        if not self.host:
            errors.append("Host is required")
        elif not (validate_ip_address(self.host) or validate_hostname(self.host)):
            errors.append(f"Invalid host format: {self.host}")
        
        # Validate port
        if not (1 <= self.port <= 65535):
            errors.append(f"Invalid port: {self.port}")
        
        # Validate username
        if not self.username:
            errors.append("Username is required")
        
        # Validate authentication
        if self.auth_method == SSHAuthMethod.PASSWORD and not self.password:
            errors.append("Password required for password authentication")
        
        if self.auth_method == SSHAuthMethod.KEY:
            if not self.key_path:
                errors.append("Key path required for key authentication")
            elif not os.path.exists(self.key_path):
                errors.append(f"SSH key file not found: {self.key_path}")
            elif not os.access(self.key_path, os.R_OK):
                errors.append(f"SSH key file not readable: {self.key_path}")
        
        return errors

@dataclass
class CommandResult:
    """SSH command execution result"""
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration: float
    command: str
    host: str
    
    def __str__(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        return f"[{self.host}] {status} ({self.exit_code}): {self.command}"

class SSHConnection:
    """Individual SSH connection wrapper"""
    
    def __init__(self, config: SSHConfig):
        self.config = config
        self.client: Optional[paramiko.SSHClient] = None
        self.sftp: Optional[paramiko.SFTPClient] = None
        self.status = ConnectionStatus.DISCONNECTED
        self.last_activity = time.time()
        self.lock = threading.Lock()
        
        # Connection statistics
        self.connect_time: Optional[float] = None
        self.commands_executed = 0
        self.bytes_transferred = 0
        self.last_error: Optional[str] = None
    
    def connect(self) -> bool:
        """Establish SSH connection"""
        with self.lock:
            if self.status == ConnectionStatus.CONNECTED:
                return True
            
            try:
                self.status = ConnectionStatus.CONNECTING
                logger.debug(f"Connecting to {self.config.host}:{self.config.port}")
                
                # Create SSH client
                self.client = paramiko.SSHClient()
                
                # Set host key policy
                if self.config.allow_host_key_policy:
                    self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                else:
                    self.client.set_missing_host_key_policy(paramiko.RejectPolicy())
                
                # Connect based on authentication method
                connect_kwargs = {
                    'hostname': self.config.host,
                    'port': self.config.port,
                    'username': self.config.username,
                    'timeout': self.config.timeout,
                    'compress': self.config.compression,
                }
                
                if self.config.auth_method == SSHAuthMethod.PASSWORD:
                    connect_kwargs['password'] = self.config.password
                elif self.config.auth_method == SSHAuthMethod.KEY:
                    connect_kwargs['key_filename'] = self.config.key_path
                    if self.config.key_passphrase:
                        connect_kwargs['passphrase'] = self.config.key_passphrase
                elif self.config.auth_method == SSHAuthMethod.AGENT:
                    connect_kwargs['allow_agent'] = True
                
                self.client.connect(**connect_kwargs)
                
                # Setup keepalive
                if self.config.keepalive > 0:
                    transport = self.client.get_transport()
                    transport.set_keepalive(self.config.keepalive)
                
                self.status = ConnectionStatus.CONNECTED
                self.connect_time = time.time()
                self.last_activity = time.time()
                self.last_error = None
                
                logger.info(f"✅ Connected to {self.config.host}")
                return True
                
            except Exception as e:
                self.status = ConnectionStatus.ERROR
                self.last_error = str(e)
                logger.error(f"❌ Failed to connect to {self.config.host}: {e}")
                
                # Cleanup on failure
                if self.client:
                    try:
                        self.client.close()
                    except:
                        pass
                    self.client = None
                
                return False
    
    def disconnect(self):
        """Close SSH connection"""
        with self.lock:
            if self.status == ConnectionStatus.DISCONNECTED:
                return
            
            try:
                if self.sftp:
                    self.sftp.close()
                    self.sftp = None
                
                if self.client:
                    self.client.close()
                    self.client = None
                
                self.status = ConnectionStatus.DISCONNECTED
                logger.debug(f"Disconnected from {self.config.host}")
                
            except Exception as e:
                logger.warning(f"Error during disconnect from {self.config.host}: {e}")
    
    def is_connected(self) -> bool:
        """Check if connection is active"""
        if self.status != ConnectionStatus.CONNECTED or not self.client:
            return False
        
        try:
            transport = self.client.get_transport()
            return transport and transport.is_active()
        except:
            return False
    
    def execute_command(
        self, 
        command: str, 
        timeout: int = 300,
        get_pty: bool = False,
        environment: Optional[Dict[str, str]] = None
    ) -> CommandResult:
        """Execute command on remote host"""
        start_time = time.time()
        
        if not self.is_connected():
            if not self.connect():
                return CommandResult(
                    success=False,
                    exit_code=-1,
                    stdout="",
                    stderr=f"Failed to connect to {self.config.host}",
                    duration=time.time() - start_time,
                    command=command,
                    host=self.config.host
                )
        
        try:
            logger.debug(f"[{self.config.host}] Executing: {command}")
            
            # Execute command
            stdin, stdout, stderr = self.client.exec_command(
                command,
                timeout=timeout,
                get_pty=get_pty,
                environment=environment
            )
            
            # Read output
            stdout_data = stdout.read().decode('utf-8', errors='replace')
            stderr_data = stderr.read().decode('utf-8', errors='replace')
            exit_code = stdout.channel.recv_exit_status()
            
            # Update statistics
            self.commands_executed += 1
            self.last_activity = time.time()
            
            duration = time.time() - start_time
            success = exit_code == 0
            
            result = CommandResult(
                success=success,
                exit_code=exit_code,
                stdout=stdout_data.strip(),
                stderr=stderr_data.strip(),
                duration=duration,
                command=command,
                host=self.config.host
            )
            
            if success:
                logger.debug(f"[{self.config.host}] ✅ Command succeeded ({duration:.2f}s)")
            else:
                logger.error(f"[{self.config.host}] ❌ Command failed ({duration:.2f}s): {command}")
                if stderr_data:
                    logger.error(f"[{self.config.host}] Error: {stderr_data.strip()}")
            
            return result
            
        except socket.timeout:
            logger.error(f"[{self.config.host}] Command timed out: {command}")
            return CommandResult(
                success=False,
                exit_code=-2,
                stdout="",
                stderr=f"Command timed out after {timeout} seconds",
                duration=time.time() - start_time,
                command=command,
                host=self.config.host
            )
            
        except Exception as e:
            logger.error(f"[{self.config.host}] Command execution error: {e}")
            return CommandResult(
                success=False,
                exit_code=-3,
                stdout="",
                stderr=str(e),
                duration=time.time() - start_time,
                command=command,
                host=self.config.host
            )
    
    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Upload file to remote host"""
        if not self.is_connected():
            if not self.connect():
                return False
        
        try:
            if not self.sftp:
                self.sftp = self.client.open_sftp()
            
            logger.debug(f"[{self.config.host}] Uploading {local_path} -> {remote_path}")
            
            # Ensure remote directory exists
            remote_dir = os.path.dirname(remote_path)
            if remote_dir:
                try:
                    self.sftp.makedirs(remote_dir)
                except:
                    pass  # Directory might already exist
            
            self.sftp.put(local_path, remote_path)
            
            # Update statistics
            file_size = os.path.getsize(local_path)
            self.bytes_transferred += file_size
            self.last_activity = time.time()
            
            logger.debug(f"[{self.config.host}] ✅ File uploaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"[{self.config.host}] File upload failed: {e}")
            return False
    
    def download_file(self, remote_path: str, local_path: str) -> bool:
        """Download file from remote host"""
        if not self.is_connected():
            if not self.connect():
                return False
        
        try:
            if not self.sftp:
                self.sftp = self.client.open_sftp()
            
            logger.debug(f"[{self.config.host}] Downloading {remote_path} -> {local_path}")
            
            # Ensure local directory exists
            local_dir = os.path.dirname(local_path)
            if local_dir:
                os.makedirs(local_dir, exist_ok=True)
            
            self.sftp.get(remote_path, local_path)
            
            # Update statistics
            file_size = os.path.getsize(local_path)
            self.bytes_transferred += file_size
            self.last_activity = time.time()
            
            logger.debug(f"[{self.config.host}] ✅ File downloaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"[{self.config.host}] File download failed: {e}")
            return False
    
    def file_exists(self, remote_path: str) -> bool:
        """Check if file exists on remote host"""
        if not self.is_connected():
            if not self.connect():
                return False
        
        try:
            if not self.sftp:
                self.sftp = self.client.open_sftp()
            
            self.sftp.stat(remote_path)
            return True
            
        except FileNotFoundError:
            return False
        except Exception:
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        return {
            'host': self.config.host,
            'status': self.status.value,
            'connected_since': self.connect_time,
            'last_activity': self.last_activity,
            'commands_executed': self.commands_executed,
            'bytes_transferred': self.bytes_transferred,
            'last_error': self.last_error
        }

class SSHManager:
    """SSH connection manager with pooling and retry logic"""
    
    def __init__(self):
        self.connections: Dict[str, SSHConnection] = {}
        self.connection_configs: Dict[str, SSHConfig] = {}
        self.lock = threading.Lock()
        
        # Connection limits
        self.max_connections = settings.ssh.max_connections
        self.cleanup_interval = 300  # 5 minutes
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self.cleanup_thread.start()
    
    def add_host(self, host: str, config: SSHConfig) -> bool:
        """Add host configuration"""
        errors = config.validate()
        if errors:
            logger.error(f"Invalid SSH config for {host}: {'; '.join(errors)}")
            return False
        
        with self.lock:
            self.connection_configs[host] = config
            logger.info(f"Added SSH config for {host}")
            return True
    
    def remove_host(self, host: str):
        """Remove host and close connection"""
        with self.lock:
            if host in self.connections:
                self.connections[host].disconnect()
                del self.connections[host]
            
            if host in self.connection_configs:
                del self.connection_configs[host]
            
            logger.info(f"Removed SSH config for {host}")
    
    def get_connection(self, host: str) -> Optional[SSHConnection]:
        """Get or create SSH connection for host"""
        with self.lock:
            if host not in self.connection_configs:
                logger.error(f"No SSH config found for host: {host}")
                return None
            
            # Check existing connection
            if host in self.connections:
                connection = self.connections[host]
                if connection.is_connected():
                    return connection
                else:
                    # Remove stale connection
                    connection.disconnect()
                    del self.connections[host]
            
            # Check connection limit
            if len(self.connections) >= self.max_connections:
                logger.warning("Maximum SSH connections reached")
                self._cleanup_stale_connections()
                
                if len(self.connections) >= self.max_connections:
                    logger.error("Cannot create new connection: limit reached")
                    return None
            
            # Create new connection
            config = self.connection_configs[host]
            connection = SSHConnection(config)
            
            if connection.connect():
                self.connections[host] = connection
                return connection
            else:
                return None
    
    @retry(max_attempts=3, delay=2.0)
    def execute_command(
        self, 
        host: str, 
        command: str, 
        timeout: int = 300,
        get_pty: bool = False,
        environment: Optional[Dict[str, str]] = None
    ) -> CommandResult:
        """Execute command on remote host with retry logic"""
        connection = self.get_connection(host)
        if not connection:
            return CommandResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=f"Failed to establish connection to {host}",
                duration=0,
                command=command,
                host=host
            )
        
        return connection.execute_command(command, timeout, get_pty, environment)
    
    def execute_parallel(
        self,
        hosts: List[str],
        command: str,
        timeout: int = 300,
        max_workers: int = 10
    ) -> Dict[str, CommandResult]:
        """Execute command on multiple hosts in parallel"""
        import concurrent.futures
        
        results = {}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit tasks
            future_to_host = {
                executor.submit(self.execute_command, host, command, timeout): host
                for host in hosts
            }
            
            # Collect results
            for future in concurrent.futures.as_completed(future_to_host):
                host = future_to_host[future]
                try:
                    results[host] = future.result()
                except Exception as e:
                    logger.error(f"Parallel execution failed for {host}: {e}")
                    results[host] = CommandResult(
                        success=False,
                        exit_code=-1,
                        stdout="",
                        stderr=str(e),
                        duration=0,
                        command=command,
                        host=host
                    )
        
        return results
    
    def upload_file(self, host: str, local_path: str, remote_path: str) -> bool:
        """Upload file to remote host"""
        connection = self.get_connection(host)
        if not connection:
            return False
        
        return connection.upload_file(local_path, remote_path)
    
    def download_file(self, host: str, remote_path: str, local_path: str) -> bool:
        """Download file from remote host"""
        connection = self.get_connection(host)
        if not connection:
            return False
        
        return connection.download_file(remote_path, local_path)
    
    def file_exists(self, host: str, remote_path: str) -> bool:
        """Check if file exists on remote host"""
        connection = self.get_connection(host)
        if not connection:
            return False
        
        return connection.file_exists(remote_path)
    
    def test_connectivity(self, host: str, timeout: int = 10) -> bool:
        """Test SSH connectivity to host"""
        try:
            result = self.execute_command(host, "echo 'connectivity_test'", timeout=timeout)
            return result.success and "connectivity_test" in result.stdout
        except Exception as e:
            logger.error(f"Connectivity test failed for {host}: {e}")
            return False
    
    def get_system_info(self, host: str) -> Dict[str, str]:
        """Get system information from remote host"""
        commands = {
            'hostname': 'hostname',
            'os': 'cat /etc/os-release | grep "^ID=" | cut -d= -f2 | tr -d \'"\'',
            'kernel': 'uname -r',
            'arch': 'uname -m',
            'memory': 'free -h | grep "^Mem:" | awk \'{print $2}\'',
            'cpu_cores': 'nproc',
            'uptime': 'uptime -p',
        }
        
        info = {}
        for key, command in commands.items():
            result = self.execute_command(host, command, timeout=10)
            if result.success:
                info[key] = result.stdout
            else:
                info[key] = "unknown"
        
        return info
    
    def _cleanup_stale_connections(self):
        """Clean up stale connections"""
        stale_hosts = []
        current_time = time.time()
        
        for host, connection in self.connections.items():
            # Check if connection is stale
            time_since_activity = current_time - connection.last_activity
            if (not connection.is_connected() or 
                time_since_activity > self.cleanup_interval * 2):
                stale_hosts.append(host)
        
        for host in stale_hosts:
            logger.debug(f"Cleaning up stale connection to {host}")
            self.connections[host].disconnect()
            del self.connections[host]
    
    def _cleanup_worker(self):
        """Background worker for connection cleanup"""
        while True:
            try:
                time.sleep(self.cleanup_interval)
                with self.lock:
                    self._cleanup_stale_connections()
            except Exception as e:
                logger.error(f"Error in cleanup worker: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get SSH manager statistics"""
        with self.lock:
            connection_stats = [
                conn.get_stats() for conn in self.connections.values()
            ]
            
            return {
                'total_connections': len(self.connections),
                'max_connections': self.max_connections,
                'configured_hosts': len(self.connection_configs),
                'connections': connection_stats
            }
    
    def close_all(self):
        """Close all SSH connections"""
        with self.lock:
            for connection in self.connections.values():
                connection.disconnect()
            
            self.connections.clear()
            logger.info("All SSH connections closed")

# Global SSH manager instance
ssh_manager = SSHManager()

__all__ = [
    'SSHAuthMethod', 'ConnectionStatus', 'SSHConfig', 'CommandResult',
    'SSHConnection', 'SSHManager', 'ssh_manager'
]
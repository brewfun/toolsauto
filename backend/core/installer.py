#!/usr/bin/env python3
"""
Base Installer for K8s Auto Installer
Provides foundation for All-in-One and HA Secure installations
"""

import os
import sys
import time
import uuid
import json
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any, Callable, Union
from enum import Enum
from pathlib import Path
import subprocess

from ..config.settings import settings
from ..utils.helpers import (
    run_command, validate_ip_address, validate_cidr, validate_k8s_version,
    K8sInstallerError, ConfigurationError, InstallationError, safe_execute,
    format_duration, ensure_directory
)
from ..utils.logger import get_installation_logger, InstallationLogger
from .ssh_manager import ssh_manager, SSHConfig, SSHAuthMethod

class InstallationMode(Enum):
    """Installation modes supported"""
    ALL_IN_ONE = "all_in_one"
    HA_SECURE = "ha_secure"

class InstallationStatus(Enum):
    """Installation status states"""
    PENDING = "pending"
    VALIDATING = "validating"
    INSTALLING = "installing"
    CONFIGURING = "configuring"
    VERIFYING = "verifying"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

class CNIProvider(Enum):
    """Container Network Interface providers"""
    CILIUM = "cilium"
    CALICO = "calico"
    FLANNEL = "flannel"

@dataclass
class NodeConfig:
    """Configuration for a Kubernetes node"""
    host: str
    role: str  # master, worker, loadbalancer
    ssh_config: Optional[SSHConfig] = None
    
    def __post_init__(self):
        if not self.ssh_config and self.host != "localhost":
            # Create default SSH config
            self.ssh_config = SSHConfig(
                host=self.host,
                username=settings.ssh.default_user,
                auth_method=SSHAuthMethod.KEY
            )

@dataclass
class InstallationConfig:
    """Configuration for K8s installation"""
    # Basic settings
    installation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    mode: InstallationMode = InstallationMode.ALL_IN_ONE
    
    # Kubernetes configuration
    k8s_version: str = settings.k8s.default_version
    pod_cidr: str = settings.k8s.default_pod_cidr
    service_cidr: str = settings.k8s.default_service_cidr
    cni_provider: CNIProvider = CNIProvider(settings.k8s.default_cni)
    
    # Network configuration
    cluster_name: str = "kubernetes"
    api_server_endpoint: Optional[str] = None
    
    # Node configuration
    nodes: List[NodeConfig] = field(default_factory=list)
    
    # Security settings
    enable_rbac: bool = settings.security.enable_rbac
    enable_network_policies: bool = settings.security.enable_network_policies
    enable_pod_security_policies: bool = settings.security.enable_pod_security_policies
    
    # Advanced options
    container_runtime: str = "containerd"
    enable_monitoring: bool = settings.monitoring.enable_metrics
    backup_etcd: bool = True
    
    # Timeouts and retries
    installation_timeout: int = settings.k8s.installation_timeout
    api_server_timeout: int = settings.k8s.api_server_timeout
    max_retries: int = settings.k8s.max_retries
    
    def validate(self) -> List[str]:
        """Validate configuration and return errors"""
        errors = []
        
        # Validate Kubernetes version
        if not validate_k8s_version(self.k8s_version):
            errors.append(f"Invalid Kubernetes version: {self.k8s_version}")
        elif self.k8s_version not in settings.k8s.supported_versions:
            errors.append(f"Unsupported Kubernetes version: {self.k8s_version}")
        
        # Validate CIDR ranges
        if not validate_cidr(self.pod_cidr):
            errors.append(f"Invalid pod CIDR: {self.pod_cidr}")
        
        if not validate_cidr(self.service_cidr):
            errors.append(f"Invalid service CIDR: {self.service_cidr}")
        
        # Validate nodes
        if not self.nodes:
            errors.append("At least one node is required")
        
        # Mode-specific validation
        if self.mode == InstallationMode.ALL_IN_ONE:
            if len(self.nodes) != 1:
                errors.append("All-in-One mode requires exactly one node")
        
        elif self.mode == InstallationMode.HA_SECURE:
            master_nodes = [n for n in self.nodes if n.role == "master"]
            lb_nodes = [n for n in self.nodes if n.role == "loadbalancer"]
            
            if len(master_nodes) < 3:
                errors.append("HA mode requires at least 3 master nodes")
            
            if len(lb_nodes) != 1:
                errors.append("HA mode requires exactly one load balancer")
        
        # Validate node configurations
        for node in self.nodes:
            if not validate_ip_address(node.host) and node.host != "localhost":
                errors.append(f"Invalid host address: {node.host}")
            
            if node.ssh_config:
                ssh_errors = node.ssh_config.validate()
                errors.extend([f"Node {node.host}: {err}" for err in ssh_errors])
        
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    def save_to_file(self, file_path: str) -> bool:
        """Save configuration to file"""
        try:
            ensure_directory(Path(file_path).parent)
            with open(file_path, 'w') as f:
                json.dump(self.to_dict(), f, indent=2, default=str)
            return True
        except Exception as e:
            return False

@dataclass
class InstallationStep:
    """Represents a single installation step"""
    name: str
    description: str
    function: Callable
    required: bool = True
    timeout: int = 300
    retry_count: int = 0
    max_retries: int = 3
    hosts: Optional[List[str]] = None  # Hosts this step applies to
    
    def __post_init__(self):
        if self.hosts is None:
            self.hosts = []

@dataclass
class StepResult:
    """Result of an installation step"""
    step_name: str
    success: bool
    duration: float
    error_message: Optional[str] = None
    output: Optional[str] = None
    host: Optional[str] = None

@dataclass
class InstallationProgress:
    """Track installation progress"""
    installation_id: str
    current_step: int = 0
    total_steps: int = 0
    status: InstallationStatus = InstallationStatus.PENDING
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    error_message: Optional[str] = None
    step_results: List[StepResult] = field(default_factory=list)
    
    @property
    def progress_percentage(self) -> float:
        if self.total_steps == 0:
            return 0.0
        return (self.current_step / self.total_steps) * 100
    
    @property
    def duration(self) -> Optional[float]:
        if not self.start_time:
            return None
        end = self.end_time or time.time()
        return end - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'installation_id': self.installation_id,
            'current_step': self.current_step,
            'total_steps': self.total_steps,
            'status': self.status.value,
            'progress_percentage': self.progress_percentage,
            'duration': self.duration,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'error_message': self.error_message,
            'step_results': [asdict(result) for result in self.step_results]
        }

class BaseInstaller(ABC):
    """Abstract base class for K8s installers"""
    
    def __init__(self, config: InstallationConfig):
        self.config = config
        self.progress = InstallationProgress(installation_id=config.installation_id)
        self.logger = get_installation_logger(config.installation_id, self.__class__.__name__)
        
        # Installation state
        self.steps: List[InstallationStep] = []
        self.cancelled = False
        self.lock = threading.Lock()
        
        # Kubeconfig path
        self.kubeconfig_path = Path.home() / ".kube" / f"config-{config.installation_id}"
        
        # Setup SSH connections for remote nodes
        self._setup_ssh_connections()
    
    def _setup_ssh_connections(self):
        """Setup SSH connections for remote nodes"""
        for node in self.config.nodes:
            if node.host != "localhost" and node.ssh_config:
                if not ssh_manager.add_host(node.host, node.ssh_config):
                    raise ConfigurationError(f"Failed to setup SSH for host: {node.host}")
    
    @abstractmethod
    def define_installation_steps(self) -> List[InstallationStep]:
        """Define installation steps (implement in subclasses)"""
        pass
    
    def pre_installation_checks(self) -> bool:
        """Pre-installation validation"""
        self.logger.info("🔍 Running pre-installation checks...")
        self.progress.status = InstallationStatus.VALIDATING
        
        try:
            # Validate configuration
            errors = self.config.validate()
            if errors:
                for error in errors:
                    self.logger.error(f"Config error: {error}")
                return False
            
            # Check system requirements
            if not self._check_system_requirements():
                return False
            
            # Test connectivity for remote nodes
            if not self._check_connectivity():
                return False
            
            # Check prerequisites on all nodes
            if not self._check_prerequisites():
                return False
            
            self.logger.info("✅ Pre-installation checks passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Pre-installation checks failed: {e}")
            return False
    
    def _check_system_requirements(self) -> bool:
        """Check system requirements"""
        self.logger.info("  → Checking system requirements...")
        
        # Check if running as root (for localhost installations)
        localhost_nodes = [n for n in self.config.nodes if n.host == "localhost"]
        if localhost_nodes and os.geteuid() != 0:
            self.logger.error("Installation requires root privileges")
            return False
        
        # Check available disk space
        statvfs = os.statvfs("/")
        free_space_gb = (statvfs.f_frsize * statvfs.f_bavail) / (1024**3)
        if free_space_gb < 10:  # Minimum 10GB free space
            self.logger.warning(f"Low disk space: {free_space_gb:.1f}GB available")
        
        return True
    
    def _check_connectivity(self) -> bool:
        """Check connectivity to remote nodes"""
        remote_nodes = [n for n in self.config.nodes if n.host != "localhost"]
        if not remote_nodes:
            return True
        
        self.logger.info(f"  → Testing connectivity to {len(remote_nodes)} remote nodes...")
        
        failed_hosts = []
        for node in remote_nodes:
            if not ssh_manager.test_connectivity(node.host):
                failed_hosts.append(node.host)
        
        if failed_hosts:
            self.logger.error(f"Failed to connect to hosts: {', '.join(failed_hosts)}")
            return False
        
        self.logger.info("  → All nodes are reachable")
        return True
    
    def _check_prerequisites(self) -> bool:
        """Check prerequisites on all nodes"""
        self.logger.info("  → Checking prerequisites on nodes...")
        
        for node in self.config.nodes:
            self.logger.info(f"    → Checking {node.host}...")
            
            if not self._check_node_prerequisites(node):
                return False
        
        return True
    
    def _check_node_prerequisites(self, node: NodeConfig) -> bool:
        """Check prerequisites on a single node"""
        try:
            # Get system information
            if node.host == "localhost":
                # Local checks
                commands = [
                    ("Check OS", "cat /etc/os-release | grep 'ID=' | head -1"),
                    ("Check architecture", "uname -m"),
                    ("Check memory", "free -h"),
                ]
                
                for description, command in commands:
                    success, stdout, stderr = run_command(command)
                    if not success:
                        self.logger.error(f"      ❌ {description} failed: {stderr}")
                        return False
                    
                    self.logger.debug(f"      ✅ {description}: {stdout}")
            
            else:
                # Remote checks via SSH
                system_info = ssh_manager.get_system_info(node.host)
                self.logger.debug(f"      System info: {system_info}")
                
                # Check OS compatibility
                if system_info.get('os', '').lower() not in ['ubuntu', 'debian', 'centos', 'rhel']:
                    self.logger.warning(f"      ⚠️  Untested OS: {system_info.get('os', 'unknown')}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"      ❌ Prerequisites check failed for {node.host}: {e}")
            return False
    
    def execute_step(self, step: InstallationStep) -> bool:
        """Execute a single installation step with retry logic"""
        if self.cancelled:
            return False
        
        step_name = f"[{self.progress.current_step + 1}/{self.progress.total_steps}] {step.name}"
        start_time = time.time()
        
        self.logger.step_start(step.name, step.description)
        
        for attempt in range(step.max_retries + 1):
            if self.cancelled:
                return False
            
            try:
                if attempt > 0:
                    self.logger.warning(f"⚠️  Retry {attempt}/{step.max_retries} for: {step.name}")
                    time.sleep(settings.k8s.retry_delay * attempt)  # Progressive delay
                
                # Execute the step
                success = step.function()
                duration = time.time() - start_time
                
                # Record result
                result = StepResult(
                    step_name=step.name,
                    success=success,
                    duration=duration,
                    error_message=None if success else "Step function returned False"
                )
                
                self.progress.step_results.append(result)
                
                if success:
                    self.logger.step_success(step.name, duration)
                    return True
                else:
                    if attempt < step.max_retries:
                        self.logger.warning(f"❌ Step failed: {step.name}, retrying...")
                    else:
                        self.logger.step_error(step.name, "Step function returned False", duration)
                        return not step.required
                        
            except Exception as e:
                duration = time.time() - start_time
                error_msg = str(e)
                
                # Record result
                result = StepResult(
                    step_name=step.name,
                    success=False,
                    duration=duration,
                    error_message=error_msg
                )
                
                self.progress.step_results.append(result)
                
                if attempt < step.max_retries:
                    self.logger.warning(f"⚠️  Exception in {step.name}: {error_msg}, retrying...")
                else:
                    self.logger.step_error(step.name, error_msg, duration)
                    return not step.required
        
        return False
    
    def execute_command(self, command: str, host: str = "localhost", timeout: int = 300) -> Tuple[bool, str]:
        """Execute command on specified host"""
        start_time = time.time()
        
        try:
            if host == "localhost":
                success, stdout, stderr = run_command(command, timeout=timeout)
                output = stdout if success else stderr
            else:
                result = ssh_manager.execute_command(host, command, timeout=timeout)
                success = result.success
                output = result.stdout if success else result.stderr
            
            duration = time.time() - start_time
            self.logger.command_executed(command, success, output, duration)
            
            return success, output
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.command_executed(command, False, str(e), duration)
            return False, str(e)
    
    def wait_for_condition(
        self,
        condition_func: Callable[[], bool],
        description: str,
        timeout: int = 300,
        check_interval: int = 5
    ) -> bool:
        """Wait for a condition to be met"""
        self.logger.info(f"⏳ Waiting for: {description}")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.cancelled:
                return False
            
            try:
                if condition_func():
                    elapsed = time.time() - start_time
                    self.logger.info(f"✅ Condition met: {description} (after {elapsed:.1f}s)")
                    return True
            except Exception as e:
                self.logger.debug(f"Condition check failed: {e}")
            
            remaining = timeout - (time.time() - start_time)
            self.logger.debug(f"  → Still waiting... ({remaining:.0f}s remaining)")
            time.sleep(check_interval)
        
        self.logger.error(f"❌ Timeout waiting for: {description} ({timeout}s)")
        return False
    
    def install(self) -> bool:
        """Main installation process"""
        with self.lock:
            if self.progress.status != InstallationStatus.PENDING:
                raise InstallationError("Installation already started")
        
        self.logger.info(f"🎯 Starting {self.config.mode.value} K8s installation")
        self.logger.info(f"📋 Installation ID: {self.config.installation_id}")
        
        try:
            # Initialize progress
            self.progress.status = InstallationStatus.INSTALLING
            self.progress.start_time = time.time()
            self.steps = self.define_installation_steps()
            self.progress.total_steps = len(self.steps)
            
            # Save configuration
            config_file = Path(settings.storage.logs_directory) / f"config_{self.config.installation_id}.json"
            self.config.save_to_file(str(config_file))
            
            # Pre-installation checks
            if not self.pre_installation_checks():
                self.progress.status = InstallationStatus.FAILED
                self.progress.error_message = "Pre-installation checks failed"
                return False
            
            # Execute installation steps
            self.progress.status = InstallationStatus.INSTALLING
            for i, step in enumerate(self.steps):
                self.progress.current_step = i
                
                if self.cancelled:
                    self.progress.status = InstallationStatus.CANCELLED
                    return False
                
                if not self.execute_step(step):
                    if step.required:
                        self.progress.status = InstallationStatus.FAILED
                        self.progress.error_message = f"Required step failed: {step.name}"
                        return False
                    else:
                        self.logger.warning(f"⚠️  Optional step failed: {step.name}")
            
            # Post-installation verification
            self.progress.status = InstallationStatus.VERIFYING
            self.progress.current_step = len(self.steps)
            
            if not self.post_installation_verification():
                self.progress.status = InstallationStatus.FAILED
                self.progress.error_message = "Post-installation verification failed"
                return False
            
            # Success
            self.progress.status = InstallationStatus.SUCCESS
            self.progress.end_time = time.time()
            
            self.logger.info(f"🎉 Installation completed successfully!")
            self.logger.info(f"⏱️  Total duration: {format_duration(self.progress.duration)}")
            self.logger.info(f"📁 Kubeconfig: {self.kubeconfig_path}")
            
            return True
            
        except KeyboardInterrupt:
            self.progress.status = InstallationStatus.CANCELLED
            self.logger.warning("❌ Installation cancelled by user")
            return False
            
        except Exception as e:
            self.progress.status = InstallationStatus.FAILED
            self.progress.error_message = str(e)
            self.logger.error(f"❌ Unexpected error: {e}")
            return False
            
        finally:
            self.progress.end_time = time.time()
            self._cleanup()
    
    def post_installation_verification(self) -> bool:
        """Post-installation verification steps"""
        self.logger.info("🔍 Running post-installation verification...")
        
        try:
            # Verify cluster is accessible
            if not self._verify_cluster_access():
                return False
            
            # Verify nodes are ready
            if not self._verify_nodes_ready():
                return False
            
            # Verify system pods are running
            if not self._verify_system_pods():
                return False
            
            # Verify CNI is working
            if not self._verify_cni():
                return False
            
            self.logger.info("✅ Post-installation verification passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Post-installation verification failed: {e}")
            return False
    
    def _verify_cluster_access(self) -> bool:
        """Verify cluster is accessible"""
        self.logger.info("  → Verifying cluster access...")
        
        success, output = self.execute_command(
            f"kubectl --kubeconfig={self.kubeconfig_path} cluster-info",
            timeout=30
        )
        
        if not success:
            self.logger.error("  ❌ Cannot access cluster")
            return False
        
        self.logger.info("  ✅ Cluster is accessible")
        return True
    
    def _verify_nodes_ready(self) -> bool:
        """Verify all nodes are ready"""
        self.logger.info("  → Verifying nodes are ready...")
        
        def check_nodes():
            success, output = self.execute_command(
                f"kubectl --kubeconfig={self.kubeconfig_path} get nodes --no-headers",
                timeout=30
            )
            
            if not success:
                return False
            
            for line in output.strip().split('\n'):
                if line and 'NotReady' in line:
                    return False
            
            return True
        
        if not self.wait_for_condition(check_nodes, "nodes to be ready", timeout=300):
            return False
        
        self.logger.info("  ✅ All nodes are ready")
        return True
    
    def _verify_system_pods(self) -> bool:
        """Verify system pods are running"""
        self.logger.info("  → Verifying system pods...")
        
        def check_system_pods():
            success, output = self.execute_command(
                f"kubectl --kubeconfig={self.kubeconfig_path} get pods -n kube-system --no-headers",
                timeout=30
            )
            
            if not success:
                return False
            
            for line in output.strip().split('\n'):
                if line and not any(status in line for status in ['Running', 'Completed']):
                    return False
            
            return True
        
        if not self.wait_for_condition(check_system_pods, "system pods to be running", timeout=600):
            return False
        
        self.logger.info("  ✅ System pods are running")
        return True
    
    def _verify_cni(self) -> bool:
        """Verify CNI is working"""
        self.logger.info(f"  → Verifying {self.config.cni_provider.value} CNI...")
        
        # CNI-specific verification logic would go here
        # For now, just check if CNI pods are running
        
        cni_namespace = "kube-system"
        if self.config.cni_provider == CNIProvider.CILIUM:
            pod_selector = "k8s-app=cilium"
        elif self.config.cni_provider == CNIProvider.CALICO:
            pod_selector = "k8s-app=calico-node"
        else:
            pod_selector = "app=flannel"
        
        def check_cni_pods():
            success, output = self.execute_command(
                f"kubectl --kubeconfig={self.kubeconfig_path} get pods -n {cni_namespace} -l {pod_selector} --no-headers",
                timeout=30
            )
            
            if not success:
                return False
            
            lines = output.strip().split('\n')
            if not lines or not lines[0]:
                return False
            
            for line in lines:
                if line and 'Running' not in line:
                    return False
            
            return True
        
        if not self.wait_for_condition(check_cni_pods, f"{self.config.cni_provider.value} pods to be running", timeout=300):
            return False
        
        self.logger.info(f"  ✅ {self.config.cni_provider.value} CNI is working")
        return True
    
    def cancel(self):
        """Cancel installation"""
        with self.lock:
            self.cancelled = True
            self.progress.status = InstallationStatus.CANCELLED
            self.logger.warning("❌ Installation cancellation requested")
    
    def get_progress(self) -> Dict[str, Any]:
        """Get current installation progress"""
        with self.lock:
            return self.progress.to_dict()
    
    def _cleanup(self):
        """Cleanup resources"""
        try:
            # Close SSH connections
            for node in self.config.nodes:
                if node.host != "localhost":
                    ssh_manager.remove_host(node.host)
        except Exception as e:
            self.logger.warning(f"Cleanup error: {e}")

# Factory function for creating installers
def create_installer(config: InstallationConfig) -> BaseInstaller:
    """Factory function to create appropriate installer"""
    if config.mode == InstallationMode.ALL_IN_ONE:
        from ..scripts.all_in_one.installer import AllInOneInstaller
        return AllInOneInstaller(config)
    elif config.mode == InstallationMode.HA_SECURE:
        from ..scripts.ha_secure.installer import HASecureInstaller
        return HASecureInstaller(config)
    else:
        raise ValueError(f"Unsupported installation mode: {config.mode}")

__all__ = [
    'InstallationMode', 'InstallationStatus', 'CNIProvider',
    'NodeConfig', 'InstallationConfig', 'InstallationStep', 'StepResult',
    'InstallationProgress', 'BaseInstaller', 'create_installer'
]
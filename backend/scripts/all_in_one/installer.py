#!/usr/bin/env python3
"""
All-in-One Kubernetes Installer
Installs single-node Kubernetes cluster with containerd and CNI
"""

import os
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from ...core.installer import (
    BaseInstaller, InstallationStep, InstallationConfig, 
    InstallationMode, NodeConfig, CNIProvider
)
from ...utils.helpers import run_command, ensure_directory, format_duration
from ...config.settings import settings

class AllInOneInstaller(BaseInstaller):
    """All-in-One Kubernetes installer implementation"""
    
    def __init__(self, config: InstallationConfig):
        # Validate config for All-in-One mode
        if config.mode != InstallationMode.ALL_IN_ONE:
            raise ValueError("AllInOneInstaller requires ALL_IN_ONE mode")
        
        if len(config.nodes) != 1:
            raise ValueError("All-in-One mode requires exactly one node")
        
        if config.nodes[0].host != "localhost":
            raise ValueError("All-in-One mode requires localhost node")
        
        super().__init__(config)
        self.node = config.nodes[0]
    
    def define_installation_steps(self) -> List[InstallationStep]:
        """Define All-in-One installation steps"""
        return [
            InstallationStep(
                name="System Configuration",
                description="Configure system for Kubernetes (swap, kernel modules, sysctl)",
                function=self.configure_system,
                timeout=180,
                max_retries=2
            ),
            InstallationStep(
                name="Install Kubernetes Components",
                description="Install kubeadm, kubelet, kubectl",
                function=self.install_kubernetes_components,
                timeout=600,  # apt operations can be slow
                max_retries=3
            ),
            InstallationStep(
                name="Install Container Runtime",
                description="Install and configure containerd",
                function=self.install_containerd,
                timeout=300,
                max_retries=2
            ),
            InstallationStep(
                name="Initialize Cluster",
                description="Initialize Kubernetes cluster with kubeadm",
                function=self.initialize_cluster,
                timeout=600,
                max_retries=1  # Only 1 retry for cluster init
            ),
            InstallationStep(
                name="Configure kubectl",
                description="Setup kubectl configuration for user access",
                function=self.configure_kubectl,
                timeout=60,
                max_retries=2
            ),
            InstallationStep(
                name="Remove Master Taint",
                description="Remove taint from control plane to allow pod scheduling",
                function=self.remove_master_taint,
                timeout=60,
                max_retries=2
            ),
            InstallationStep(
                name="Install CNI",
                description=f"Install {self.config.cni_provider.value} Container Network Interface",
                function=self.install_cni,
                timeout=300,
                max_retries=3
            ),
            InstallationStep(
                name="Configure Storage",
                description="Install and configure local-path-provisioner StorageClass",
                function=self.configure_storage,
                timeout=180,
                max_retries=2
            ),
            InstallationStep(
                name="Wait for System Ready",
                description="Wait for all system components to be ready",
                function=self.wait_for_system_ready,
                timeout=300,
                max_retries=1
            )
        ]
    
    def configure_system(self) -> bool:
        """Configure system for Kubernetes"""
        self.logger.info("🔧 Configuring system for Kubernetes...")
        
        # Define system configuration commands
        commands = [
            # Disable swap
            {
                "description": "Disable swap",
                "command": "swapoff -a",
                "critical": True
            },
            {
                "description": "Disable swap in fstab",
                "command": "sed -i '/ swap / s/^/#/' /etc/fstab",
                "critical": True
            },
            
            # Configure kernel modules
            {
                "description": "Add kernel modules configuration",
                "command": """cat <<EOF | tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF""",
                "critical": True
            },
            {
                "description": "Load overlay module",
                "command": "modprobe overlay",
                "critical": True
            },
            {
                "description": "Load br_netfilter module", 
                "command": "modprobe br_netfilter",
                "critical": True
            },
            
            # Configure sysctl parameters
            {
                "description": "Configure sysctl parameters",
                "command": """cat <<EOF | tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF""",
                "critical": True
            },
            {
                "description": "Apply sysctl parameters",
                "command": "sysctl --system",
                "critical": True
            }
        ]
        
        # Execute commands
        for cmd in commands:
            self.logger.info(f"  → {cmd['description']}")
            success, output = self.execute_command(cmd['command'])
            
            if not success:
                if cmd['critical']:
                    self.logger.error(f"Critical command failed: {cmd['description']}")
                    return False
                else:
                    self.logger.warning(f"Non-critical command failed: {cmd['description']}")
        
        self.logger.info("✅ System configuration completed")
        return True
    
    def install_kubernetes_components(self) -> bool:
        """Install Kubernetes components"""
        self.logger.info("📦 Installing Kubernetes components...")
        
        # Check if already installed
        success, output = self.execute_command("which kubeadm", timeout=10)
        if success:
            self.logger.info("  → Kubernetes components already installed")
            return True
        
        k8s_version = self.config.k8s_version
        
        commands = [
            {
                "description": "Update package index",
                "command": "apt-get update",
                "critical": True
            },
            {
                "description": "Install dependencies",
                "command": "apt-get install -y apt-transport-https ca-certificates curl gpg",
                "critical": True
            },
            {
                "description": "Add Kubernetes GPG key",
                "command": f"curl -fsSL https://pkgs.k8s.io/core:/stable:/v{k8s_version}/deb/Release.key | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg",
                "critical": True
            },
            {
                "description": "Add Kubernetes repository",
                "command": f"echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v{k8s_version}/deb/ /' | tee /etc/apt/sources.list.d/kubernetes.list",
                "critical": True
            },
            {
                "description": "Update package index",
                "command": "apt-get update",
                "critical": True
            },
            {
                "description": "Install Kubernetes packages",
                "command": "apt-get install -y kubelet kubeadm kubectl",
                "critical": True
            },
            {
                "description": "Hold Kubernetes packages",
                "command": "apt-mark hold kubelet kubeadm kubectl",
                "critical": False
            },
            {
                "description": "Enable kubelet service",
                "command": "systemctl enable --now kubelet",
                "critical": True
            }
        ]
        
        for cmd in commands:
            self.logger.info(f"  → {cmd['description']}")
            success, output = self.execute_command(cmd['command'], timeout=300)
            
            if not success and cmd['critical']:
                self.logger.error(f"Failed to {cmd['description'].lower()}")
                return False
        
        # Verify installation
        success, version = self.execute_command("kubeadm version --output=short")
        if success:
            self.logger.info(f"✅ Kubernetes components installed: {version}")
        else:
            self.logger.error("Failed to verify Kubernetes installation")
            return False
        
        return True
    
    def install_containerd(self) -> bool:
        """Install and configure containerd"""
        self.logger.info("🐳 Installing and configuring containerd...")
        
        # Check if containerd is already running
        success, output = self.execute_command("systemctl is-active containerd", timeout=10)
        if success and "active" in output:
            self.logger.info("  → containerd is already running")
            return True
        
        commands = [
            {
                "description": "Install containerd",
                "command": "apt install containerd -y",
                "critical": True
            },
            {
                "description": "Create containerd config directory", 
                "command": "mkdir -p /etc/containerd",
                "critical": True
            },
            {
                "description": "Generate default containerd config",
                "command": "containerd config default > /etc/containerd/config.toml",
                "critical": True
            },
            {
                "description": "Enable SystemdCgroup",
                "command": "sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml",
                "critical": True
            },
            {
                "description": "Restart containerd service",
                "command": "systemctl restart containerd.service",
                "critical": True
            },
            {
                "description": "Restart kubelet service",
                "command": "systemctl restart kubelet.service",
                "critical": False
            }
        ]
        
        for cmd in commands:
            self.logger.info(f"  → {cmd['description']}")
            success, output = self.execute_command(cmd['command'])
            
            if not success and cmd['critical']:
                self.logger.error(f"Failed to {cmd['description'].lower()}")
                return False
        
        # Verify containerd is running
        success, output = self.execute_command("systemctl is-active containerd")
        if success and "active" in output:
            self.logger.info("✅ containerd installed and configured")
            return True
        else:
            self.logger.error("containerd is not running properly")
            return False
    
    def initialize_cluster(self) -> bool:
        """Initialize Kubernetes cluster"""
        self.logger.info("🚀 Initializing Kubernetes cluster...")
        
        # Check if cluster is already initialized
        success, output = self.execute_command("kubectl cluster-info", timeout=10)
        if success and "running" in output.lower():
            self.logger.info("  → Cluster already initialized")
            return True
        
        # Pull images first
        self.logger.info("  → Pulling container images...")
        success, output = self.execute_command("kubeadm config images pull", timeout=300)
        if not success:
            self.logger.warning("Failed to pre-pull images, continuing anyway...")
        
        # Initialize cluster
        init_command = (
            f"kubeadm init "
            f"--pod-network-cidr={self.config.pod_cidr} "
            f"--service-cidr={self.config.service_cidr} "
            f"--cri-socket=unix:///var/run/containerd/containerd.sock "
            f"--skip-phases=addon/kube-proxy"
        )
        
        self.logger.info("  → Running kubeadm init...")
        success, output = self.execute_command(init_command, timeout=600)
        
        if not success:
            self.logger.error("Cluster initialization failed")
            self.logger.error(f"Error output: {output}")
            return False
        
        self.logger.info("✅ Cluster initialized successfully")
        return True
    
    def configure_kubectl(self) -> bool:
        """Configure kubectl for user access"""
        self.logger.info("⚙️  Configuring kubectl...")
        
        # Setup kubeconfig for root user
        kube_dir = Path.home() / ".kube"
        ensure_directory(kube_dir)
        
        commands = [
            {
                "description": "Create .kube directory",
                "command": f"mkdir -p {kube_dir}",
                "critical": True
            },
            {
                "description": "Copy admin config",
                "command": f"cp -i /etc/kubernetes/admin.conf {kube_dir}/config",
                "critical": True
            },
            {
                "description": "Set config ownership",
                "command": f"chown $(id -u):$(id -g) {kube_dir}/config",
                "critical": True
            }
        ]
        
        for cmd in commands:
            self.logger.info(f"  → {cmd['description']}")
            success, output = self.execute_command(cmd['command'])
            
            if not success and cmd['critical']:
                self.logger.error(f"Failed to {cmd['description'].lower()}")
                return False
        
        # Copy config to our installation-specific path
        success, output = self.execute_command(f"cp {kube_dir}/config {self.kubeconfig_path}")
        if not success:
            self.logger.warning(f"Failed to copy config to {self.kubeconfig_path}")
        
        # Test kubectl access
        success, output = self.execute_command("kubectl cluster-info", timeout=30)
        if success:
            self.logger.info("✅ kubectl configured successfully")
            return True
        else:
            self.logger.error("kubectl configuration test failed")
            return False
    
    def remove_master_taint(self) -> bool:
        """Remove taint from master node to allow pod scheduling"""
        self.logger.info("🏷️  Removing master taint...")
        
        # Remove control-plane taint
        success, output = self.execute_command(
            "kubectl taint nodes --all node-role.kubernetes.io/control-plane- || true",
            timeout=60
        )
        
        if success or "not found" in output.lower():
            self.logger.info("✅ Master taint removed")
            return True
        else:
            self.logger.error("Failed to remove master taint")
            return False
    
    def install_cni(self) -> bool:
        """Install Container Network Interface"""
        self.logger.info(f"🌐 Installing {self.config.cni_provider.value} CNI...")
        
        if self.config.cni_provider == CNIProvider.CILIUM:
            return self._install_cilium()
        elif self.config.cni_provider == CNIProvider.CALICO:
            return self._install_calico()
        elif self.config.cni_provider == CNIProvider.FLANNEL:
            return self._install_flannel()
        else:
            self.logger.error(f"Unsupported CNI provider: {self.config.cni_provider}")
            return False
    
    def _install_cilium(self) -> bool:
        """Install Cilium CNI"""
        self.logger.info("  → Installing Cilium...")
        
        # Check if already installed
        success, output = self.execute_command(
            "kubectl get pods -n kube-system -l k8s-app=cilium --no-headers",
            timeout=30
        )
        if success and output.strip():
            self.logger.info("  → Cilium already installed")
            return True
        
        # Install Cilium
        cilium_manifest = "https://raw.githubusercontent.com/cilium/cilium/v1.14.5/install/kubernetes/quick-install.yaml"
        success, output = self.execute_command(
            f"kubectl apply -f {cilium_manifest}",
            timeout=180
        )
        
        if not success:
            self.logger.error("Failed to install Cilium")
            return False
        
        # Wait for Cilium pods to be ready
        def check_cilium_ready():
            success, output = self.execute_command(
                "kubectl get pods -n kube-system -l k8s-app=cilium --no-headers",
                timeout=30
            )
            if not success:
                return False
            
            for line in output.strip().split('\n'):
                if line and 'Running' not in line:
                    return False
            return True
        
        if self.wait_for_condition(check_cilium_ready, "Cilium pods to be ready", timeout=300):
            self.logger.info("✅ Cilium CNI installed and ready")
            return True
        else:
            self.logger.error("Cilium pods failed to become ready")
            return False
    
    def _install_calico(self) -> bool:
        """Install Calico CNI"""
        self.logger.info("  → Installing Calico...")
        
        # Check if already installed
        success, output = self.execute_command(
            "kubectl get pods -n kube-system -l k8s-app=calico-node --no-headers",
            timeout=30
        )
        if success and output.strip():
            self.logger.info("  → Calico already installed")
            return True
        
        # Install Calico
        calico_manifest = "https://docs.projectcalico.org/manifests/calico.yaml"
        success, output = self.execute_command(
            f"kubectl apply -f {calico_manifest}",
            timeout=180
        )
        
        if not success:
            self.logger.error("Failed to install Calico")
            return False
        
        # Wait for Calico pods to be ready
        def check_calico_ready():
            success, output = self.execute_command(
                "kubectl get pods -n kube-system -l k8s-app=calico-node --no-headers",
                timeout=30
            )
            if not success:
                return False
            
            for line in output.strip().split('\n'):
                if line and 'Running' not in line:
                    return False
            return True
        
        if self.wait_for_condition(check_calico_ready, "Calico pods to be ready", timeout=300):
            self.logger.info("✅ Calico CNI installed and ready")
            return True
        else:
            self.logger.error("Calico pods failed to become ready")
            return False
    
    def _install_flannel(self) -> bool:
        """Install Flannel CNI"""
        self.logger.info("  → Installing Flannel...")
        
        # Check if already installed
        success, output = self.execute_command(
            "kubectl get pods -n kube-flannel --no-headers",
            timeout=30
        )
        if success and output.strip():
            self.logger.info("  → Flannel already installed")
            return True
        
        # Install Flannel
        flannel_manifest = "https://github.com/flannel-io/flannel/releases/latest/download/kube-flannel.yml"
        success, output = self.execute_command(
            f"kubectl apply -f {flannel_manifest}",
            timeout=180
        )
        
        if not success:
            self.logger.error("Failed to install Flannel")
            return False
        
        # Wait for Flannel pods to be ready
        def check_flannel_ready():
            success, output = self.execute_command(
                "kubectl get pods -n kube-flannel --no-headers",
                timeout=30
            )
            if not success:
                return False
            
            for line in output.strip().split('\n'):
                if line and 'Running' not in line:
                    return False
            return True
        
        if self.wait_for_condition(check_flannel_ready, "Flannel pods to be ready", timeout=300):
            self.logger.info("✅ Flannel CNI installed and ready")
            return True
        else:
            self.logger.error("Flannel pods failed to become ready")
            return False
    
    def configure_storage(self) -> bool:
        """Configure storage class"""
        self.logger.info("💾 Configuring storage class...")
        
        # Check if local-path storage class already exists
        success, output = self.execute_command(
            "kubectl get storageclass local-path --no-headers",
            timeout=30
        )
        if success and "local-path" in output:
            self.logger.info("  → local-path StorageClass already exists")
            return True
        
        # Install local-path-provisioner
        self.logger.info("  → Installing local-path-provisioner...")
        provisioner_manifest = "https://raw.githubusercontent.com/rancher/local-path-provisioner/master/deploy/local-path-storage.yaml"
        
        success, output = self.execute_command(
            f"kubectl apply -f {provisioner_manifest}",
            timeout=120
        )
        
        if not success:
            self.logger.error("Failed to install local-path-provisioner")
            return False
        
        # Wait for provisioner to be ready
        def check_provisioner_ready():
            success, output = self.execute_command(
                "kubectl get pods -n local-path-storage --no-headers",
                timeout=30
            )
            if not success:
                return False
            
            for line in output.strip().split('\n'):
                if line and 'Running' not in line:
                    return False
            return True
        
        if not self.wait_for_condition(check_provisioner_ready, "local-path-provisioner to be ready", timeout=180):
            self.logger.warning("local-path-provisioner may not be ready, continuing...")
        
        # Set as default storage class
        self.logger.info("  → Setting as default StorageClass...")
        success, output = self.execute_command(
            'kubectl patch storageclass local-path -p \'{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}\'',
            timeout=30
        )
        
        if success:
            self.logger.info("✅ Storage class configured successfully")
            return True
        else:
            self.logger.error("Failed to set default storage class")
            return False
    
    def wait_for_system_ready(self) -> bool:
        """Wait for all system components to be ready"""
        self.logger.info("⏳ Waiting for system to be ready...")
        
        # Wait for all nodes to be ready
        def check_nodes_ready():
            success, output = self.execute_command(
                "kubectl get nodes --no-headers",
                timeout=30
            )
            if not success:
                return False
            
            for line in output.strip().split('\n'):
                if line and 'Ready' not in line:
                    return False
            return True
        
        if not self.wait_for_condition(check_nodes_ready, "nodes to be ready", timeout=180):
            return False
        
        # Wait for core system pods
        critical_pods = [
            ("kube-system", "kube-apiserver"),
            ("kube-system", "kube-controller-manager"),
            ("kube-system", "kube-scheduler"),
            ("kube-system", "etcd"),
        ]
        
        for namespace, pod_prefix in critical_pods:
            def check_pod_ready():
                success, output = self.execute_command(
                    f"kubectl get pods -n {namespace} --no-headers | grep {pod_prefix}",
                    timeout=30
                )
                if not success:
                    return False
                
                for line in output.strip().split('\n'):
                    if line and 'Running' not in line:
                        return False
                return True
            
            if not self.wait_for_condition(
                check_pod_ready, 
                f"{pod_prefix} pod to be ready", 
                timeout=120
            ):
                self.logger.warning(f"{pod_prefix} pod may not be ready")
        
        # Final cluster health check
        success, output = self.execute_command("kubectl cluster-info", timeout=30)
        if success and "running" in output.lower():
            self.logger.info("✅ System is ready!")
            return True
        else:
            self.logger.error("System readiness check failed")
            return False
    
    def get_cluster_info(self) -> Dict[str, Any]:
        """Get cluster information"""
        info = {
            'mode': 'all-in-one',
            'kubernetes_version': self.config.k8s_version,
            'cni_provider': self.config.cni_provider.value,
            'pod_cidr': self.config.pod_cidr,
            'service_cidr': self.config.service_cidr,
            'kubeconfig_path': str(self.kubeconfig_path),
            'installation_id': self.config.installation_id
        }
        
        # Get cluster status
        try:
            success, output = self.execute_command("kubectl get nodes -o wide --no-headers", timeout=30)
            if success:
                info['nodes'] = []
                for line in output.strip().split('\n'):
                    if line:
                        parts = line.split()
                        if len(parts) >= 6:
                            info['nodes'].append({
                                'name': parts[0],
                                'status': parts[1],
                                'roles': parts[2],
                                'age': parts[3],
                                'version': parts[4],
                                'internal_ip': parts[5],
                            })
            
            # Get pod count by namespace
            success, output = self.execute_command(
                "kubectl get pods --all-namespaces --no-headers | awk '{print $1}' | sort | uniq -c",
                timeout=30
            )
            if success:
                info['pod_count_by_namespace'] = {}
                for line in output.strip().split('\n'):
                    if line:
                        parts = line.strip().split()
                        if len(parts) == 2:
                            count, namespace = parts
                            info['pod_count_by_namespace'][namespace] = int(count)
            
        except Exception as e:
            self.logger.warning(f"Failed to get cluster info: {e}")
        
        return info
    
    def generate_kubeconfig_instructions(self) -> str:
        """Generate instructions for accessing the cluster"""
        instructions = f"""
🎉 Kubernetes All-in-One Installation Complete!

📋 Cluster Information:
   • Installation ID: {self.config.installation_id}
   • Kubernetes Version: {self.config.k8s_version}
   • CNI Provider: {self.config.cni_provider.value}
   • Pod CIDR: {self.config.pod_cidr}
   • Service CIDR: {self.config.service_cidr}

🔧 Accessing Your Cluster:

1. Using kubectl (as root):
   kubectl get nodes
   kubectl get pods --all-namespaces

2. Kubeconfig location:
   {self.kubeconfig_path}

3. Set KUBECONFIG environment variable:
   export KUBECONFIG={self.kubeconfig_path}

4. Test cluster access:
   kubectl cluster-info
   kubectl get nodes
   kubectl get pods -A

📝 Next Steps:

1. Deploy sample application:
   kubectl create deployment nginx --image=nginx
   kubectl expose deployment nginx --port=80 --type=NodePort

2. Check application:
   kubectl get pods
   kubectl get services

3. Access application:
   curl http://localhost:<node-port>

🛡️  Security Notes:
   • This is a development cluster - not for production use
   • All pods can run on the control plane node
   • No network policies are configured by default

📚 Useful Commands:
   • kubectl get all -A                    # See all resources
   • kubectl describe node <node-name>     # Node details
   • kubectl logs -n kube-system <pod>     # System pod logs
   • kubectl top nodes                     # Resource usage (if metrics-server installed)

🔍 Troubleshooting:
   • Check logs: journalctl -u kubelet
   • Pod issues: kubectl describe pod <pod-name>
   • Network issues: kubectl get pods -n kube-system

Happy Kubernetes-ing! 🚀
"""
        return instructions

# Convenience function for direct usage
def install_all_in_one(
    k8s_version: str = settings.k8s.default_version,
    cni_provider: str = settings.k8s.default_cni,
    pod_cidr: str = settings.k8s.default_pod_cidr,
    service_cidr: str = settings.k8s.default_service_cidr
) -> bool:
    """
    Convenience function to install All-in-One Kubernetes cluster
    
    Args:
        k8s_version: Kubernetes version to install
        cni_provider: CNI provider (cilium, calico, flannel)
        pod_cidr: Pod network CIDR
        service_cidr: Service network CIDR
    
    Returns:
        bool: Installation success
    """
    try:
        # Create configuration
        config = InstallationConfig(
            mode=InstallationMode.ALL_IN_ONE,
            k8s_version=k8s_version,
            cni_provider=CNIProvider(cni_provider),
            pod_cidr=pod_cidr,
            service_cidr=service_cidr,
            nodes=[NodeConfig(host="localhost", role="master")]
        )
        
        # Create and run installer
        installer = AllInOneInstaller(config)
        success = installer.install()
        
        if success:
            print("\n" + installer.generate_kubeconfig_instructions())
            
        return success
        
    except Exception as e:
        print(f"Installation failed: {e}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Kubernetes All-in-One Installer")
    parser.add_argument(
        "--k8s-version", 
        default=settings.k8s.default_version,
        help=f"Kubernetes version (default: {settings.k8s.default_version})"
    )
    parser.add_argument(
        "--cni",
        choices=['cilium', 'calico', 'flannel'],
        default=settings.k8s.default_cni,
        help=f"CNI provider (default: {settings.k8s.default_cni})"
    )
    parser.add_argument(
        "--pod-cidr",
        default=settings.k8s.default_pod_cidr,
        help=f"Pod network CIDR (default: {settings.k8s.default_pod_cidr})"
    )
    parser.add_argument(
        "--service-cidr", 
        default=settings.k8s.default_service_cidr,
        help=f"Service network CIDR (default: {settings.k8s.default_service_cidr})"
    )
    
    args = parser.parse_args()
    
    success = install_all_in_one(
        k8s_version=args.k8s_version,
        cni_provider=args.cni,
        pod_cidr=args.pod_cidr,
        service_cidr=args.service_cidr
    )
    
    exit(0 if success else 1)
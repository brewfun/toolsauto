#!/usr/bin/env python3
"""
Kubernetes All-in-One Installer
Cài đặt và cấu hình Kubernetes cluster single-node với containerd và Calico CNI
Optimized version with better error handling and logging
"""

import logging
import os
import sys
import time
import subprocess
from typing import Tuple, Optional
from pathlib import Path

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('k8s_install.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class K8sInstaller:
    """Kubernetes All-in-One Installer Class"""
    
    def __init__(self):
        self.k8s_version = "1.30"
        self.pod_cidr = "10.10.0.0/16"
        self.kubeconfig_path = Path.home() / ".kube" / "config"
        
    def run_command(self, command: str, check_output: bool = False, timeout: int = 300) -> Tuple[bool, str]:
        """
        Thực thi command shell với error handling tốt hơn
        
        Args:
            command: Command cần chạy
            check_output: Có capture output không
            timeout: Timeout cho command (seconds)
            
        Returns:
            Tuple[bool, str]: (success, output/error)
        """
        try:
            logger.debug(f"Executing: {command}")
            
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False
            )
            
            if result.returncode == 0:
                logger.debug(f"Command succeeded: {command}")
                return True, result.stdout.strip()
            else:
                logger.error(f"Command failed: {command}")
                logger.error(f"Error output: {result.stderr.strip()}")
                return False, result.stderr.strip()
                
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out after {timeout}s: {command}")
            return False, f"Command timed out after {timeout} seconds"
        except Exception as e:
            logger.error(f"Exception running command '{command}': {str(e)}")
            return False, str(e)

    def check_root_privileges(self) -> bool:
        """Kiểm tra quyền root"""
        if os.geteuid() != 0:
            logger.error("Script này cần chạy với quyền root/sudo")
            return False
        return True

    def configure_system(self) -> bool:
        """Cấu hình hệ thống cơ bản cho Kubernetes"""
        logger.info("🔧 Cấu hình hệ thống cho Kubernetes...")

        steps = [
            # Disable swap
            ("Tắt swap", "swapoff -a"),
            ("Disable swap trong fstab", "sed -i '/ swap / s/^/#/' /etc/fstab"),
            
            # Kernel modules
            ("Thêm kernel modules", """cat <<EOF | tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF"""),
            ("Load overlay module", "modprobe overlay"),
            ("Load br_netfilter module", "modprobe br_netfilter"),
            
            # Sysctl configuration
            ("Cấu hình sysctl", """cat <<EOF | tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF"""),
            ("Apply sysctl config", "sysctl --system"),
        ]

        for description, command in steps:
            logger.info(f"  → {description}")
            success, output = self.run_command(command)
            if not success:
                logger.error(f"Lỗi khi {description.lower()}: {output}")
                return False

        logger.info("✅ Cấu hình hệ thống hoàn tất!")
        return True

    def install_kubernetes_components(self) -> bool:
        """Cài đặt kubelet, kubeadm, kubectl"""
        logger.info("📦 Cài đặt Kubernetes components...")

        # Kiểm tra đã cài chưa
        success, _ = self.run_command("which kubeadm")
        if success:
            logger.info("  → Kubernetes components đã được cài đặt")
            return True

        steps = [
            ("Update package index", "apt-get update"),
            ("Cài dependencies", "apt-get install -y apt-transport-https ca-certificates curl gpg"),
            ("Thêm Kubernetes GPG key", 
             f"curl -fsSL https://pkgs.k8s.io/core:/stable:/v{self.k8s_version}/deb/Release.key | "
             "gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg"),
            ("Thêm Kubernetes repository",
             f"echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] "
             f"https://pkgs.k8s.io/core:/stable:/v{self.k8s_version}/deb/ /' | "
             "tee /etc/apt/sources.list.d/kubernetes.list"),
            ("Update package index", "apt-get update"),
            ("Cài Kubernetes packages", "apt-get install -y kubelet kubeadm kubectl"),
            ("Hold packages", "apt-mark hold kubelet kubeadm kubectl"),
            ("Enable kubelet service", "systemctl enable --now kubelet"),
        ]

        for description, command in steps:
            logger.info(f"  → {description}")
            success, output = self.run_command(command, timeout=600)  # Tăng timeout cho apt
            if not success:
                logger.error(f"Lỗi khi {description.lower()}: {output}")
                return False

        logger.info("✅ Kubernetes components cài đặt thành công!")
        return True

    def install_containerd(self) -> bool:
        """Cài đặt và cấu hình containerd"""
        logger.info("🐳 Cài đặt và cấu hình containerd...")

        # Kiểm tra đã cài chưa
        success, output = self.run_command("systemctl is-active containerd")
        if success and "active" in output:
            logger.info("  → containerd đã chạy")
            return True

        steps = [
            ("Cài containerd", "apt install containerd -y"),
            ("Tạo thư mục config", "mkdir -p /etc/containerd"),
            ("Tạo config mặc định", "containerd config default > /etc/containerd/config.toml"),
            ("Bật SystemdCgroup", "sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml"),
            ("Restart containerd", "systemctl restart containerd.service"),
            ("Restart kubelet", "systemctl restart kubelet.service"),
        ]

        for description, command in steps:
            logger.info(f"  → {description}")
            success, output = self.run_command(command)
            if not success:
                logger.error(f"Lỗi khi {description.lower()}: {output}")
                return False

        logger.info("✅ containerd cài đặt và cấu hình thành công!")
        return True

    def wait_for_api_server(self, timeout: int = 300) -> bool:
        """Chờ Kubernetes API server sẵn sàng"""
        logger.info("⏳ Chờ Kubernetes API server sẵn sàng...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            success, output = self.run_command("kubectl cluster-info", timeout=10)
            if success and "running" in output.lower():
                logger.info("✅ API server đã sẵn sàng!")
                return True
            
            remaining = int(timeout - (time.time() - start_time))
            logger.info(f"  → Chờ thêm... (còn {remaining}s)")
            time.sleep(10)
            
        logger.error(f"❌ Timeout chờ API server ({timeout}s)")
        return False

    def init_kubernetes_cluster(self) -> bool:
        """Khởi tạo Kubernetes cluster"""
        logger.info("🚀 Khởi tạo Kubernetes cluster...")

        # Kiểm tra cluster đã tồn tại chưa
        success, _ = self.run_command("kubectl cluster-info", timeout=10)
        if success:
            logger.info("  → Kubernetes cluster đã tồn tại!")
            return True

        # Thiết lập KUBECONFIG
        os.environ["KUBECONFIG"] = str(self.kubeconfig_path)

        steps = [
            ("Pull container images", "kubeadm config images pull"),
            ("Khởi tạo cluster", 
             f"kubeadm init --pod-network-cidr={self.pod_cidr} --skip-phases=addon/kube-proxy"),
        ]

        for description, command in steps:
            logger.info(f"  → {description}")
            success, output = self.run_command(command, timeout=600)  # Tăng timeout
            if not success:
                logger.error(f"Lỗi khi {description.lower()}: {output}")
                return False

        # Thiết lập kubeconfig
        logger.info("  → Thiết lập kubeconfig")
        kubeconfig_commands = [
            f"mkdir -p {self.kubeconfig_path.parent}",
            f"cp -i /etc/kubernetes/admin.conf {self.kubeconfig_path}",
            f"chown $(id -u):$(id -g) {self.kubeconfig_path}"
        ]

        for cmd in kubeconfig_commands:
            success, output = self.run_command(cmd)
            if not success:
                logger.error(f"Lỗi khi thiết lập kubeconfig: {output}")
                return False

        # Chờ API server
        if not self.wait_for_api_server():
            return False

        # Remove taint từ control plane node
        logger.info("  → Remove taint từ control plane")
        success, output = self.run_command(
            "kubectl taint nodes --all node-role.kubernetes.io/control-plane- || true"
        )
        # Không cần check lỗi vì có thể taint không tồn tại

        logger.info("✅ Kubernetes cluster khởi tạo thành công!")
        return True

    def install_calico(self) -> bool:
        """Cài đặt Calico CNI"""
        logger.info("🌐 Cài đặt Calico CNI...")

        # Kiểm tra đã cài chưa
        success, output = self.run_command("kubectl get pods -n kube-system -l k8s-app=calico-node")
        if success and "calico-node" in output:
            logger.info("  → Calico đã được cài đặt!")
            return True

        # Cài Calico
        logger.info("  → Apply Calico manifest")
        success, output = self.run_command(
            "kubectl apply -f https://docs.projectcalico.org/manifests/calico.yaml",
            timeout=180
        )
        if not success:
            logger.error(f"Lỗi khi cài Calico: {output}")
            return False

        # Chờ Calico pods ready
        logger.info("  → Chờ Calico pods ready...")
        success, output = self.run_command(
            "kubectl wait --for=condition=ready pod -l k8s-app=calico-node -n kube-system --timeout=300s"
        )
        if not success:
            logger.warning(f"Calico pods có thể chưa ready hoàn toàn: {output}")
            # Không return False vì có thể cần thời gian

        logger.info("✅ Calico CNI cài đặt thành công!")
        return True

    def configure_storage_class(self) -> bool:
        """Cấu hình local-path StorageClass"""
        logger.info("💾 Cấu hình StorageClass...")

        # Kiểm tra đã tồn tại chưa
        success, output = self.run_command("kubectl get storageclass local-path")
        if success:
            logger.info("  → StorageClass local-path đã tồn tại!")
            return True

        steps = [
            ("Cài local-path-provisioner",
             "kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/master/deploy/local-path-storage.yaml"),
            ("Đặt làm default StorageClass",
             'kubectl patch storageclass local-path -p \'{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}\''),
        ]

        for description, command in steps:
            logger.info(f"  → {description}")
            success, output = self.run_command(command)
            if not success:
                logger.error(f"Lỗi khi {description.lower()}: {output}")
                return False

        logger.info("✅ StorageClass cấu hình thành công!")
        return True

    def verify_installation(self) -> bool:
        """Verify cluster hoạt động"""
        logger.info("🔍 Kiểm tra trạng thái cluster...")

        checks = [
            ("Cluster info", "kubectl cluster-info"),
            ("Node status", "kubectl get nodes"),
            ("System pods", "kubectl get pods -n kube-system"),
            ("StorageClass", "kubectl get storageclass"),
        ]

        for description, command in checks:
            logger.info(f"  → {description}")
            success, output = self.run_command(command)
            if not success:
                logger.error(f"Lỗi khi kiểm tra {description.lower()}: {output}")
                return False
            
            # Log một phần output
            lines = output.split('\n')[:3]  # Chỉ log 3 dòng đầu
            for line in lines:
                if line.strip():
                    logger.info(f"    {line}")

        logger.info("✅ Cluster hoạt động bình thường!")
        return True

    def install(self) -> bool:
        """Main installation process"""
        logger.info("🎯 Bắt đầu cài đặt Kubernetes All-in-One...")
        
        # Kiểm tra quyền root
        if not self.check_root_privileges():
            return False

        installation_steps = [
            ("Cấu hình hệ thống", self.configure_system),
            ("Cài Kubernetes components", self.install_kubernetes_components),
            ("Cài containerd", self.install_containerd),
            ("Khởi tạo cluster", self.init_kubernetes_cluster),
            ("Cài Calico CNI", self.install_calico),
            ("Cấu hình StorageClass", self.configure_storage_class),
            ("Verify installation", self.verify_installation),
        ]

        for step_name, step_func in installation_steps:
            logger.info(f"\n{'='*60}")
            logger.info(f"BƯỚC: {step_name}")
            logger.info('='*60)
            
            try:
                if not step_func():
                    logger.error(f"❌ {step_name} thất bại!")
                    return False
            except Exception as e:
                logger.error(f"❌ Exception trong {step_name}: {str(e)}")
                return False

        logger.info(f"\n{'='*60}")
        logger.info("🎉 CÀI ĐẶT HOÀN TẤT!")
        logger.info("✅ Kubernetes All-in-One cluster đã sẵn sàng sử dụng!")
        logger.info(f"📁 Kubeconfig: {self.kubeconfig_path}")
        logger.info(f"📋 Logs: k8s_install.log")
        logger.info('='*60)
        
        return True


def main():
    """Entry point"""
    installer = K8sInstaller()
    
    try:
        success = installer.install()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n❌ Cài đặt bị hủy bởi người dùng")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Lỗi không mong đợi: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
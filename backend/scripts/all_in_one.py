import logging
import os
import time
from utils import run_command

# Thiết lập logging
logger = logging.getLogger(__name__)

def configure_system():
    """
    Cấu hình hệ thống cho Kubernetes: tắt swap, nạp kernel modules, bật sysctl params.
    """
    logger.info("Bắt đầu cấu hình hệ thống cho Kubernetes...")

    # Tắt swap
    success, output = run_command(" swapoff -a")
    if not success:
        logger.error("Lỗi khi tắt swap: %s", output)
        return False
    
    # Vô hiệu hóa swap trong /etc/fstab
    success, output = run_command(" sed -i '/ swap / s/^/#/' /etc/fstab")
    if not success:
        logger.error("Lỗi khi cập nhật /etc/fstab: %s", output)
        return False

    # Thêm kernel modules
    success, output = run_command(
        " tee /etc/modules-load.d/k8s.conf <<EOF\noverlay\nbr_netfilter\nEOF"
    )
    if not success:
        logger.error("Lỗi khi thêm kernel modules: %s", output)
        return False

    # Nạp kernel modules
    for module in ["overlay", "br_netfilter"]:
        success, output = run_command(f" modprobe {module}")
        if not success:
            logger.error("Lỗi khi nạp module %s: %s", module, output)
            return False

    # Thiết lập sysctl params
    success, output = run_command(
        " tee /etc/sysctl.d/k8s.conf <<EOF\nnet.bridge.bridge-nf-call-iptables=1\nnet.bridge.bridge-nf-call-ip6tables=1\nnet.ipv4.ip_forward=1\nEOF"
    )
    if not success:
        logger.error("Lỗi khi thiết lập sysctl params: %s", output)
        return False

    # Áp dụng sysctl params mà không cần reboot
    success, output = run_command(" sysctl --system")
    if not success:
        logger.error("Lỗi khi áp dụng sysctl params: %s", output)
        return False

    logger.info("Cấu hình hệ thống hoàn tất!")
    return True

def install_containerd():
    """
    Cài đặt containerd trên Ubuntu và cấu hình SystemdCgroup.
    """
    logger.info("Bắt đầu cài đặt containerd...")

    # Kiểm tra xem containerd đã cài chưa
    success, output = run_command("containerd --version")
    if success:
        logger.info("containerd đã được cài đặt: %s", output.strip())
        return True

    # Cập nhật package index
    success, output = run_command(" apt-get update")
    if not success:
        logger.error("Lỗi khi chạy apt-get update: %s", output)
        return False

    # Cài đặt dependencies
    success, output = run_command(
        " apt-get install -y apt-transport-https ca-certificates curl gpg"
    )
    if not success:
        logger.error("Lỗi khi cài dependencies: %s", output)
        return False

    # Cài đặt containerd
    success, output = run_command(" apt-get install -y containerd")
    if not success:
        logger.error("Lỗi khi cài containerd: %s", output)
        return False

    # Tạo cấu hình containerd
    success, output = run_command(" mkdir -p /etc/containerd && containerd config default |  tee /etc/containerd/config.toml")
    if not success:
        logger.error("Lỗi khi tạo cấu hình containerd: %s", output)
        return False

    # Bật SystemdCgroup
    success, output = run_command(" sed -i 's/ SystemdCgroup = false/ SystemdCgroup = true/' /etc/containerd/config.toml")
    if not success:
        logger.error("Lỗi khi bật SystemdCgroup: %s", output)
        return False

    # Khởi động lại containerd
    success, output = run_command(" systemctl restart containerd.service")
    if not success:
        logger.error("Lỗi khi khởi động lại containerd: %s", output)
        return False

    logger.info("containerd cài đặt và cấu hình thành công!")
    return True

def install_kubeadm():
    """
    Cài đặt kubeadm, kubelet, kubectl trên Ubuntu (phiên bản 1.30).
    """
    logger.info("Bắt đầu cài đặt kubeadm, kubelet, kubectl...")

    # Kiểm tra xem kubeadm đã cài chưa
    success, output = run_command("kubeadm version")
    if success:
        logger.info("Kubeadm đã được cài đặt: %s", output.strip())
        return True

    # Thêm Kubernetes GPG key
    success, output = run_command(
        "curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.30/deb/Release.key |  gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg"
    )
    if not success:
        logger.error("Lỗi khi thêm Kubernetes GPG key: %s", output)
        return False

    # Thêm Kubernetes repository
    success, output = run_command(
        "echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.30/deb/ /' |  tee /etc/apt/sources.list.d/kubernetes.list"
    )
    if not success:
        logger.error("Lỗi khi thêm Kubernetes repository: %s", output)
        return False

    # Cài đặt kubeadm, kubelet, kubectl
    success, output = run_command(" apt-get update &&  apt-get install -y kubelet kubeadm kubectl")
    if not success:
        logger.error("Lỗi khi cài kubeadm, kubelet, kubectl: %s", output)
        return False

    # Giữ phiên bản cố định
    success, output = run_command(" apt-mark hold kubelet kubeadm kubectl")
    if not success:
        logger.error("Lỗi khi hold packages: %s", output)
        return False

    # Enable và start kubelet
    success, output = run_command(" systemctl enable --now kubelet")
    if not success:
        logger.error("Lỗi khi enable/start kubelet: %s", output)
        return False

    logger.info("Kubeadm, kubelet, kubectl cài đặt thành công!")
    return True

def wait_for_api_server(timeout=300):
    """
    Chờ Kubernetes API server sẵn sàng.
    Args:
        timeout (int): Thời gian chờ tối đa (giây).
    Returns:
        bool: True nếu API server sẵn sàng, False nếu hết thời gian.
    """
    logger.info("Chờ Kubernetes API server sẵn sàng...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        success, output = run_command("kubectl cluster-info")
        if success:
            logger.info("Kubernetes API server đã sẵn sàng!")
            return True
        logger.debug("API server chưa sẵn sàng, thử lại sau 5 giây: %s", output)
        time.sleep(5)
    logger.error("Hết thời gian chờ API server (%d giây)", timeout)
    return False

def init_kubernetes():
    """
    Khởi tạo single-node Kubernetes cluster với kubeadm, dùng containerd runtime.
    """
    logger.info("Bắt đầu khởi tạo Kubernetes cluster...")

    # Kiểm tra xem cluster đã init chưa
    success, output = run_command("kubectl cluster-info")
    if success:
        logger.info("Kubernetes cluster đã tồn tại!")
        return True

    # Thiết lập biến môi trường KUBECONFIG
    os.environ["KUBECONFIG"] = os.path.expanduser("~/.kube/config")

    # Tải trước images
    success, output = run_command(" kubeadm config images pull")
    if not success:
        logger.error("Lỗi khi tải images: %s", output)
        return False

    # Khởi tạo cluster
    success, output = run_command(
        " kubeadm init --pod-network-cidr=10.10.0.0/16 --cri-socket=unix:///var/run/containerd/containerd.sock --skip-phases=addon/kube-proxy"
    )
    if not success:
        logger.error("Lỗi khi khởi tạo cluster: %s", output)
        return False

    # Thiết lập kubeconfig
    success, output = run_command(
        "mkdir -p $HOME/.kube &&  cp -i /etc/kubernetes/admin.conf $HOME/.kube/config &&  chown $(id -u):$(id -g) $HOME/.kube/config"
    )
    if not success:
        logger.error("Lỗi khi thiết lập kubeconfig: %s", output)
        return False

    # Chờ API server sẵn sàng
    if not wait_for_api_server():
        logger.error("Kubernetes API server không sẵn sàng, thoát.")
        return False

    # Taint master node để chạy pods
    success, output = run_command("kubectl taint nodes --all node-role.kubernetes.io/control-plane-")
    if not success:
        logger.error("Lỗi khi taint master node: %s", output)
        return False

    logger.info("Kubernetes cluster khởi tạo thành công!")
    return True

def install_calico():
    """
    Cài đặt Calico làm CNI cho Kubernetes.
    """
    logger.info("Bắt đầu cài đặt Calico CNI...")

    # Kiểm tra xem Calico đã cài chưa
    success, output = run_command("kubectl get pods -n kube-system -l k8s-app=calico-node")
    if success and "calico-node" in output:
        logger.info("Calico đã được cài đặt!")
        return True

    # Cài Calico
    success, output = run_command(
        "kubectl apply -f https://docs.projectcalico.org/manifests/calico.yaml"
    )
    if not success:
        logger.error("Lỗi khi cài Calico: %s", output)
        return False

    # Chờ Calico pods ready
    success, output = run_command(
        "kubectl wait --for=condition=ready pod -l k8s-app=calico-node -n kube-system --timeout=300s"
    )
    if not success:
        logger.error("Lỗi khi chờ Calico pods: %s", output)
        return False

    logger.info("Calico CNI cài đặt thành công!")
    return True

def configure_storage_class():
    """
    Cài đặt và cấu hình local-path-provisioner làm default StorageClass.
    """
    logger.info("Bắt đầu cấu hình StorageClass...")

    # Kiểm tra xem StorageClass local-path đã tồn tại chưa
    success, output = run_command("kubectl get storageclass local-path")
    if success:
        logger.info("StorageClass local-path đã tồn tại!")
        return True

    # Cài local-path-provisioner
    success, output = run_command(
        "kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/master/deploy/local-path-storage.yaml"
    )
    if not success:
        logger.error("Lỗi khi cài local-path-provisioner: %s", output)
        return False

    # Đặt local-path làm default StorageClass
    success, output = run_command(
        "kubectl patch storageclass local-path -p '{\"metadata\": {\"annotations\":{\"storageclass.kubernetes.io/is-default-class\":\"true\"}}}'"
    )
    if not success:
        logger.error("Lỗi khi đặt default StorageClass: %s", output)
        return False

    logger.info("StorageClass local-path cài đặt và cấu hình thành công!")
    return True

def main():
    """
    Hàm chính để chạy toàn bộ quy trình cài đặt Kubernetes All-in-One.
    """
    logger.info("Bắt đầu quy trình cài đặt Kubernetes All-in-One với containerd và Calico...")

    # Bước 1: Cấu hình hệ thống
    if not configure_system():
        logger.error("Cấu hình hệ thống thất bại, thoát.")
        return False

    # Bước 2: Cài containerd
    if not install_containerd():
        logger.error("Cài đặt containerd thất bại, thoát.")
        return False

    # Bước 3: Cài kubeadm, kubelet, kubectl
    if not install_kubeadm():
        logger.error("Cài đặt kubeadm thất bại, thoát.")
        return False

    # Bước 4: Khởi tạo cluster
    if not init_kubernetes():
        logger.error("Khởi tạo Kubernetes thất bại, thoát.")
        return False

    # Bước 5: Cài Calico CNI
    if not install_calico():
        logger.error("Cài đặt Calico thất bại, thoát.")
        return False

    # Bước 6: Cấu hình StorageClass
    if not configure_storage_class():
        logger.error("Cấu hình StorageClass thất bại, thoát.")
        return False

    logger.info("Cài đặt Kubernetes All-in-One hoàn tất!")
    return True

if __name__ == "__main__":
    success = main()
    if success:
        print("Cài đặt thành công! Cluster đã sẵn sàng.")
    else:
        print("Cài đặt thất bại, kiểm tra logs/app.log để biết chi tiết.")
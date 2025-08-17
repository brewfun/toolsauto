
import pytest
from unittest.mock import patch, MagicMock, call
from backend.scripts.all_in_one.installer import AllInOneInstaller
from backend.core.installer import InstallationConfig, InstallationMode, NodeConfig, CNIProvider

@pytest.fixture
def valid_config():
    return InstallationConfig(
        mode=InstallationMode.ALL_IN_ONE,
        nodes=[NodeConfig(host="localhost", role="master")]
    )

@pytest.fixture
def installer(valid_config):
    with patch('backend.core.installer.BaseInstaller.__init__'):
        installer = AllInOneInstaller(valid_config)
        installer.config = valid_config
        installer.node = valid_config.nodes[0]
        installer.logger = MagicMock()
        installer.kubeconfig_path = "/dummy/path"
        return installer

def test_init_success(installer, valid_config):
    assert installer.config == valid_config

def test_init_invalid_mode():
    config = InstallationConfig(mode=InstallationMode.HA_SECURE)
    with pytest.raises(ValueError, match="AllInOneInstaller requires ALL_IN_ONE mode"):
        AllInOneInstaller(config)

def test_init_invalid_node_count(valid_config):
    valid_config.nodes.append(NodeConfig(host="localhost", role="worker"))
    with pytest.raises(ValueError, match="All-in-One mode requires exactly one node"):
        AllInOneInstaller(valid_config)

def test_init_invalid_host(valid_config):
    valid_config.nodes[0].host = "remotehost"
    with pytest.raises(ValueError, match="All-in-One mode requires localhost node"):
        AllInOneInstaller(valid_config)

def test_define_installation_steps(installer):
    steps = installer.define_installation_steps()
    assert len(steps) == 9
    step_names = [step.name for step in steps]
    assert "Initialize Cluster" in step_names
    assert "Install CNI" in step_names

def test_configure_system_success(installer):
    with patch.object(installer, 'execute_command', return_value=(True, "")) as mock_execute:
        result = installer.configure_system()
        assert result is True
        assert mock_execute.call_count > 0

def test_configure_system_critical_command_fails(installer):
    with patch.object(installer, 'execute_command', return_value=(False, "Error")) as mock_execute:
        result = installer.configure_system()
        assert result is False
        mock_execute.assert_called_once()

def test_install_kubernetes_components_success(installer):
    with patch.object(installer, 'execute_command') as mock_execute:
        # Simulate kubeadm not installed, then successful installation
        mock_execute.side_effect = [(False, ""), (True, ""), (True, ""), (True, ""), (True, ""), (True, ""), (True, ""), (True, ""), (True, ""), (True, "v1.28.0")]
        result = installer.install_kubernetes_components()
        assert result is True
        assert mock_execute.call_count > 1

def test_install_kubernetes_components_already_installed(installer):
    with patch.object(installer, 'execute_command', return_value=(True, "")) as mock_execute:
        result = installer.install_kubernetes_components()
        assert result is True
        mock_execute.assert_called_once_with("which kubeadm", timeout=10)

def test_install_kubernetes_components_critical_command_fails(installer):
    with patch.object(installer, 'execute_command') as mock_execute:
        # Simulate kubeadm not installed, then apt-get update fails
        mock_execute.side_effect = [(False, ""), (False, "Error")]
        result = installer.install_kubernetes_components()
        assert result is False
        assert mock_execute.call_count == 2

def test_install_containerd_success(installer):
    with patch.object(installer, 'execute_command') as mock_execute:
        mock_execute.side_effect = [(False, ""), (True, ""), (True, ""), (True, ""), (True, ""), (True, ""), (True, ""), (True, "active")]
        result = installer.install_containerd()
        assert result is True

def test_install_containerd_already_installed(installer):
    with patch.object(installer, 'execute_command', return_value=(True, "active")) as mock_execute:
        result = installer.install_containerd()
        assert result is True
        mock_execute.assert_called_once_with("systemctl is-active containerd", timeout=10)

def test_install_containerd_critical_command_fails(installer):
    with patch.object(installer, 'execute_command') as mock_execute:
        mock_execute.side_effect = [(False, ""), (False, "Error")]
        result = installer.install_containerd()
        assert result is False

def test_initialize_cluster_success(installer):
    with patch.object(installer, 'execute_command') as mock_execute:
        mock_execute.side_effect = [(False, ""), (True, ""), (True, "")]
        result = installer.initialize_cluster()
        assert result is True

def test_initialize_cluster_already_initialized(installer):
    with patch.object(installer, 'execute_command', return_value=(True, "running")) as mock_execute:
        result = installer.initialize_cluster()
        assert result is True
        mock_execute.assert_called_once_with("kubectl cluster-info", timeout=10)

def test_initialize_cluster_fails(installer):
    with patch.object(installer, 'execute_command') as mock_execute:
        mock_execute.side_effect = [(False, ""), (True, ""), (False, "Error")]
        result = installer.initialize_cluster()
        assert result is False

def test_configure_kubectl_success(installer):
    with patch.object(installer, 'execute_command', return_value=(True, "")) as mock_execute:
        result = installer.configure_kubectl()
        assert result is True

def test_configure_kubectl_fails(installer):
    with patch.object(installer, 'execute_command', return_value=(False, "Error")) as mock_execute:
        result = installer.configure_kubectl()
        assert result is False

def test_remove_master_taint_success(installer):
    with patch.object(installer, 'execute_command', return_value=(True, "")) as mock_execute:
        result = installer.remove_master_taint()
        assert result is True

def test_remove_master_taint_not_found(installer):
    with patch.object(installer, 'execute_command', return_value=(True, "not found")) as mock_execute:
        result = installer.remove_master_taint()
        assert result is True

def test_remove_master_taint_fails(installer):
    with patch.object(installer, 'execute_command', return_value=(False, "Error")) as mock_execute:
        result = installer.remove_master_taint()
        assert result is False

@patch('backend.scripts.all_in_one.installer.AllInOneInstaller._install_cilium', return_value=True)
def test_install_cni_cilium(mock_install, installer):
    installer.config.cni_provider = CNIProvider.CILIUM
    result = installer.install_cni()
    assert result is True
    mock_install.assert_called_once()

@patch('backend.scripts.all_in_one.installer.AllInOneInstaller._install_calico', return_value=True)
def test_install_cni_calico(mock_install, installer):
    installer.config.cni_provider = CNIProvider.CALICO
    result = installer.install_cni()
    assert result is True
    mock_install.assert_called_once()

@patch('backend.scripts.all_in_one.installer.AllInOneInstaller._install_flannel', return_value=True)
def test_install_cni_flannel(mock_install, installer):
    installer.config.cni_provider = CNIProvider.FLANNEL
    result = installer.install_cni()
    assert result is True
    mock_install.assert_called_once()

def test_install_cni_unsupported(installer):
    installer.config.cni_provider = MagicMock()
    result = installer.install_cni()
    assert result is False

def test_configure_storage_success(installer):
    with patch.object(installer, 'execute_command') as mock_execute, \
         patch.object(installer, 'wait_for_condition', return_value=True):
        mock_execute.return_value = (True, "")
        result = installer.configure_storage()
        assert result is True

def test_configure_storage_already_exists(installer):
    with patch.object(installer, 'execute_command', return_value=(True, "local-path")) as mock_execute:
        result = installer.configure_storage()
        assert result is True
        mock_execute.assert_called_once()

def test_configure_storage_fails(installer):
    with patch.object(installer, 'execute_command', return_value=(False, "Error")) as mock_execute:
        result = installer.configure_storage()
        assert result is False

@patch.object(AllInOneInstaller, 'execute_command', return_value=(True, "running"))
@patch.object(AllInOneInstaller, 'wait_for_condition', return_value=True)
def test_wait_for_system_ready_success(mock_wait, mock_execute, installer):
    result = installer.wait_for_system_ready()
    assert result is True

@patch.object(AllInOneInstaller, 'wait_for_condition', return_value=False)
def test_wait_for_system_ready_nodes_fail(mock_wait, installer):
    result = installer.wait_for_system_ready()
    assert result is False

@patch.object(AllInOneInstaller, 'execute_command', return_value=(True, "running"))
@patch.object(AllInOneInstaller, 'wait_for_condition', side_effect=[True, True, True, True, False])
def test_wait_for_system_ready_pods_fail(mock_wait, mock_execute, installer):
    result = installer.wait_for_system_ready()
    assert result is True # Non-critical

@patch.object(AllInOneInstaller, 'wait_for_condition', return_value=True)
@patch.object(AllInOneInstaller, 'execute_command', return_value=(False, "Error"))
def test_wait_for_system_ready_cluster_info_fails(mock_execute, mock_wait, installer):
    result = installer.wait_for_system_ready()
    assert result is False

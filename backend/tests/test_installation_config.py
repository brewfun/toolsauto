import pytest
from unittest.mock import patch
from backend.core.installer import InstallationConfig, InstallationMode, NodeConfig, CNIProvider
from backend.core.ssh_manager import SSHConfig
from backend.config.settings import settings

@pytest.fixture
def valid_all_in_one_config():
    return InstallationConfig(
        mode=InstallationMode.ALL_IN_ONE,
        nodes=[NodeConfig(host="localhost", role="master")]
    )

@pytest.fixture
def valid_ha_secure_config():
    ssh_config = SSHConfig(host="dummy", username="dummy", key_path="/dummy/path")
    return InstallationConfig(
        mode=InstallationMode.HA_SECURE,
        nodes=[
            NodeConfig(host="1.1.1.1", role="master", ssh_config=ssh_config),
            NodeConfig(host="1.1.1.2", role="master", ssh_config=ssh_config),
            NodeConfig(host="1.1.1.3", role="master", ssh_config=ssh_config),
            NodeConfig(host="2.2.2.2", role="loadbalancer", ssh_config=ssh_config),
        ]
    )

def test_valid_all_in_one_config(valid_all_in_one_config):
    errors = valid_all_in_one_config.validate()
    assert not errors

@patch('os.path.exists', return_value=True)
@patch('os.access', return_value=True)
def test_valid_ha_secure_config(mock_access, mock_exists, valid_ha_secure_config):
    errors = valid_ha_secure_config.validate()
    assert not errors

def test_invalid_k8s_version(valid_all_in_one_config):
    valid_all_in_one_config.k8s_version = "1.28."
    errors = valid_all_in_one_config.validate()
    assert "Invalid Kubernetes version" in errors[0]

def test_unsupported_k8s_version(valid_all_in_one_config):
    valid_all_in_one_config.k8s_version = "1.10.0"
    errors = valid_all_in_one_config.validate()
    assert "Unsupported Kubernetes version" in errors[0]

def test_invalid_pod_cidr(valid_all_in_one_config):
    valid_all_in_one_config.pod_cidr = "invalid-cidr"
    errors = valid_all_in_one_config.validate()
    assert "Invalid pod CIDR" in errors[0]

def test_no_nodes():
    config = InstallationConfig(nodes=[])
    errors = config.validate()
    assert "At least one node is required" in errors[0]

def test_all_in_one_too_many_nodes(valid_all_in_one_config):
    valid_all_in_one_config.nodes.append(NodeConfig(host="1.1.1.1", role="worker"))
    errors = valid_all_in_one_config.validate()
    assert "All-in-One mode requires exactly one node" in errors[0]

def test_ha_secure_not_enough_masters(valid_ha_secure_config):
    # Remove one master
    valid_ha_secure_config.nodes.pop(0)
    errors = valid_ha_secure_config.validate()
    assert "HA mode requires at least 3 master nodes" in errors[0]

def test_ha_secure_no_load_balancer(valid_ha_secure_config):
    # Remove load balancer
    valid_ha_secure_config.nodes.pop(3)
    errors = valid_ha_secure_config.validate()
    assert "HA mode requires exactly one load balancer" in errors[0]

def test_invalid_node_host(valid_all_in_one_config):
    valid_all_in_one_config.nodes[0].host = "invalid-host"
    errors = valid_all_in_one_config.validate()
    assert "Invalid host address" in errors[0]
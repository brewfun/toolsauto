
import pytest
from backend.api.routes.installation import validate_request_data
from backend.core.installer import CNIProvider
from backend.config.settings import settings

@pytest.fixture
def base_ha_config():
    """Provides a base valid config for HA secure mode."""
    return {
        "k8s_version": settings.k8s.supported_versions[0],
        "masters": ["1.1.1.1", "1.1.1.2", "1.1.1.3"],
        "load_balancer": "2.2.2.2",
        "ssh_config": {
            "username": "root",
            "auth_method": "key",
            "key_path": "/path/to/key"
        }
    }

# All-in-One Mode Tests
def test_all_in_one_valid():
    data = {"k8s_version": settings.k8s.supported_versions[0]}
    is_valid, errors = validate_request_data(data, 'all_in_one')
    assert is_valid
    assert errors == ""

def test_all_in_one_missing_k8s_version():
    data = {}
    is_valid, errors = validate_request_data(data, 'all_in_one')
    assert not is_valid
    assert "Missing required field: k8s_version" in errors

def test_all_in_one_invalid_k8s_version_format():
    data = {"k8s_version": "1.28."}
    is_valid, errors = validate_request_data(data, 'all_in_one')
    assert not is_valid
    assert "Invalid Kubernetes version" in errors

def test_all_in_one_unsupported_k8s_version():
    data = {"k8s_version": "1.10.0"}
    is_valid, errors = validate_request_data(data, 'all_in_one')
    assert not is_valid
    assert "Unsupported Kubernetes version" in errors

def test_invalid_pod_cidr():
    data = {"k8s_version": settings.k8s.supported_versions[0], "pod_cidr": "10.244.0.0/33"}
    is_valid, errors = validate_request_data(data, 'all_in_one')
    assert not is_valid
    assert "Invalid pod CIDR" in errors

def test_invalid_cni_provider():
    data = {"k8s_version": settings.k8s.supported_versions[0], "cni_provider": "invalid_cni"}
    is_valid, errors = validate_request_data(data, 'all_in_one')
    assert not is_valid
    assert "Invalid CNI provider" in errors

# HA Secure Mode Tests
def test_ha_secure_valid(base_ha_config):
    is_valid, errors = validate_request_data(base_ha_config, 'ha_secure')
    assert is_valid
    assert errors == ""

def test_ha_secure_missing_masters(base_ha_config):
    del base_ha_config["masters"]
    is_valid, errors = validate_request_data(base_ha_config, 'ha_secure')
    assert not is_valid
    assert "Missing required field: masters" in errors

def test_ha_secure_not_enough_masters(base_ha_config):
    base_ha_config["masters"] = ["1.1.1.1", "1.1.1.2"]
    is_valid, errors = validate_request_data(base_ha_config, 'ha_secure')
    assert not is_valid
    assert "HA mode requires at least 3 master nodes" in errors

def test_ha_secure_invalid_master_ip(base_ha_config):
    base_ha_config["masters"][0] = "invalid-ip"
    is_valid, errors = validate_request_data(base_ha_config, 'ha_secure')
    assert not is_valid
    assert "Invalid IP address for master 1" in errors

def test_ha_secure_invalid_worker_ip(base_ha_config):
    base_ha_config["workers"] = ["invalid-ip"]
    is_valid, errors = validate_request_data(base_ha_config, 'ha_secure')
    assert not is_valid
    assert "Invalid IP address for worker 1" in errors

def test_ha_secure_missing_ssh_config(base_ha_config):
    del base_ha_config["ssh_config"]
    is_valid, errors = validate_request_data(base_ha_config, 'ha_secure')
    assert not is_valid
    assert "SSH configuration required for HA mode" in errors

def test_ha_secure_missing_ssh_username(base_ha_config):
    del base_ha_config["ssh_config"]["username"]
    is_valid, errors = validate_request_data(base_ha_config, 'ha_secure')
    assert not is_valid
    assert "SSH username is required" in errors

def test_ha_secure_missing_ssh_password(base_ha_config):
    base_ha_config["ssh_config"]["auth_method"] = "password"
    is_valid, errors = validate_request_data(base_ha_config, 'ha_secure')
    assert not is_valid
    assert "SSH password is required" in errors

def test_ha_secure_missing_ssh_key_path(base_ha_config):
    del base_ha_config["ssh_config"]["key_path"]
    is_valid, errors = validate_request_data(base_ha_config, 'ha_secure')
    assert not is_valid
    assert "SSH key path is required" in errors

import json
import pytest
from unittest.mock import patch, MagicMock

from backend.main import create_app
from backend.api.routes.installation import installations

@pytest.fixture
def client():
    """Create and configure a new app instance for each test."""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture(autouse=True)
def cleanup_installations():
    """Clear the installations dictionary after each test."""
    yield
    installations.clear()

def test_get_installation_modes(client):
    """Test GET /api/v1/installation/modes"""
    response = client.get('/api/v1/installation/modes')
    assert response.status_code == 200
    data = response.get_json()
    assert 'success' in data and data['success'] is True
    assert 'modes' in data
    assert 'all_in_one' in data['modes']
    assert 'ha_secure' in data['modes']
    assert 'supported_versions' in data
    assert 'supported_cnis' in data
    assert 'default_config' in data

@patch('backend.api.routes.installation.validate_request_data', return_value=(True, ""))
@patch('backend.api.routes.installation.create_installation_config')
@patch('backend.api.routes.installation.create_installer')
def test_start_installation_all_in_one_success(mock_create_installer, mock_create_config, mock_validate_data, client):
    """Test POST /api/v1/installation/all_in_one/start - success"""
    mock_installer = MagicMock()
    mock_create_installer.return_value = mock_installer
    mock_config = MagicMock()
    mock_config.validate.return_value = []
    mock_config.installation_id = 'mock-install-id'
    mock_create_config.return_value = mock_config

    response = client.post('/api/v1/installation/all_in_one/start', json={'k8s_version': '1.28.0'})
    assert response.status_code == 202
    data = response.get_json()
    assert data['success'] is True
    assert data['installation_id'] == 'mock-install-id'
    assert data['mode'] == 'all_in_one'
    mock_create_installer.assert_called_once()

@patch('backend.api.routes.installation.validate_request_data', return_value=(True, ""))
@patch('backend.api.routes.installation.create_installation_config')
@patch('backend.api.routes.installation.create_installer')
def test_start_installation_ha_secure_success(mock_create_installer, mock_create_config, mock_validate_data, client):
    """Test POST /api/v1/installation/ha_secure/start - success"""
    mock_installer = MagicMock()
    mock_create_installer.return_value = mock_installer
    mock_config = MagicMock()
    mock_config.validate.return_value = []
    mock_config.installation_id = 'mock-install-id'
    mock_create_config.return_value = mock_config

    ha_config = {
        "k8s_version": "1.28.0",
        "masters": ["192.168.1.10", "192.168.1.11", "192.168.1.12"],
        "load_balancer": "192.168.1.20",
        "workers": ["192.168.1.100"],
        "ssh_config": {
            "username": "testuser",
            "password": "testpassword",
            "auth_method": "password"
        }
    }

    response = client.post('/api/v1/installation/ha_secure/start', json=ha_config)
    assert response.status_code == 202
    data = response.get_json()
    assert data['success'] is True
    assert data['installation_id'] == 'mock-install-id'
    assert data['mode'] == 'ha_secure'
    mock_create_installer.assert_called_once()

def test_start_installation_invalid_mode(client):
    """Test starting installation with an invalid mode"""
    response = client.post('/api/v1/installation/invalid_mode/start', json={'k8s_version': '1.28.0'})
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert 'Invalid installation mode' in data['error']

def test_start_installation_validation_error(client):
    """Test starting installation with missing required fields"""
    response = client.post('/api/v1/installation/ha_secure/start', json={'k8s_version': '1.28.0'})
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert 'Validation failed' in data['error']
    assert 'Missing required field: masters' in data['error']

def test_get_installation_status_not_found(client):
    """Test GET /api/v1/installation/<id>/status for a non-existent installation"""
    response = client.get('/api/v1/installation/invalid_id/status')
    assert response.status_code == 404

def test_get_installation_status_success(client):
    """Test GET /api/v1/installation/<id>/status for an existing installation"""
    mock_installer = MagicMock()
    mock_installer.get_progress.return_value = {'status': 'installing', 'progress': 50}

    installations['mock_id'] = {
        'installer': mock_installer,
        'config': MagicMock(),
        'started_at': 1234567890,
        'completed': False
    }

    response = client.get('/api/v1/installation/mock_id/status')
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['installation_id'] == 'mock_id'
    assert data['progress']['status'] == 'installing'

def test_get_installation_logs_success(client):
    """Test GET /api/v1/installation/<id>/logs"""
    mock_installer = MagicMock()
    mock_logs = [
        {'level': 'INFO', 'message': 'Starting... ' },
        {'level': 'DEBUG', 'message': 'details...'}
    ]
    mock_installer.get_progress.return_value = {'logs': mock_logs}

    installations['mock_id'] = {'installer': mock_installer}

    response = client.get('/api/v1/installation/mock_id/logs')
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert len(data['logs']) == 2

    # Test filtering
    response = client.get('/api/v1/installation/mock_id/logs?level=INFO')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data['logs']) == 1
    assert data['logs'][0]['level'] == 'INFO'

def test_cancel_installation_success(client):
    """Test POST /api/v1/installation/<id>/cancel for a running installation"""
    mock_installer = MagicMock()
    installations['mock_id'] = {
        'installer': mock_installer,
        'completed': False
    }

    response = client.post('/api/v1/installation/mock_id/cancel')
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    mock_installer.cancel.assert_called_once()
    assert installations['mock_id']['completed'] is True
    assert installations['mock_id']['error'] == 'Cancelled by user'

def test_cancel_installation_already_completed(client):
    """Test POST /api/v1/installation/<id>/cancel for a completed installation"""
    installations['mock_id'] = {'completed': True}

    response = client.post('/api/v1/installation/mock_id/cancel')
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert 'already completed' in data['error']
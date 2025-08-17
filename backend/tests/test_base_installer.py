import pytest
from unittest.mock import patch, MagicMock
from backend.core.installer import BaseInstaller, InstallationConfig, InstallationStep, InstallationStatus

class DummyInstaller(BaseInstaller):
    def define_installation_steps(self):
        return [
            InstallationStep(name="Step 1", description="", function=lambda: True),
            InstallationStep(name="Step 2", description="", function=lambda: True, required=False),
            InstallationStep(name="Step 3", description="", function=lambda: False, required=True),
        ]

@pytest.fixture
def config():
    return InstallationConfig()

@pytest.fixture
def installer(config):
    with patch('backend.core.installer.ssh_manager'), \
         patch('backend.core.installer.get_installation_logger'):
        return DummyInstaller(config)

def test_pre_installation_checks_success(installer):
    with patch.object(installer.config, 'validate', return_value=[]), \
         patch.object(installer, '_check_system_requirements', return_value=True), \
         patch.object(installer, '_check_connectivity', return_value=True), \
         patch.object(installer, '_check_prerequisites', return_value=True):
        result = installer.pre_installation_checks()
        assert result is True

def test_pre_installation_checks_fails(installer):
    with patch.object(installer.config, 'validate', return_value=["error"]):
        result = installer.pre_installation_checks()
        assert result is False

def test_execute_step_success(installer):
    step = InstallationStep(name="Test Step", description="", function=lambda: True)
    result = installer.execute_step(step)
    assert result is True
    assert installer.progress.step_results[0].success is True

def test_execute_step_required_fails(installer):
    step = InstallationStep(name="Test Step", description="", function=lambda: False, required=True)
    result = installer.execute_step(step)
    assert result is False

def test_execute_step_optional_fails(installer):
    step = InstallationStep(name="Test Step", description="", function=lambda: False, required=False)
    result = installer.execute_step(step)
    assert result is True

def test_install_success(installer):
    with patch.object(installer, 'pre_installation_checks', return_value=True), \
         patch.object(installer, 'post_installation_verification', return_value=True), \
         patch.object(installer.config, 'save_to_file', return_value=True), \
         patch.object(installer, 'execute_step', return_value=True):
        installer.steps = [InstallationStep(name="Step 1", description="", function=lambda: True)]
        result = installer.install()
        assert result is True
        assert installer.progress.status == InstallationStatus.SUCCESS

def test_install_pre_checks_fail(installer):
    with patch.object(installer, 'pre_installation_checks', return_value=False), \
         patch.object(installer.config, 'save_to_file', return_value=True):
        result = installer.install()
        assert result is False
        assert installer.progress.status == InstallationStatus.FAILED

def test_install_step_fails(installer):
    with patch.object(installer, 'pre_installation_checks', return_value=True), \
         patch.object(installer.config, 'save_to_file', return_value=True):
        installer.steps = [InstallationStep(name="Step 1", description="", function=lambda: False, required=True)]
        result = installer.install()
        assert result is False
        assert installer.progress.status == InstallationStatus.FAILED

def test_install_post_checks_fail(installer):
    with patch.object(installer, 'pre_installation_checks', return_value=True), \
         patch.object(installer, 'post_installation_verification', return_value=False), \
         patch.object(installer.config, 'save_to_file', return_value=True):
        installer.steps = [InstallationStep(name="Step 1", description="", function=lambda: True)]
        result = installer.install()
        assert result is False
        assert installer.progress.status == InstallationStatus.FAILED

def test_cancel_installation(installer):
    installer.cancel()
    assert installer.cancelled is True
    assert installer.progress.status == InstallationStatus.CANCELLED

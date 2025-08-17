#!/usr/bin/env python3
"""
Installation API Routes for K8s Auto Installer
Provides REST endpoints for managing Kubernetes installations
"""

import threading
import time
from flask import Blueprint, request, jsonify
from typing import Dict, Any
import uuid

from backend.core.installer import (
    create_installer, InstallationConfig, InstallationMode,
    NodeConfig, CNIProvider, InstallationStatus
)
from backend.core.ssh_manager import SSHConfig, SSHAuthMethod
from backend.config.settings import settings
from backend.utils.logger import get_logger, log_manager
from backend.utils.helpers import validate_ip_address, validate_cidr, validate_k8s_version

# Create blueprint
installation_bp = Blueprint('installation', __name__, url_prefix='/api/v1/installation')
logger = get_logger(__name__)

# Global storage for installation instances
installations: Dict[str, Any] = {}
installation_threads: Dict[str, threading.Thread] = {}

# Request validation schemas
REQUIRED_FIELDS = {
    'all_in_one': ['k8s_version'],
    'ha_secure': ['k8s_version', 'masters', 'load_balancer']
}

def validate_request_data(data: Dict[str, Any], mode: str) -> tuple[bool, str]:
    """Validate request data"""
    errors = []

    # Check required fields
    required = REQUIRED_FIELDS.get(mode, [])
    for field in required:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    # Validate Kubernetes version
    if 'k8s_version' in data:
        if not validate_k8s_version(data['k8s_version']):
            errors.append(f"Invalid Kubernetes version: {data['k8s_version']}")
        elif data['k8s_version'] not in settings.k8s.supported_versions:
            errors.append(f"Unsupported Kubernetes version: {data['k8s_version']}")

    # Validate CIDR ranges
    if 'pod_cidr' in data and not validate_cidr(data['pod_cidr']):
        errors.append(f"Invalid pod CIDR: {data['pod_cidr']}")

    if 'service_cidr' in data and not validate_cidr(data['service_cidr']):
        errors.append(f"Invalid service CIDR: {data['service_cidr']}")

    # Validate CNI provider
    if 'cni_provider' in data:
        try:
            CNIProvider(data['cni_provider'])
        except ValueError:
            valid_cnis = [cni.value for cni in CNIProvider]
            errors.append(f"Invalid CNI provider. Valid options: {', '.join(valid_cnis)}")

    # Mode-specific validation
    if mode == 'ha_secure':
        # Validate masters
        if 'masters' in data:
            if not isinstance(data['masters'], list) or len(data['masters']) < 3:
                errors.append("HA mode requires at least 3 master nodes")

            for i, master in enumerate(data['masters']):
                if not validate_ip_address(master):
                    errors.append(f"Invalid IP address for master {i+1}: {master}")

        # Validate load balancer
        if 'load_balancer' in data and not validate_ip_address(data['load_balancer']):
            errors.append(f"Invalid load balancer IP: {data['load_balancer']}")

        # Validate workers (optional)
        if 'workers' in data:
            if not isinstance(data['workers'], list):
                errors.append("Workers must be a list of IP addresses")

            for i, worker in enumerate(data['workers']):
                if not validate_ip_address(worker):
                    errors.append(f"Invalid IP address for worker {i+1}: {worker}")

        # SSH configuration is required for HA mode
        if 'ssh_config' not in data:
            errors.append("SSH configuration required for HA mode")
        else:
            ssh_config = data['ssh_config']
            if 'username' not in ssh_config:
                errors.append("SSH username is required")

            if ssh_config.get('auth_method') == 'password' and 'password' not in ssh_config:
                errors.append("SSH password is required for password authentication")

            if ssh_config.get('auth_method') == 'key' and 'key_path' not in ssh_config:
                errors.append("SSH key path is required for key authentication")

    return len(errors) == 0, "; ".join(errors)

def create_installation_config(data: Dict[str, Any], mode: str) -> InstallationConfig:
    """Create installation configuration from request data"""
    installation_id = str(uuid.uuid4())[:8]

    config = InstallationConfig(
        installation_id=installation_id,
        mode=InstallationMode(mode),
        k8s_version=data.get('k8s_version', settings.k8s.default_version),
        pod_cidr=data.get('pod_cidr', settings.k8s.default_pod_cidr),
        service_cidr=data.get('service_cidr', settings.k8s.default_service_cidr),
        cni_provider=CNIProvider(data.get('cni_provider', settings.k8s.default_cni)),
        cluster_name=data.get('cluster_name', 'kubernetes'),
        enable_rbac=data.get('enable_rbac', settings.security.enable_rbac),
        enable_network_policies=data.get('enable_network_policies', settings.security.enable_network_policies),
        enable_monitoring=data.get('enable_monitoring', settings.monitoring.enable_metrics)
    )

    # Add nodes based on mode
    if mode == 'all_in_one':
        config.nodes = [NodeConfig(host="localhost", role="master")]

    elif mode == 'ha_secure':
        # Add load balancer
        lb_ssh_config = create_ssh_config(data.get('ssh_config', {}), data['load_balancer'])
        config.nodes.append(NodeConfig(
            host=data['load_balancer'],
            role="loadbalancer",
            ssh_config=lb_ssh_config
        ))

        # Add masters
        for master_ip in data['masters']:
            master_ssh_config = create_ssh_config(data.get('ssh_config', {}), master_ip)
            config.nodes.append(NodeConfig(
                host=master_ip,
                role="master",
                ssh_config=master_ssh_config
            ))

        # Add workers (optional)
        for worker_ip in data.get('workers', []):
            worker_ssh_config = create_ssh_config(data.get('ssh_config', {}), worker_ip)
            config.nodes.append(NodeConfig(
                host=worker_ip,
                role="worker",
                ssh_config=worker_ssh_config
            ))

    return config

def create_ssh_config(ssh_data: Dict[str, Any], host: str) -> SSHConfig:
    """Create SSH configuration"""
    return SSHConfig(
        host=host,
        port=ssh_data.get('port', 22),
        username=ssh_data.get('username', settings.ssh.default_user),
        password=ssh_data.get('password'),
        key_path=ssh_data.get('key_path'),
        key_passphrase=ssh_data.get('key_passphrase'),
        auth_method=SSHAuthMethod(ssh_data.get('auth_method', 'key')),
        timeout=ssh_data.get('timeout', settings.ssh.connection_timeout),
        allow_host_key_policy=ssh_data.get('allow_host_key_policy', True)
    )

def run_installation(installation_id: str):
    """Run installation in background thread"""
    try:
        installer = installations[installation_id]['installer']
        success = installer.install()

        installations[installation_id]['completed'] = True
        installations[installation_id]['success'] = success

        if success:
            logger.info(f"Installation {installation_id} completed successfully")
        else:
            logger.error(f"Installation {installation_id} failed")

    except Exception as e:
        logger.error(f"Installation {installation_id} failed with exception: {e}")
        installations[installation_id]['completed'] = True
        installations[installation_id]['success'] = False
        installations[installation_id]['error'] = str(e)

@installation_bp.route('/modes', methods=['GET'])
def get_installation_modes():
    """Get available installation modes"""
    modes = {
        'all_in_one': {
            'name': 'All-in-One',
            'description': 'Single-node Kubernetes cluster for development and testing',
            'requirements': ['Root access on local machine'],
            'features': ['Quick setup', 'Single node', 'Local development', 'Basic CNI'],
            'estimated_time': '10-15 minutes'
        },
        'ha_secure': {
            'name': 'HA Secure',
            'description': 'High-availability Kubernetes cluster with multiple masters',
            'requirements': ['Minimum 4 servers', 'SSH access to all nodes', 'Load balancer'],
            'features': ['High availability', 'Multi-master', 'Production ready', 'Advanced CNI'],
            'estimated_time': '30-45 minutes'
        }
    }

    return jsonify({
        'success': True,
        'modes': modes,
        'supported_versions': settings.k8s.supported_versions,
        'supported_cnis': [cni.value for cni in CNIProvider],
        'default_config': {
            'k8s_version': settings.k8s.default_version,
            'pod_cidr': settings.k8s.default_pod_cidr,
            'service_cidr': settings.k8s.default_service_cidr,
            'cni_provider': settings.k8s.default_cni
        }
    })

@installation_bp.route('/<mode>/start', methods=['POST'])
def start_installation(mode: str):
    """Start a new installation"""
    # Validate mode
    if mode not in ['all_in_one', 'ha_secure']:
        return jsonify({
            'success': False,
            'error': f'Invalid installation mode: {mode}'
        }), 400

    # Get request data
    data = request.get_json() or {}

    # Validate request data
    valid, error_message = validate_request_data(data, mode)
    if not valid:
        return jsonify({
            'success': False,
            'error': f'Validation failed: {error_message}'
        }), 400

    try:
        # Create installation configuration
        config = create_installation_config(data, mode)

        # Validate configuration
        config_errors = config.validate()
        if config_errors:
            return jsonify({
                'success': False,
                'error': f'Configuration validation failed: {"; ".join(config_errors)}'
            }), 400

        # Create installer
        installer = create_installer(config)

        # Store installation
        installations[config.installation_id] = {
            'installer': installer,
            'config': config,
            'started_at': time.time(),
            'completed': False,
            'success': False,
            'error': None
        }

        # Start installation in background thread
        thread = threading.Thread(
            target=run_installation,
            args=(config.installation_id,),
            name=f"installation-{config.installation_id}"
        )
        thread.daemon = True
        thread.start()

        installation_threads[config.installation_id] = thread

        logger.info(f"Started {mode} installation: {config.installation_id}")

        return jsonify({
            'success': True,
            'installation_id': config.installation_id,
            'message': f'Installation started successfully',
            'mode': mode,
            'estimated_duration': '10-15 minutes' if mode == 'all_in_one' else '30-45 minutes'
        }), 202

    except Exception as e:
        logger.error(f"Failed to start installation: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to start installation: {str(e)}'
        }), 500

@installation_bp.route('/<installation_id>/status', methods=['GET'])
def get_installation_status(installation_id: str):
    """Get installation status and progress"""
    if installation_id not in installations:
        return jsonify({
            'success': False,
            'error': 'Installation not found'
        }), 404

    try:
        installation = installations[installation_id]
        installer = installation['installer']

        progress = installer.get_progress()

        response = {
            'success': True,
            'installation_id': installation_id,
            'progress': progress,
            'started_at': installation['started_at'],
            'completed': installation['completed']
        }

        if installation['completed']:
            response['success_status'] = installation['success']
            if installation.get('error'):
                response['error'] = installation['error']

            # Add cluster info if successful
            if installation['success'] and hasattr(installer, 'get_cluster_info'):
                response['cluster_info'] = installer.get_cluster_info()

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error getting installation status: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@installation_bp.route('/<installation_id>/logs', methods=['GET'])
def get_installation_logs(installation_id: str):
    """Get installation logs"""
    if installation_id not in installations:
        return jsonify({
            'success': False,
            'error': 'Installation not found'
        }), 404

    try:
        installation = installations[installation_id]
        installer = installation['installer']

        progress = installer.get_progress()
        logs = progress.get('logs', [])

        # Get log level filter from query params
        level_filter = request.args.get('level', '').upper()
        if level_filter and level_filter in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            logs = [log for log in logs if log.get('level', '').upper() >= level_filter]

        # Get recent logs (last N entries)
        limit = request.args.get('limit', type=int)
        if limit:
            logs = logs[-limit:]

        return jsonify({
            'success': True,
            'installation_id': installation_id,
            'logs': logs,
            'total_logs': len(logs)
        })

    except Exception as e:
        logger.error(f"Error getting installation logs: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

@installation_bp.route('/<installation_id>/cancel', methods=['POST'])
def cancel_installation(installation_id: str):
    """Cancel running installation"""
    if installation_id not in installations:
        return jsonify({
            'success': False,
            'error': 'Installation not found'
        }), 404

    try:
        installation = installations[installation_id]

        if installation['completed']:
            return jsonify({
                'success': False,
                'error': 'Installation already completed'
            }), 400

        # Cancel the installation
        installer = installation['installer']
        installer.cancel()

        # Mark as completed
        installation['completed'] = True
        installation['success'] = False
        installation['error'] = 'Cancelled by user'

        logger.info(f"Installation {installation_id} cancelled")

        return jsonify({
            'success': True,
            'message': f'Installation {installation_id} cancelled successfully'
        }), 200

    except Exception as e:
        logger.error(f"Error cancelling installation {installation_id}: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to cancel installation: {str(e)}'
        }), 500

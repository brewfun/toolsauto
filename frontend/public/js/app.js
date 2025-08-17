/**
 * K8s Auto Installer Frontend JavaScript
 * Handles form submission, progress tracking, and real-time updates
 */

(function() {

// Global variables
let currentInstallationId = null;
let progressInterval = null;
let logWebSocket = null;

// API base URL
const API_BASE = '/api/v1';

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
    window.initializeApp();
});

function initializeApp() {
    console.log('Initializing K8s Auto Installer...');
    
    // Load initial data
    window.loadStats();
    window.loadInstallations();
    
    // Setup form handlers
    window.setupFormHandlers();
    
    // Setup mode switching
    window.setupModeSwitch();
    
    // Setup periodic refresh
    setInterval(window.loadStats, 30000); // Refresh stats every 30 seconds
    setInterval(window.loadInstallations, 15000); // Refresh installations every 15 seconds
}

function setupFormHandlers() {
    const form = document.getElementById('installation-form');
    if (form) {
        form.addEventListener('submit', window.handleFormSubmit);
    }
}

function setupModeSwitch() {
    const modeRadios = document.querySelectorAll('input[name="mode"]');
    modeRadios.forEach(radio => {
        radio.addEventListener('change', window.handleModeChange);
    });
}

function handleModeChange(event) {
    const mode = event.target.value;
    const haConfig = document.getElementById('ha-config');
    
    if (mode === 'ha_secure') {
        haConfig.classList.remove('d-none');
        // Add default nodes for HA mode
        if (document.getElementById('nodes-config').children.length === 0) {
            window.addDefaultHANodes();
        }
    } else {
        haConfig.classList.add('d-none');
    }
}

function addDefaultHANodes() {
    // Add default nodes for HA setup
    const defaultNodes = [
        { role: 'loadbalancer', host: '', ssh_user: 'ubuntu' },
        { role: 'master', host: '', ssh_user: 'ubuntu' },
        { role: 'master', host: '', ssh_user: 'ubuntu' },
        { role: 'master', host: '', ssh_user: 'ubuntu' }
    ];
    
    defaultNodes.forEach(node => {
        window.addNodeConfig(node);
    });
}

function addNodeConfig(defaultValues = {}) {
    const nodesContainer = document.getElementById('nodes-config');
    const nodeIndex = nodesContainer.children.length;
    
    const nodeDiv = document.createElement('div');
    nodeDiv.className = 'card mb-2';
    nodeDiv.innerHTML = `
        <div class="card-body">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <h6 class="mb-0">Node ${nodeIndex + 1}</h6>
                <button type="button" class="btn btn-outline-danger btn-sm" onclick="window.removeNodeConfig(this)">
                    <i class="bi bi-trash"></i>
                </button>
            </div>
            <div class="row g-2">
                <div class="col-md-3">
                    <label class="form-label">Role</label>
                    <select class="form-select" name="nodes[${nodeIndex}][role]" required>
                        <option value="master" ${defaultValues.role === 'master' ? 'selected' : ''}>Master</option>
                        <option value="worker" ${defaultValues.role === 'worker' ? 'selected' : ''}>Worker</option>
                        <option value="loadbalancer" ${defaultValues.role === 'loadbalancer' ? 'selected' : ''}>Load Balancer</option>
                    </select>
                </div>
                <div class="col-md-3">
                    <label class="form-label">Host IP</label>
                    <input type="text" class="form-control" name="nodes[${nodeIndex}][host]" 
                           placeholder="192.168.1.10" value="${defaultValues.host || ''}" required>
                </div>
                <div class="col-md-2">
                    <label class="form-label">SSH User</label>
                    <input type="text" class="form-control" name="nodes[${nodeIndex}][ssh_user]" 
                           value="${defaultValues.ssh_user || 'ubuntu'}" required>
                </div>
                <div class="col-md-4">
                    <label class="form-label">SSH Key Path</label>
                    <input type="text" class="form-control" name="nodes[${nodeIndex}][ssh_key_path]" 
                           placeholder="/path/to/private/key" value="${defaultValues.ssh_key_path || ''}">
                    <small class="text-muted">Leave empty to use password authentication</small>
                </div>
            </div>
        </div>
    `;
    
    nodesContainer.appendChild(nodeDiv);
}

function removeNodeConfig(button) {
    const nodeCard = button.closest('.card');
    nodeCard.remove();
    
    // Update node indices
    const nodesContainer = document.getElementById('nodes-config');
    Array.from(nodesContainer.children).forEach((card, index) => {
        const title = card.querySelector('h6');
        title.textContent = `Node ${index + 1}`;
        
        // Update form field names
        const inputs = card.querySelectorAll('input, select');
        inputs.forEach(input => {
            const name = input.getAttribute('name');
            if (name && name.includes('[')) {
                const newName = name.replace(/[\[]\d+[\]]/, `[${index}]`);
                input.setAttribute('name', newName);
            }
        });
    });
}

async function handleFormSubmit(event) {
    event.preventDefault();
    
    const formData = new FormData(event.target);
    const config = {};
    
    // Basic configuration
    config.mode = formData.get('mode');
    config.k8s_version = formData.get('k8s_version');
    config.cni_provider = formData.get('cni_provider');
    config.pod_cidr = formData.get('pod_cidr');
    config.service_cidr = formData.get('service_cidr');
    
    // Advanced options
    config.enable_rbac = formData.has('enable_rbac');
    config.enable_network_policies = formData.has('enable_network_policies');
    config.enable_monitoring = formData.has('enable_monitoring');
    
    // HA mode configuration
    if (config.mode === 'ha_secure') {
        config.nodes = [];
        const nodesContainer = document.getElementById('nodes-config');
        
        Array.from(nodesContainer.children).forEach((card, index) => {
            const node = {
                role: formData.get(`nodes[${index}][role]`), 
                host: formData.get(`nodes[${index}][host]`),
                ssh_user: formData.get(`nodes[${index}][ssh_user]`),
                ssh_key_path: formData.get(`nodes[${index}][ssh_key_path]`) || null
            };
            
            if (node.role && node.host) {
                config.nodes.push(node);
            }
        });
        
        if (config.nodes.length < 4) {
            window.showAlert('HA mode requires at least 4 nodes (1 load balancer + 3 masters)', 'danger');
            return;
        }
    }
    
    // Validate configuration
    try {
        const validation = await fetch(`${API_BASE}/installation/validate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });
        
        const validationResult = await validation.json();
        
        if (!validation.ok || !validationResult.valid) {
            window.showAlert(`Configuration validation failed: ${validationResult.error}`, 'danger');
            return;
        }
        
    } catch (error) {
        window.showAlert(`Validation error: ${error.message}`, 'danger');
        return;
    }
    
    // Start installation
    try {
        const response = await fetch(`${API_BASE}/installation/start`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            currentInstallationId = result.installation_id;
            window.showProgressModal();
            window.startProgressTracking();
        } else {
            window.showAlert(`Installation failed to start: ${result.error}`, 'danger');
        }
        
    } catch (error) {
        window.showAlert(`Error starting installation: ${error.message}`, 'danger');
    }
}

function showProgressModal() {
    const modal = new bootstrap.Modal(document.getElementById('progress-modal'));
    modal.show();
    
    // Reset progress
    window.updateProgressBar(0, 'Starting installation...');
    document.getElementById('installation-id').textContent = currentInstallationId;
    document.getElementById('current-step').textContent = '-';
    document.getElementById('installation-duration').textContent = '-';
    document.getElementById('log-content').textContent = '';
    
    // Show cancel button, hide close button
    document.getElementById('cancel-btn').classList.remove('d-none');
    document.getElementById('close-btn').classList.add('d-none');
}

function startProgressTracking() {
    if (progressInterval) {
        clearInterval(progressInterval);
    }
    
    progressInterval = setInterval(async () => {
        if (!currentInstallationId) return;
        
        try {
            const response = await fetch(`${API_BASE}/installation/${currentInstallationId}/status`);
            const status = await response.json();
            
            if (response.ok) {
                window.updateProgress(status);
                
                // Check if installation completed
                if (status.completed) {
                    clearInterval(progressInterval);
                    window.handleInstallationComplete(status);
                }
            } else {
                console.error('Failed to fetch status:', status.error);
            }
            
        } catch (error) {
            console.error('Progress tracking error:', error);
        }
    }, 2000); // Check every 2 seconds
    
    // Also load logs periodically
    window.startLogTracking();
}

function startLogTracking() {
    setInterval(async () => {
        if (!currentInstallationId) return;
        
        try {
            const response = await fetch(`${API_BASE}/installation/${currentInstallationId}/logs?limit=50`);
            const result = await response.json();
            
            if (response.ok) {
                window.updateLogs(result.logs);
            }
            
        } catch (error) {
            console.error('Log tracking error:', error);
        }
    }, 3000); // Check logs every 3 seconds
}

function updateProgress(status) {
    // Update progress bar
    const percentage = Math.round(status.progress_percentage || 0);
    window.updateProgressBar(percentage, `Step ${status.current_step || 0}/${status.total_steps || 0}`);
    
    // Update details
    document.getElementById('current-step').textContent = `${status.current_step || 0}/${status.total_steps || 0}`;
    
    // Update duration
    if (status.duration) {
        const duration = window.formatDuration(status.duration);
        document.getElementById('installation-duration').textContent = duration;
    }
    
    // Update status indicator
    const progressText = document.getElementById('progress-text');
    switch (status.status) {
        case 'pending':
            progressText.textContent = 'Preparing installation...';
            break;
        case 'validating':
            progressText.textContent = 'Validating configuration...';
            break;
        case 'installing':
            progressText.textContent = 'Installing Kubernetes...';
            break;
        case 'configuring':
            progressText.textContent = 'Configuring cluster...';
            break;
        case 'verifying':
            progressText.textContent = 'Verifying installation...';
            break;
        default:
            progressText.textContent = status.status;
    }
}

function updateProgressBar(percentage, text) {
    const progressBar = document.getElementById('progress-bar');
    const progressPercentage = document.getElementById('progress-percentage');
    
    progressBar.style.width = `${percentage}%`;
    progressBar.setAttribute('aria-valuenow', percentage);
    progressPercentage.textContent = `${percentage}%`;
    
    if (text) {
        document.getElementById('progress-text').textContent = text;
    }
}

function updateLogs(logs) {
    const logContent = document.getElementById('log-content');
    const logContainer = document.getElementById('log-container');
    
    // Format and append new logs
    let logText = '';
    logs.forEach(log => {
        const timestamp = new Date(log.timestamp * 1000).toLocaleTimeString();
        const level = log.level.toUpperCase();
        const message = log.message;
        
        let levelColor = '';
        switch (level) {
            case 'ERROR':
                levelColor = 'text-danger';
                break;
            case 'WARNING':
                levelColor = 'text-warning';
                break;
            case 'INFO':
                levelColor = 'text-primary';
                break;
            case 'DEBUG':
                levelColor = 'text-muted';
                break;
        }
        
        logText += `[${timestamp}] <span class="${levelColor}">[${level}]</span> ${message}\n`;
    });
    
    logContent.innerHTML = logText;
    
    // Auto-scroll to bottom
    logContainer.scrollTop = logContainer.scrollHeight;
}

function handleInstallationComplete(status) {
    // Hide cancel button, show close button
    document.getElementById('cancel-btn').classList.add('d-none');
    document.getElementById('close-btn').classList.remove('d-none');
    
    // Update progress to 100%
    window.updateProgressBar(100, 'Installation complete');
    
    // Close progress modal and show result modal
    setTimeout(() => {
        const progressModal = bootstrap.Modal.getInstance(document.getElementById('progress-modal'));
        progressModal.hide();
        
        window.showResultModal(status);
    }, 2000);
}

function showResultModal(status) {
    const modal = document.getElementById('result-modal');
    const header = document.getElementById('result-header');
    const title = document.getElementById('result-title');
    const content = document.getElementById('result-content');
    const downloadBtn = document.getElementById('download-kubeconfig');
    
    if (status.success) {
        // Success
        header.className = 'modal-header bg-success text-white';
        title.innerHTML = '<i class="bi bi-check-circle"></i> Installation Successful!';
        
        content.innerHTML = `
            <div class="alert alert-success">
                <h5><i class="bi bi-check-circle"></i> Kubernetes cluster installed successfully!</h5>
                <p>Your cluster is now ready for use. Installation took ${window.formatDuration(status.duration)}.</p>
            </div>
            
            <div class="row g-3">
                <div class="col-md-6">
                    <h6>Installation Details</h6>
                    <ul class="list-unstyled">
                        <li><strong>Mode:</strong> ${status.mode}</li>
                        <li><strong>Installation ID:</strong> ${status.installation_id}</li>
                        <li><strong>Duration:</strong> ${window.formatDuration(status.duration)}</li>
                    </ul>
                </div>
                <div class="col-md-6">
                    <h6>Next Steps</h6>
                    <ol>
                        <li>Download the kubeconfig file</li>
                        <li>Set KUBECONFIG environment variable</li>
                        <li>Test cluster access: <code>kubectl get nodes</code></li>
                        <li>Deploy your applications</li>
                    </ol>
                </div>
            </div>
            
            <div class="mt-3">
                <h6>Quick Commands</h6>
                <div class="bg-light p-3 rounded">
                    <code>export KUBECONFIG=~/kubeconfig-${status.installation_id}.yaml</code><br>
                    <code>kubectl get nodes</code><br>
                    <code>kubectl get pods -A</code>
                </div>
            </div>
        `;
        
        downloadBtn.classList.remove('d-none');
        downloadBtn.onclick = () => window.downloadKubeconfig(status.installation_id);
        
    } else {
        // Failure
        header.className = 'modal-header bg-danger text-white';
        title.innerHTML = '<i class="bi bi-x-circle"></i> Installation Failed';
        
        content.innerHTML = `
            <div class="alert alert-danger">
                <h5><i class="bi bi-x-circle"></i> Installation failed</h5>
                <p>The installation encountered an error and could not complete.</p>
                ${status.error_message ? `<p><strong>Error:</strong> ${status.error_message}</p>` : ''}
            </div>
            
            <div class="mb-3">
                <h6>Troubleshooting Steps</h6>
                <ol>
                    <li>Check the installation logs above for specific errors</li>
                    <li>Verify system requirements are met</li>
                    <li>Ensure sufficient disk space and memory</li>
                    <li>Check network connectivity</li>
                    <li>Try the installation again with corrected configuration</li>
                </ol>
            </div>
            
            <div>
                <h6>Get Help</h6>
                <p>If the problem persists:</p>
                <ul>
                    <li>Check the documentation for common issues</li>
                    <li>Review system logs: <code>journalctl -u kubelet</code></li>
                    <li>Contact support with installation ID: <code>${status.installation_id}</code></li>
                </ul>
            </div>
        `;
        
        downloadBtn.classList.add('d-none');
    }
    
    const resultModal = new bootstrap.Modal(modal);
    resultModal.show();
    
    // Refresh installations list
    window.loadInstallations();
}

async function cancelInstallation() {
    if (!currentInstallationId) return;
    
    try {
        const response = await fetch(`${API_BASE}/installation/${currentInstallationId}/cancel`, {
            method: 'POST'
        });
        
        if (response.ok) {
            window.showAlert('Installation cancelled', 'warning');
            
            // Stop tracking
            if (progressInterval) {
                clearInterval(progressInterval);
            }
            
            // Hide progress modal
            const progressModal = bootstrap.Modal.getInstance(document.getElementById('progress-modal'));
            progressModal.hide();
            
            currentInstallationId = null;
            
            // Refresh installations list
            window.loadInstallations();
            
        } else {
            const result = await response.json();
            window.showAlert(`Failed to cancel installation: ${result.error}`, 'danger');
        }
        
    } catch (error) {
        window.showAlert(`Error cancelling installation: ${error.message}`, 'danger');
    }
}

async function downloadKubeconfig(installationId) {
    try {
        const response = await fetch(`${API_BASE}/installation/${installationId}/kubeconfig`);
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `kubeconfig-${installationId}.yaml`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } else {
            const result = await response.json();
            window.showAlert(`Failed to download kubeconfig: ${result.error}`, 'danger');
        }
        
    } catch (error) {
        window.showAlert(`Error downloading kubeconfig: ${error.message}`, 'danger');
    }
}

async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/installation/stats`);
        const stats = await response.json();
        
        if (response.ok) {
            window.updateStats(stats);
        }
        
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

function updateStats(stats) {
    document.getElementById('total-installations').textContent = stats.total_installations || 0;
    
    // Count running installations
    const running = Object.values(stats.status_breakdown || {})
        .reduce((sum, count) => sum + (count || 0), 0) - (stats.completed_installations?.total_completed || 0);
    document.getElementById('running-installations').textContent = Math.max(0, running);
    
    document.getElementById('successful-installations').textContent = stats.completed_installations?.successful || 0;
    document.getElementById('failed-installations').textContent = stats.completed_installations?.failed || 0;
}

async function loadInstallations() {
    try {
        const response = await fetch(`${API_BASE}/installation/list`);
        const result = await response.json();
        
        if (response.ok) {
            window.updateInstallationsTable(result.installations || []);
        }
        
    } catch (error) {
        console.error('Failed to load installations:', error);
    }
}

function updateInstallationsTable(installations) {
    const tbody = document.getElementById('installations-table-body');
    
    if (installations.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center text-muted">
                    <i class="bi bi-inbox"></i>
                    No installations found
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = installations.map(installation => {
        const statusBadge = window.getStatusBadge(installation.status, installation.success);
        const progressBar = window.getProgressBar(installation.progress_percentage || 0);
        const duration = installation.duration ? window.formatDuration(installation.duration) : '-';
        const actions = window.getActionButtons(installation);
        
        return `
            <tr>
                <td>
                    <span class="font-monospace">${installation.installation_id}</span>
                </td>
                <td>
                    <span class="badge bg-secondary">${installation.mode.replace('_', '-')}</span>
                </td>
                <td>${statusBadge}</td>
                <td>${progressBar}</td>
                <td>${duration}</td>
                <td>${actions}</td>
            </tr>
        `;
    }).join('');
}

function getStatusBadge(status, success) {
    let badgeClass = 'bg-secondary';
    let icon = 'bi-hourglass-split';
    
    switch (status) {
        case 'pending':
            badgeClass = 'bg-secondary';
            icon = 'bi-hourglass-split';
            break;
        case 'installing':
        case 'configuring':
        case 'verifying':
            badgeClass = 'bg-primary';
            icon = 'bi-arrow-repeat';
            break;
        case 'success':
            badgeClass = 'bg-success';
            icon = 'bi-check-circle';
            break;
        case 'failed':
            badgeClass = 'bg-danger';
            icon = 'bi-x-circle';
            break;
        case 'cancelled':
            badgeClass = 'bg-warning';
            icon = 'bi-stop-circle';
            break;
    }
    
    // Override for completed installations
    if (status === 'success' || (success === true)) {
        badgeClass = 'bg-success';
        icon = 'bi-check-circle';
        status = 'success';
    } else if (success === false && status !== 'cancelled') {
        badgeClass = 'bg-danger';
        icon = 'bi-x-circle';
        status = 'failed';
    }
    
    return `<span class="badge ${badgeClass}"><i class=" ${icon}"></i> ${status}</span>`;
}

function getProgressBar(percentage) {
    if (percentage === 0) {
        return '<span class="text-muted">-</span>';
    }
    
    return `
        <div class="progress" style="width: 80px;">
            <div class="progress-bar" role="progressbar" style="width: ${percentage}%" 
                 aria-valuenow="${percentage}" aria-valuemin="0" aria-valuemax="100">
            </div>
        </div>
        <small>${Math.round(percentage)}%</small>
    `;
}

function getActionButtons(installation) {
    const buttons = [];
    
    // View details button
    buttons.push(`
        <button class="btn btn-outline-primary btn-sm" onclick="window.viewInstallationDetails('${installation.installation_id}')" title="View Details">
            <i class="bi bi-eye"></i>
        </button>
    `);
    
    // Download kubeconfig if successful
    if (installation.success === true) {
        buttons.push(`
            <button class="btn btn-outline-success btn-sm" onclick="window.downloadKubeconfig('${installation.installation_id}')" title="Download Kubeconfig">
                <i class="bi bi-download"></i>
            </button>
        `);
    }
    
    // Cancel if running
    if (!installation.completed) {
        buttons.push(`
            <button class="btn btn-outline-warning btn-sm" onclick="window.cancelInstallationById('${installation.installation_id}')" title="Cancel">
                <i class="bi bi-stop-circle"></i>
            </button>
        `);
    }
    
    // Delete button
    buttons.push(`
        <button class="btn btn-outline-danger btn-sm" onclick="window.deleteInstallation('${installation.installation_id}')" title="Delete">
            <i class="bi bi-trash"></i>
        </button>
    `);
    
    return buttons.join(' ');
}

async function viewInstallationDetails(installationId) {
    // This could open a modal with detailed installation information
    // For now, just show an alert with basic info
    try {
        const response = await fetch(`${API_BASE}/installation/${installationId}/status`);
        const installation = await response.json();
        
        if (response.ok) {
            const details = `
Installation ID: ${installation.installation_id}
Mode: ${installation.mode}
Status: ${installation.status}
Progress: ${Math.round(installation.progress_percentage || 0)}%
Duration: ${installation.duration ? window.formatDuration(installation.duration) : 'N/A'}
${installation.error_message ? `Error: ${installation.error_message}` : ''}
            `;
            
            window.alert(details);
        }
        
    } catch (error) {
        window.showAlert(`Error loading installation details: ${error.message}`, 'danger');
    }
}

async function cancelInstallationById(installationId) {
    if (!window.confirm('Are you sure you want to cancel this installation?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/installation/${installationId}/cancel`, {
            method: 'POST'
        });
        
        if (response.ok) {
            window.showAlert('Installation cancelled', 'warning');
            
            // Stop tracking
            if (progressInterval) {
                clearInterval(progressInterval);
            }
            
            // Hide progress modal
            const progressModal = bootstrap.Modal.getInstance(document.getElementById('progress-modal'));
            progressModal.hide();
            
            currentInstallationId = null;
            
            // Refresh installations list
            window.loadInstallations();
            
        } else {
            const result = await response.json();
            window.showAlert(`Failed to cancel installation: ${result.error}`, 'danger');
        }
        
    } catch (error) {
        window.showAlert(`Error cancelling installation: ${error.message}`, 'danger');
    }
}

async function deleteInstallation(installationId) {
    if (!window.confirm('Are you sure you want to delete this installation record?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/installation/${installationId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            window.showAlert('Installation deleted', 'info');
            window.loadInstallations();
            window.loadStats();
        } else {
            const result = await response.json();
            window.showAlert(`Failed to delete installation: ${result.error}`, 'danger');
        }
        
    } catch (error) {
        window.showAlert(`Error deleting installation: ${error.message}`, 'danger');
    }
}

// Utility functions
function formatDuration(seconds) {
    if (seconds < 60) {
        return `${Math.round(seconds)}s`;
    } else if (seconds < 3600) {
        return `${Math.round(seconds / 60)}m ${Math.round(seconds % 60)}s`;
    }
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.round((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
}

function showAlert(message, type = 'info') {
    // Create alert element
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    // Add to page
    const container = document.querySelector('.container');
    container.insertBefore(alertDiv, container.firstChild);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

function scrollToInstall() {
    document.getElementById('install-section').scrollIntoView({
        behavior: 'smooth'
    });
}

function clearLogs() {
    document.getElementById('log-content').textContent = '';
}

// Attach functions to window object for testability and global access
window.initializeApp = initializeApp;
window.setupFormHandlers = setupFormHandlers;
window.setupModeSwitch = setupModeSwitch;
window.handleModeChange = handleModeChange;
window.addDefaultHANodes = addDefaultHANodes;
window.addNodeConfig = addNodeConfig;
window.removeNodeConfig = removeNodeConfig;
window.handleFormSubmit = handleFormSubmit;
window.showProgressModal = showProgressModal;
window.startProgressTracking = startProgressTracking;
window.startLogTracking = startLogTracking;
window.updateProgress = updateProgress;
window.updateProgressBar = updateProgressBar;
window.updateLogs = updateLogs;
window.handleInstallationComplete = handleInstallationComplete;
window.showResultModal = showResultModal;
window.cancelInstallation = cancelInstallation;
window.downloadKubeconfig = downloadKubeconfig;
window.loadStats = loadStats;
window.updateStats = updateStats;
window.loadInstallations = loadInstallations;
window.updateInstallationsTable = updateInstallationsTable;
window.getStatusBadge = getStatusBadge;
window.getProgressBar = getProgressBar;
window.getActionButtons = getActionButtons;
window.viewInstallationDetails = viewInstallationDetails;
window.cancelInstallationById = cancelInstallationById;
window.deleteInstallation = deleteInstallation;
window.formatDuration = formatDuration;
window.showAlert = showAlert;
window.scrollToInstall = scrollToInstall;
window.clearLogs = clearLogs;

})();

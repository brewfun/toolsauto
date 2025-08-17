# Kubernetes Auto Installer API Documentation

This document describes the RESTful API endpoints for managing Kubernetes cluster installations.

## Base URL
`/api/v1/installation`

## Authentication
Currently, no authentication is required for these API endpoints. All endpoints are publicly accessible.

## Endpoints

### 1. Get Available Installation Modes
`GET /api/v1/installation/modes`

**Description:** Retrieves a list of supported Kubernetes installation modes, along with supported Kubernetes versions, CNI providers, and default configuration settings.

**Response (200 OK):**
```json
{
  "success": true,
  "modes": {
    "all_in_one": {
      "name": "All-in-One",
      "description": "Single-node Kubernetes cluster for development and testing",
      "requirements": ["Root access on local machine"],
      "features": ["Quick setup", "Single node", "Local development", "Basic CNI"],
      "estimated_time": "10-15 minutes"
    },
    "ha_secure": {
      "name": "HA Secure",
      "description": "High-availability Kubernetes cluster with multiple masters",
      "requirements": ["Minimum 4 servers", "SSH access to all nodes", "Load balancer"],
      "features": ["High availability", "Multi-master", "Production ready", "Advanced CNI"],
      "estimated_time": "30-45 minutes"
    }
  },
  "supported_versions": [
    "1.30",
    "1.29",
    "1.28"
  ],
  "supported_cnis": [
    "cilium",
    "calico",
    "flannel"
  ],
  "default_config": {
    "k8s_version": "1.30",
    "pod_cidr": "10.244.0.0/16",
    "service_cidr": "10.96.0.0/12",
    "cni_provider": "cilium"
  }
}
```

### 2. Start a New Installation
`POST /api/v1/installation/{mode}/start`

**Description:** Initiates a new Kubernetes cluster installation based on the specified mode and configuration.

**Path Parameters:**
- `mode` (string, required): The installation mode. Allowed values: `all_in_one`, `ha_secure`.

**Request Body (application/json):**

**For `all_in_one` mode:**
```json
{
  "k8s_version": "1.30",
  "pod_cidr": "10.244.0.0/16",
  "service_cidr": "10.96.0.0/12",
  "cni_provider": "cilium",
  "cluster_name": "my-single-node-k8s",
  "enable_rbac": true,
  "enable_monitoring": false
}
```

**For `ha_secure` mode:**
```json
{
  "k8s_version": "1.30",
  "masters": [
    "192.168.1.10",
    "192.168.1.11",
    "192.168.1.12"
  ],
  "load_balancer": "192.168.1.20",
  "workers": [
    "192.168.1.30",
    "192.168.1.31"
  ],
  "ssh_config": {
    "username": "ubuntu",
    "auth_method": "key",
    "key_path": "/home/user/.ssh/id_rsa",
    "key_passphrase": "mysecret",
    ""port": 22,
    "timeout": 30
  },
  "pod_cidr": "10.244.0.0/16",
  "service_cidr": "10.96.0.0/12",
  "cni_provider": "calico",
  "cluster_name": "my-ha-k8s",
  "enable_rbac": true
}
```

**Response (202 Accepted):**
```json
{
  "success": true,
  "installation_id": "a1b2c3d4",
  "message": "Installation started successfully",
  "mode": "all_in_one",
  "estimated_duration": "10-15 minutes"
}
```

**Error Responses (400 Bad Request):**
```json
{
  "success": false,
  "error": "Validation failed: Missing required field: masters"
}
```

### 3. Get Installation Status
`GET /api/v1/installation/{installation_id}/status`

**Description:** Retrieves the current status and progress of a specific Kubernetes installation.

**Path Parameters:**
- `installation_id` (string, required): The unique ID of the installation.

**Response (200 OK):**
```json
{
  "success": true,
  "installation_id": "a1b2c3d4",
  "progress": {
    "installation_id": "a1b2c3d4",
    "current_step": 3,
    "total_steps": 9,
    "status": "installing",
    "progress_percentage": 33.33,
    "duration": 120.5,
    "start_time": 1678886400.0,
    "end_time": null,
    "error_message": null,
    "step_results": [
      { "step_name": "System Configuration", "success": true, "duration": 10.0, "error_message": null, "output": null, "host": null },
      { "step_name": "Install Kubernetes Components", "success": true, "duration": 60.0, "error_message": null, "output": null, "host": null }
    ]
  },
  "started_at": 1678886400.0,
  "completed": false
}
```

**Response (200 OK) - Completed Installation:**
```json
{
  "success": true,
  "installation_id": "a1b2c3d4",
  "progress": { /* ... same as above ... */ },
  "started_at": 1678886400.0,
  "completed": true,
  "success_status": true,
  "cluster_info": {
    "mode": "all-in-one",
    "kubernetes_version": "1.30",
    "cni_provider": "cilium",
    "pod_cidr": "10.244.0.0/16",
    "service_cidr": "10.96.0.0/12",
    "kubeconfig_path": "/home/user/.kube/config-a1b2c3d4",
    "installation_id": "a1b2c3d4",
    "nodes": [
      {
        "name": "localhost",
        "status": "Ready",
        "roles": "control-plane,master",
        "age": "1d",
        "version": "v1.30.0",
        "internal_ip": "127.0.0.1"
      }
    ],
    "pod_count_by_namespace": {
      "kube-system": 20,
      "default": 3
    }
  }
}
```

**Error Responses (404 Not Found):**
```json
{
  "success": false,
  "error": "Installation not found"
}
```

### 4. Get Installation Logs
`GET /api/v1/installation/{installation_id}/logs`

**Description:** Retrieves the detailed logs for a specific Kubernetes installation.

**Path Parameters:**
- `installation_id` (string, required): The unique ID of the installation.

**Query Parameters:**
- `level` (string, optional): Filter logs by minimum log level. Allowed values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.
- `limit` (integer, optional): The maximum number of recent log entries to retrieve.

**Response (200 OK):**
```json
{
  "success": true,
  "installation_id": "a1b2c3d4",
  "logs": [
    {
      "timestamp": "2023-03-15T10:00:00.123456",
      "level": "INFO",
      "message": "Starting K8s Auto Installer API server",
      "source": "backend.main"
    },
    {
      "timestamp": "2023-03-15T10:00:05.789012",
      "level": "STEP_START",
      "message": "Running pre-installation checks...",
      "source": "backend.core.installer"
    }
  ],
  "total_logs": 150
}
```

**Error Responses (404 Not Found):**
```json
{
  "success": false,
  "error": "Installation not found"
}
```

### 5. Cancel Running Installation
`POST /api/v1/installation/{installation_id}/cancel`

**Description:** Requests to cancel a currently running Kubernetes installation.

**Path Parameters:**
- `installation_id` (string, required): The unique ID of the installation to cancel.

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Installation a1b2c3d4 cancelled successfully"
}
```

**Error Responses (400 Bad Request):**
```json
{
  "success": false,
  "error": "Installation already completed"
}
```

**Error Responses (404 Not Found):**
```json
{
  "success": false,
  "error": "Installation not found"
}
```

## General Error Responses

In addition to specific error responses per endpoint, the API may return the following general HTTP error codes:

-   `400 Bad Request`: The request was invalid or cannot be served (e.g., missing required fields, invalid data format).
-   `404 Not Found`: The requested resource was not found.
-   `500 Internal Server Error`: An unexpected error occurred on the server side.

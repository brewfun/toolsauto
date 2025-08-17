# Kubernetes Auto Installer Architecture

## Overview

The Kubernetes Auto Installer is a tool designed to simplify the deployment of Kubernetes clusters. It provides a web-based API for users to initiate and monitor Kubernetes installations, abstracting away the complexities of setting up a cluster. The system is built with a modular architecture, allowing for easy extension to support different installation modes, cloud providers, and additional DevOps features.

## Core Components

### 1. Flask API (`backend/api/routes/installation.py`)

This is the entry point for user interaction. It exposes RESTful endpoints for:
- Retrieving available installation modes and supported configurations.
- Starting new Kubernetes cluster installations.
- Monitoring the status and progress of ongoing installations.
- Retrieving detailed logs for specific installations.
- Cancelling running installations.

The API handles request validation, delegates installation logic to the core installer components, and provides real-time updates to the frontend.

### 2. Installation Core (`backend/core/installer.py`)

This module contains the fundamental logic for Kubernetes installations. It defines:

-   **`BaseInstaller` (Abstract Class):** Provides a common framework for all installation types. It handles:
    -   Pre-installation checks (system requirements, connectivity, prerequisites).
    -   Execution of defined installation steps with retry mechanisms.
    -   Post-installation verification (cluster access, node readiness, system pods, CNI).
    -   Progress tracking and cancellation logic.
-   **`InstallationConfig`:** A dataclass representing the configuration parameters for a Kubernetes installation (e.g., K8s version, CIDRs, CNI provider, node details, SSH configuration).
-   **`NodeConfig`:** A dataclass defining the properties of a single Kubernetes node (host, role, SSH configuration).
-   **`InstallationStep`:** A dataclass representing a single, executable step in the installation process, including its name, description, and the function to execute.
-   **`InstallationProgress`:** A dataclass for tracking the overall progress of an installation, including current step, total steps, status, duration, and results of individual steps.
-   **`create_installer` (Factory Function):** A function that dynamically creates the appropriate installer instance (e.g., `AllInOneInstaller`, `HASecureInstaller`) based on the `InstallationMode` specified in the `InstallationConfig`.

### 3. Specific Installers (`backend/scripts/`)

Concrete implementations of `BaseInstaller` for different Kubernetes installation modes:

-   **`AllInOneInstaller` (`backend/scripts/all_in_one/installer.py`):** Handles the installation of a single-node Kubernetes cluster. It defines the specific sequence of steps required for an all-in-one setup, such as:
    -   System configuration (swap, kernel modules, sysctl).
    -   Installation of Kubernetes components (kubeadm, kubelet, kubectl).
    -   Container runtime installation (containerd).
    -   Cluster initialization with `kubeadm init`.
    -   `kubectl` configuration for user access.
    -   Removal of master taint.
    -   CNI (Container Network Interface) installation (Cilium, Calico, Flannel).
    -   Storage class configuration.
    -   Waiting for system readiness.

### 4. SSH Manager (`backend/core/ssh_manager.py`)

Responsible for managing SSH connections to remote nodes. It provides functionalities for:
-   Adding and removing SSH host configurations.
-   Testing SSH connectivity.
-   Executing commands on remote hosts.
-   Retrieving system information from remote hosts.

### 5. Utilities (`backend/utils/`)

Contains various helper functions and modules used across the application:
-   **`helpers.py`:** Provides general utility functions such as IP/CIDR validation, command execution (`run_command`), file operations (read/write, YAML/JSON load/save), string manipulation, and Kubernetes-specific validations.
-   **`logger.py`:** Manages application logging, including custom log levels and installation-specific log streams.

### 6. Configuration (`backend/config/settings.py`)

A centralized module for managing application settings, including Kubernetes defaults, security settings, storage paths, and Flask application configurations. Settings are loaded from environment variables and `.env` files.

## Installation Flow (K8s Auto-Install Feature)

1.  **User Request:** The user initiates an installation via a `POST` request to `/api/v1/installation/{mode}/start` with the desired configuration.
2.  **API Validation:** The Flask API validates the incoming request data against predefined schemas.
3.  **Installer Creation:** The `create_installer` factory function instantiates the appropriate `BaseInstaller` subclass (e.g., `AllInOneInstaller`) based on the requested `mode`.
4.  **Background Execution:** The installation process is started in a separate background thread to avoid blocking the API response.
5.  **Pre-installation Checks:** The installer performs a series of checks:
    -   Validates the `InstallationConfig`.
    -   Verifies system requirements (e.g., root privileges, disk space).
    -   Tests network connectivity to all specified nodes.
    -   Checks for necessary prerequisites on each node.
6.  **Step-by-Step Installation:** The installer executes a predefined sequence of `InstallationStep`s. Each step involves running commands (locally or via SSH), configuring services, and waiting for conditions to be met.
7.  **Progress Tracking:** The `InstallationProgress` object is continuously updated, and logs are streamed, allowing the frontend to display real-time status.
8.  **Post-installation Verification:** After all steps are completed, the installer performs final checks to ensure the Kubernetes cluster is fully functional (e.g., cluster access, node readiness, system pods, CNI).
9.  **Completion/Failure:** The installation concludes with a `SUCCESS` or `FAILED` status. If successful, cluster access information (like kubeconfig path) is made available.

## Future Enhancements

This architecture provides a solid foundation for expanding the tool's capabilities. Future features may include:
-   **CI/CD Integration:** Automating deployment pipelines for applications on the newly provisioned clusters.
-   **Monitoring & Alerting:** Integrating with monitoring solutions to provide insights into cluster health and performance.
-   **Multi-Cloud Support:** Extending installers to deploy Kubernetes on various cloud providers (AWS, Azure, GCP).
-   **Advanced Networking & Storage:** Support for more complex CNI and storage solutions.
-   **UI Enhancements:** A more interactive and feature-rich frontend for managing installations.

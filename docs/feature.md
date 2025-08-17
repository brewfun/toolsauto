# Features of K8s Auto Installer

This document outlines the current and planned features for the K8s Auto Installer project.

## Current Features (Kubernetes Auto-Installation)

The current version of the K8s Auto Installer focuses on providing a streamlined experience for deploying Kubernetes clusters. Key features include:

*   **Basic Kubernetes Cluster Deployment:**
    *   Support for `all_in_one` (single-node) and `ha_secure` (multi-master high-availability) installation modes.
    *   Automated setup of essential Kubernetes components.
    *   Selection of Kubernetes versions (e.g., 1.30, 1.29, 1.28).
    *   Choice of Container Network Interface (CNI) providers (e.g., Cilium, Calico, Flannel).
    *   Configurable Pod and Service CIDR ranges.
    *   Optional RBAC (Role-Based Access Control) and Network Policies.
*   **Installation Progress Tracking:**
    *   Real-time updates on installation status and progress percentage.
    *   Detailed step-by-step logs for troubleshooting.
    *   Installation duration tracking.
*   **Management and Monitoring:**
    *   Ability to view a list of past and ongoing installations.
    *   Option to cancel running installations.
    *   Download of generated Kubeconfig files for cluster access.
    *   Basic statistics on total, running, successful, and failed installations.

## Planned Advanced Kubernetes Features

We are continuously working to enhance the Kubernetes installation capabilities. Future advanced features will include:

*   **Advanced Cluster Customization:**
    *   More granular control over Kubernetes component versions and configurations.
    *   Support for custom certificates and external CAs.
    *   Integration with various cloud providers for automated resource provisioning.
*   **Storage Integration:**
    *   Automated setup and configuration of Persistent Volumes (PVs) and Persistent Volume Claims (PVCs) with different storage classes.
    *   Support for popular storage solutions (e.g., Rook-Ceph, Longhorn, NFS).
*   **Network Enhancements:**
    *   Advanced network policy management.
    *   Integration with Ingress controllers (e.g., Nginx Ingress, Traefik).
    *   Service Mesh integration (e.g., Istio, Linkerd).
*   **Security Hardening:**
    *   Automated security best practices implementation (e.g., CIS benchmarks).
    *   Integration with secrets management solutions.

## Future DevOps Features

Beyond Kubernetes, the K8s Auto Installer aims to evolve into a comprehensive DevOps automation platform. Planned new features include:

*   **Docker Management:**
    *   Automated Docker Engine installation and configuration.
    *   Management of Docker images and containers.
    *   Deployment of Docker Compose applications.
*   **CI/CD Pipeline Automation:**
    *   Integration with popular CI/CD tools (e.g., Jenkins, GitLab CI, GitHub Actions).
    *   Automated build, test, and deployment workflows.
    *   Templated pipelines for common application types.
*   **Monitoring and Logging Solutions:**
    *   Deployment and configuration of monitoring stacks (e.g., Prometheus, Grafana, ELK Stack).
    *   Centralized log collection and analysis.
    *   Alerting and notification system setup.
*   **Infrastructure as Code (IaC) Integration:**
    *   Support for deploying infrastructure using tools like Terraform or Ansible.
    *   Management of cloud resources and on-premise infrastructure.
*   **Cloud-Native Tooling:**
    *   Integration with other cloud-native projects and tools to provide a complete DevOps ecosystem.

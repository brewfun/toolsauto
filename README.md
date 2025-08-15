# K8s Auto Installer Web App

## Overview

The **K8s Auto Installer Web App** is a web-based application designed to automate the installation of Kubernetes (k8s) clusters. It provides a user-friendly interface to trigger k8s setup in two modes:
- **All-in-One**: A single-node Kubernetes cluster (ideal for local testing or development).
- **HA Secure**: A high-availability (HA) cluster with a minimum of 4 servers (1 NGINX load balancer for API server, 3 master nodes) and optional worker nodes (0-2). Uses Cilium as the Container Network Interface (CNI).

This project serves as both a practical DevOps tool and a learning platform for Python and Kubernetes automation. It leverages Python for backend automation, Flask for API, and a simple HTML/JS frontend for user interaction.

## Features

- **Frontend**: A web interface with a form to select installation type (All-in-One or HA Secure), input server details (for HA), and view real-time installation logs.
- **Backend**: A Flask-based API that validates inputs, triggers Python scripts for automation, and streams logs.
- **Automation**: Scripts to install Docker, kubeadm, and Cilium; configure NGINX as a load balancer (for HA); and set up HA clusters with secure configurations (RBAC, network policies).
- **Deployment**: Designed to run on free-tier cloud platforms (e.g., Netlify for frontend, Heroku for backend) or locally with Minikube for testing.
- **Learning Focus**: Includes detailed comments in Python code to teach beginners concepts like functions, SSH automation, and subprocess handling.

## Project Structure

```
k8s-auto-installer/
├── backend/                     # Backend code (Python, Flask)
│   ├── api/                     # API routes and logic
│   ├── scripts/                 # Automation scripts (all-in-one, HA, Cilium)
│   ├── tests/                   # Unit tests
│   ├── config/                  # Environment configs
│   ├── requirements.txt         # Python dependencies
│   └── main.py                  # Flask app entry point
├── frontend/                    # Frontend code (HTML, CSS, JS)
│   ├── public/                  # Static assets (CSS, JS)
│   ├── templates/               # HTML templates
│   └── package.json             # Frontend dependencies
├── docs/                        # Project documentation
├── logs/                        # Temporary runtime logs
├── .gitignore                   # Git ignore rules
├── README.md                    # This file
├── docker-compose.yml           # Container setup
└── Dockerfile                   # Docker for backend
```

## Prerequisites

To run this project, ensure you have the following installed:

- **Python 3.9+**: For backend development and automation scripts.
- **Node.js and npm** (optional): For frontend development if using external JS libraries.
- **Git**: For version control.
- **Docker**: For containerizing the application (optional for development).
- **Minikube** or **Multipass/VirtualBox**: For local testing of k8s clusters.
- **Cloud Account** (optional): AWS/GCP free tier for cloud-based deployments.
- **SSH Keys**: For HA Secure mode, to access multiple servers.

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <repository-url>
cd k8s-auto-installer
```

### 2. Set Up Python Environment

1. **Install Python 3.9+** (if not already installed):
   - Ubuntu: `sudo apt update && sudo apt install python3 python3-pip`
   - macOS: `brew install python`
   - Windows: Download from [python.org](https://www.python.org/downloads/).

2. **Create a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Python dependencies**:
   ```bash
   pip install -r backend/requirements.txt
   ```
   *Note*: If `requirements.txt` is not yet populated, install Flask and Paramiko:
   ```bash
   pip install flask paramiko
   ```

### 3. Set Up Frontend (Static Assets)

- The frontend uses static HTML/JS served by Flask. No additional setup is required unless you add Node.js dependencies.
- If using npm for frontend libraries (e.g., Axios):
  ```bash
  cd frontend
  npm install
  ```

### 4. Configure Environment Variables

1. Copy the example environment file:
   ```bash
   cp backend/config/dev.env backend/config/.env
   ```

2. Edit `backend/config/.env` to add sensitive data (e.g., SSH credentials, cloud API keys):
   ```env
   FLASK_ENV=development
   SSH_USER=<your-ssh-user>
   SSH_KEY_PATH=<path-to-ssh-private-key>
   AWS_ACCESS_KEY=<your-aws-key>  # Optional for cloud
   AWS_SECRET_KEY=<your-aws-secret>  # Optional
   ```

   *Note*: Never commit `.env` to Git (already ignored in `.gitignore`).

### 5. Run the Application Locally

1. **Start the Flask backend**:
   ```bash
   cd backend
   python main.py
   ```
   The API will run at `http://localhost:5000`.

2. **Access the frontend**:
   Open `http://localhost:5000` in a browser to see the form for selecting k8s installation options.

### 6. Test Automation Locally

- For **All-in-One** mode, ensure Minikube is installed:
  ```bash
  curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
  sudo install minikube-linux-amd64 /usr/local/bin/minikube
  ```
- Test the script in `backend/scripts/all_in_one.py` (to be developed).

- For **HA Secure** mode, simulate servers using Multipass:
  ```bash
  multipass launch --name k8s-lb
  multipass launch --name k8s-master1
  multipass launch --name k8s-master2
  multipass launch --name k8s-master3
  ```
  Update `.env` with Multipass IPs and SSH keys.

## Running Tests

Unit tests are located in `backend/tests/`. Run them with:
```bash
cd backend
pytest tests/
```

## Deployment

### Local Testing
- Use Minikube for All-in-One mode.
- Use Multipass/VirtualBox to simulate HA Secure mode with 4+ servers.

### Cloud Deployment (Free Tier)
- **Frontend**: Deploy static files (`frontend/templates`, `frontend/public`) to Netlify or Vercel.
- **Backend**: Deploy Flask app to Heroku or AWS Lambda (via Zappa for serverless).
- **Kubernetes Cluster**: Use AWS EC2 free tier (t2.micro instances) or GCP Compute Engine for provisioning servers.

## Usage

1. Open the web interface (`http://localhost:5000` or deployed URL).
2. Select an installation option:
   - **All-in-One**: Choose local or cloud, then click "Install".
   - **HA Secure**: Enter at least 4 server IPs (1 load balancer, 3 masters), optional worker IPs (0-2), and SSH credentials.
3. Monitor the installation via the dashboard (real-time logs).
4. Download the `kubeconfig` file or follow instructions to access the cluster.

## Development Roadmap

- **Phase 1**: Set up Python env, write basic automation scripts (`all_in_one.py`, `utils.py`).
- **Phase 2**: Build Flask API and All-in-One automation.
- **Phase 3**: Implement HA Secure automation (NGINX LB, 3 masters, Cilium).
- **Phase 4**: Develop frontend with form and real-time logs.
- **Phase 5**: Add cloud support, tests, and polish.

## Contributing

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature-name`.
3. Commit changes: `git commit -m "Add feature"`.
4. Push to branch: `git push origin feature-name`.
5. Open a pull request.

## Learning Resources

- **Python**: [Official Python Docs](https://docs.python.org/3/)
- **Flask**: [Flask Quickstart](https://flask.palletsprojects.com/en/stable/quickstart/)
- **Kubernetes**: [Kubeadm HA Guide](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/high-availability/)
- **Cilium**: [Cilium Installation](https://docs.cilium.io/en/stable/gettingstarted/k8s-install-default/)
- **Paramiko**: [Paramiko SSH Tutorial](http://docs.paramiko.org/en/stable/)

## License (Updating)

MIT License (to be added in a separate `LICENSE` file).
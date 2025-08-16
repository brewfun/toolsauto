# 🚀 ToolsAuto - K8s Auto Installer

[![Python](https://img.shields.io/badge/Python-3.9+-blue?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.0+-green?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-1.24+-blue?style=for-the-badge&logo=kubernetes&logoColor=white)](https://kubernetes.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](https://opensource.org/licenses/MIT)

> **Automate Kubernetes cluster deployment with just a few clicks!**

**ToolsAuto** is a modern web application that helps you deploy Kubernetes clusters automatically and effortlessly. No more memorizing hundreds of kubectl commands or troubleshooting complex installation errors!

## ✨ Key Features

### 🎯 Two Powerful Deployment Modes
- **🔥 All-in-One**: Single-node cluster perfect for development and testing
- **⚡ HA Secure**: High-availability cluster with minimum 4 servers (1 NGINX LB + 3 masters) + optional workers

### 🛠️ Modern Tech Stack
- **Backend**: Python 3.9+ with Flask API
- **Frontend**: Modern HTML/JS with real-time streaming logs
- **Container Network**: Cilium CNI for optimal performance
- **Security**: Built-in RBAC and network policies
- **Deployment**: Ready for cloud platforms (Netlify, Heroku, AWS)

### 🎓 Learning-Focused
- Detailed comments in Python code
- Best practices for SSH automation and subprocess handling
- Perfect for beginners learning DevOps and K8s

## 🏗️ Project Architecture

```
toolsauto/
├── 🔙 backend/              # Python Flask API
│   ├── 📡 api/              # API routes & logic  
│   ├── 🤖 scripts/          # Automation scripts (All-in-One, HA, Cilium)
│   ├── 🧪 tests/            # Unit tests
│   ├── ⚙️ config/           # Environment configurations
│   ├── 📋 requirements.txt  # Python dependencies
│   └── 🚀 main.py           # Flask app entry point
├── 🎨 frontend/             # Modern Web Interface
│   ├── 📁 public/           # Static assets (CSS, JS)
│   ├── 📄 templates/        # HTML templates
│   └── 📦 package.json      # Frontend dependencies
├── 📚 docs/                 # Documentation
├── 📝 logs/                 # Runtime logs
└── 🐳 docker-compose.yml    # Container orchestration
```

## 🚀 Quick Start

### 📋 System Requirements

| Requirement | Version | Purpose |
|-------------|---------|---------|
| 🐍 **Python** | 3.9+ | Backend & automation |
| 🌐 **Node.js** | 16+ (optional) | Frontend development |
| 🐳 **Docker** | 20+ (optional) | Containerization |
| ☸️ **Minikube** | Latest | Local K8s testing |
| 🔑 **SSH Keys** | - | HA mode server access |

### ⚡ Quick Installation

```bash
# 1. Clone repository
git clone https://github.com/brewfun/toolsauto.git
cd toolsauto

# 2. Create Python virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r backend/requirements.txt

# 4. Setup environment
cp backend/config/dev.env backend/config/.env
# Edit .env with SSH credentials and cloud keys

# 5. Start the magic! ✨
cd backend && python main.py
```

🎉 **Access**: http://localhost:5000

## 🎮 How to Use

### 🔥 All-in-One Mode
1. Select "All-in-One" on the web interface
2. Click "Install" and enjoy your ☕
3. Download `kubeconfig` and start deploying apps!

### ⚡ HA Secure Mode  
1. Prepare 4+ servers (or use Multipass to simulate)
2. Enter server IPs and SSH credentials
3. Watch real-time logs as your cluster builds up
4. Enjoy your production-ready K8s cluster! 🎊

### 🧪 Testing with Multipass

```bash
# Create test environment
multipass launch --name k8s-lb --cpus 2 --memory 2G
multipass launch --name k8s-master1 --cpus 2 --memory 2G  
multipass launch --name k8s-master2 --cpus 2 --memory 2G
multipass launch --name k8s-master3 --cpus 2 --memory 2G

# Get IPs and update .env file
multipass list
```

## 🔬 Development & Testing

```bash
# Run unit tests
cd backend && pytest tests/

# Development mode with hot reload
export FLASK_ENV=development
python main.py
```

## ☁️ Cloud Deployment

### Frontend (Netlify/Vercel)
- Deploy static files from `frontend/` directory
- Configure environment variables

### Backend (Heroku/AWS)
- Deploy Flask app with `main.py` entrypoint  
- Set environment variables from `.env`
- Configure SSH keys securely

### Infrastructure (AWS/GCP)
- Use free-tier instances (t2.micro)
- Setup security groups for K8s ports
- Configure load balancer for HA mode

## 🛣️ Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 🏗️ **Phase 1** | ✅ | Core automation scripts & Python environment |
| 🔧 **Phase 2** | 🚧 | Flask API & All-in-One automation |
| ⚡ **Phase 3** | 📋 | HA Secure mode with NGINX LB + Cilium |
| 🎨 **Phase 4** | 📋 | Modern frontend with real-time logs |
| ☁️ **Phase 5** | 📋 | Cloud support, comprehensive tests & polish |

## 🤝 Contributing

We welcome contributions! 

```bash
# 1. Fork repository
# 2. Create feature branch
git checkout -b feature/amazing-feature

# 3. Commit changes
git commit -m "Add: amazing new feature"

# 4. Push and create Pull Request
git push origin feature/amazing-feature
```

## 📚 Resources & References

- 🐍 [Python Official Docs](https://docs.python.org/3/)
- 🌶️ [Flask Documentation](https://flask.palletsprojects.com/)
- ☸️ [Kubernetes HA Setup Guide](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/high-availability/)
- 🐛 [Cilium Installation](https://docs.cilium.io/en/stable/gettingstarted/k8s-install-default/)
- 🔐 [Paramiko SSH Library](http://docs.paramiko.org/en/stable/)

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

---

<div align="center">

### 💫 "The best infrastructure is the one you never have to think about!"

**Built with ❤️ by [brewfun](https://github.com/brewfun)**

[![GitHub stars](https://img.shields.io/github/stars/brewfun/toolsauto?style=social)](https://github.com/brewfun/toolsauto/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/brewfun/toolsauto?style=social)](https://github.com/brewfun/toolsauto/network/members)

</div>
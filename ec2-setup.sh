#!/bin/bash
# ============================================
# ec2-setup.sh
# TravelQ EC2 Instance Initial Setup Script
# Run this ONCE after launching your EC2 instance
# Usage: chmod +x ec2-setup.sh && ./ec2-setup.sh
# ============================================

set -e

echo "=========================================="
echo "  TravelQ EC2 Setup - Starting..."
echo "=========================================="

# --- Update System ---
echo "Updating system packages..."
sudo yum update -y

# --- Install Docker ---
echo "Installing Docker..."
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user

# --- Install Docker Compose v2 ---
echo "Installing Docker Compose v2..."
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m)" \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# --- Install Git and utilities ---
echo "Installing Git and htop..."
sudo yum install -y git htop

# --- Install Certbot for SSL ---
echo "Installing Certbot..."
sudo yum install -y certbot || echo "Certbot install skipped (can install later)"

# --- Configure Docker log rotation ---
echo "Configuring Docker log rotation..."
sudo tee /etc/docker/daemon.json > /dev/null <<DAEMON_CFG
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
DAEMON_CFG
sudo systemctl restart docker

# --- Create app directory ---
echo "Creating application directory..."
mkdir -p ~/agentic-travelq

echo ""
echo "=========================================="
echo "  EC2 Setup Complete!"
echo "=========================================="
echo ""
echo "  LOG OUT AND BACK IN for Docker permissions:"
echo "    exit"
echo "    ssh -i your-key.pem ec2-user@YOUR_IP"
echo ""
echo "Then follow these steps:"
echo ""
echo "  1. Clone your repo:"
echo "     git clone https://github.com/YOUR_USERNAME/agentic-travelq.git"
echo "     cd agentic-travelq"
echo ""
echo "  2. Create .env.prod:"
echo "     cp .env.prod.example .env.prod"
echo "     nano .env.prod"
echo ""
echo "  3. Start TravelQ:"
echo "     docker compose -f docker-compose.prod.yml up -d --build"
echo ""
echo "  4. Check health:"
echo "     docker compose -f docker-compose.prod.yml ps"
echo "     curl http://localhost/api/trips/health"
echo ""
echo "  5. View logs:"
echo "     docker compose -f docker-compose.prod.yml logs -f"
echo ""
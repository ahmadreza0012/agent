#!/bin/bash

# Script to prepare EC2 server for CI/CD deployment
# Run this ONCE on your EC2 server

set -e

echo "🚀 Setting up EC2 server for CI/CD deployment..."

# Update system
echo "📦 Updating system packages..."
sudo yum update -y

# Install required packages
echo "📥 Installing required packages..."
sudo yum install -y python3 python3-pip git tmux

# Create project directory
echo "📁 Creating project directory..."
mkdir -p ~/trading-agent
cd ~/trading-agent

# Initialize git repository
echo "🔄 Initializing git repository..."
if [ ! -d .git ]; then
    git init
    echo "✅ Git repository initialized"
    echo ""
    echo "⚠️  IMPORTANT: Add your GitHub repository as remote:"
    echo "   git remote add origin <YOUR_GITHUB_REPO_URL>"
else
    echo "✅ Git repository already exists"
fi

# Create virtual environment
echo "🐍 Setting up virtual environment..."
if [ ! -d venv ]; then
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Copy .env.example to .env if not exists
if [ ! -f .env ]; then
    echo "📋 Creating .env file from example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✅ .env file created"
        echo ""
        echo "⚠️  IMPORTANT: Edit .env and add your API keys:"
        echo "   nano .env"
    else
        echo "⚠️  .env.example not found. Please create .env manually"
    fi
else
    echo "✅ .env file already exists"
fi

echo ""
echo "=========================================="
echo "✅ Server setup completed!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Add GitHub remote (if not done):"
echo "   git remote add origin <YOUR_GITHUB_REPO_URL>"
echo ""
echo "2. Configure .env file:"
echo "   nano .env"
echo ""
echo "3. Do an initial pull from GitHub:"
echo "   git pull origin main"
echo ""
echo "4. Start the application with tmux:"
echo "   tmux new -s trading-agent"
echo "   source venv/bin/activate"
echo "   python main.py"
echo "   (Press Ctrl+B, D to detach)"
echo ""
echo "5. Set up GitHub Secrets (see README_CI_CD.md)"
echo ""
echo "=========================================="

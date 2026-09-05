#!/bin/bash

# AWS EC2 Deployment Script for Trading Agent
# Server: 52.23.157.88
# Key: agentkey.pem

set -e

KEY_FILE="/workspace/agentkey.pem"
SERVER_IP="52.23.157.88"
PROJECT_NAME="trading-agent"

# Ensure key has correct permissions
chmod 600 $KEY_FILE

echo "=== Starting deployment to AWS EC2 ($SERVER_IP) ==="

# Function to try SSH with different users
try_ssh() {
    local user=$1
    local cmd=$2
    ssh -i $KEY_FILE -o StrictHostKeyChecking=no -o ConnectTimeout=10 $user@$SERVER_IP "$cmd" 2>/dev/null
}

# Detect the correct SSH user
echo "Detecting SSH user..."
SSH_USER=""
for user in ec2-user ubuntu admin root; do
    if try_ssh $user "whoami" > /dev/null 2>&1; then
        SSH_USER=$user
        echo "Found valid user: $SSH_USER"
        break
    fi
done

if [ -z "$SSH_USER" ]; then
    echo "ERROR: Could not connect to server with any known user (ec2-user, ubuntu, admin, root)"
    echo "Please check:"
    echo "  1. Server IP is correct: $SERVER_IP"
    echo "  2. Key file is valid: $KEY_FILE"
    echo "  3. Security group allows SSH (port 22)"
    echo "  4. Instance is running"
    exit 1
fi

# Create deployment script on server
echo "Creating deployment script on server..."

cat << 'DEPLOY_SCRIPT' | ssh -i /workspace/agentkey.pem -o StrictHostKeyChecking=no $SSH_USER@$SERVER_IP "cat > deploy_app.sh"
#!/bin/bash
set -e

echo "=== Starting application deployment ==="

# Update system
sudo yum update -y 2>/dev/null || sudo apt-get update -y

# Install dependencies
echo "Installing system dependencies..."
sudo yum install -y python3 python3-pip git tmux htop 2>/dev/null || \
sudo apt-get install -y python3 python3-pip git tmux htop

# Create app directory
APP_DIR="/home/$SSH_USER/$PROJECT_NAME"
mkdir -p $APP_DIR
cd $APP_DIR

# Clone repository or update if exists
if [ ! -d ".git" ]; then
    echo "Cloning repository..."
    # Replace with your actual repo URL
    git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git . 2>/dev/null || true
else
    echo "Updating repository..."
    git pull
fi

# Create virtual environment
echo "Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
if [ -f requirements.txt ]; then
    pip install -r requirements.txt
fi

# Setup environment variables
echo "Setting up environment..."
if [ ! -f .env ]; then
    cp .env.example .env 2>/dev/null || echo "No .env.example found"
    echo "Please configure .env file with your API keys and settings"
fi

# Initialize database if needed
echo "Initializing database..."
source venv/bin/activate
python main.py --init-db 2>/dev/null || true

# Create systemd service or tmux session for running the app
echo "Setting up application runner..."

# Option 1: Using tmux (simpler)
tmux kill-session -t $PROJECT_NAME 2>/dev/null || true
tmux new -d -s $PROJECT_NAME "cd $APP_DIR && source venv/bin/activate && python main.py"

echo ""
echo "=== Deployment Complete ==="
echo "Application is running in tmux session: $PROJECT_NAME"
echo "To attach: tmux attach -t $PROJECT_NAME"
echo "To detach: Ctrl+B, then D"
echo ""
echo "Server IP: $SERVER_IP"
echo "To monitor logs, check the application output in tmux"
DEPLOY_SCRIPT

# Make it executable and run
ssh -i $KEY_FILE -o StrictHostKeyChecking=no $SSH_USER@$SERVER_IP "chmod +x deploy_app.sh"

echo ""
echo "=== Deployment Script Created ==="
echo ""
echo "Next steps:"
echo "1. Update the Git repository URL in deploy_app.sh on the server"
echo "2. Run the deployment script on server:"
echo "   ssh -i $KEY_FILE $SSH_USER@$SERVER_IP './deploy_app.sh'"
echo ""
echo "Or manually:"
echo "   ssh -i $KEY_FILE $SSH_USER@$SERVER_IP"
echo ""
echo "Quick connection command:"
echo "   ssh -i $KEY_FILE $SSH_USER@$SERVER_IP"
echo ""

#!/bin/bash

# Installation script for 24/7 Operation Console Monitor services
# This script sets up systemd services (Linux) or LaunchAgents (macOS)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Project paths
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_NAME=$(whoami)
PYTHON_BIN=$(which python3)

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║   Operation Console Monitor - 24/7 Service Installer      ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "Project Directory: $PROJECT_DIR"
echo "User: $USER_NAME"
echo "Python: $PYTHON_BIN"
echo ""

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
    echo "Detected OS: Linux (systemd)"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    echo "Detected OS: macOS (LaunchAgent)"
else
    echo -e "${RED}❌ Unsupported OS: $OSTYPE${NC}"
    exit 1
fi

echo ""

# Create required directories
echo "📁 Creating directories..."
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/backups"
echo -e "${GREEN}✅ Directories created${NC}"
echo ""

# Install services based on OS
if [ "$OS" == "linux" ]; then
    # Linux systemd installation
    echo "🔧 Installing systemd services..."
    
    # Dashboard service
    sudo tee /etc/systemd/system/oc-dashboard.service > /dev/null <<EOF
[Unit]
Description=Operation Console Monitor Dashboard
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$USER_NAME
Group=$USER_NAME
WorkingDirectory=$PROJECT_DIR
Environment="PATH=/usr/local/bin:/usr/bin:/bin"

ExecStart=$PYTHON_BIN run_dashboard.py --host 0.0.0.0 --port 8080

Restart=always
RestartSec=10
StartLimitInterval=200
StartLimitBurst=5

StandardOutput=append:$PROJECT_DIR/logs/dashboard.log
StandardError=append:$PROJECT_DIR/logs/dashboard-error.log

MemoryLimit=512M
CPUQuota=50%

NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
    
    # Scheduler service
    sudo tee /etc/systemd/system/oc-scheduler.service > /dev/null <<EOF
[Unit]
Description=Operation Console Monitor Scheduler
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$USER_NAME
Group=$USER_NAME
WorkingDirectory=$PROJECT_DIR
Environment="PATH=/usr/local/bin:/usr/bin:/bin"

ExecStart=$PYTHON_BIN -m operation_console_monitor.scheduler --config config/monitor.yaml

Restart=always
RestartSec=30
StartLimitInterval=300
StartLimitBurst=5

StandardOutput=append:$PROJECT_DIR/logs/scheduler.log
StandardError=append:$PROJECT_DIR/logs/scheduler-error.log

MemoryLimit=1G
CPUQuota=75%

NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
    
    echo -e "${GREEN}✅ Service files created${NC}"
    
    # Reload systemd
    echo "🔄 Reloading systemd..."
    sudo systemctl daemon-reload
    echo -e "${GREEN}✅ Systemd reloaded${NC}"
    echo ""
    
    # Enable services
    echo "🚀 Enabling services (auto-start on boot)..."
    sudo systemctl enable oc-dashboard
    sudo systemctl enable oc-scheduler
    echo -e "${GREEN}✅ Services enabled${NC}"
    echo ""
    
    # Start services
    echo "▶️  Starting services..."
    sudo systemctl start oc-dashboard
    sudo systemctl start oc-scheduler
    echo -e "${GREEN}✅ Services started${NC}"
    echo ""
    
    # Show status
    echo "📊 Service Status:"
    sudo systemctl status oc-dashboard --no-pager || true
    echo ""
    sudo systemctl status oc-scheduler --no-pager || true
    echo ""
    
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✅ Installation Complete!${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "📋 Service Management Commands:"
    echo "   Start:    sudo systemctl start oc-dashboard oc-scheduler"
    echo "   Stop:     sudo systemctl stop oc-dashboard oc-scheduler"
    echo "   Restart:  sudo systemctl restart oc-dashboard oc-scheduler"
    echo "   Status:   sudo systemctl status oc-dashboard oc-scheduler"
    echo "   Logs:     journalctl -u oc-dashboard -f"
    echo ""
    echo "🌐 Dashboard URL: http://localhost:8080"
    echo ""
    
elif [ "$OS" == "macos" ]; then
    # macOS LaunchAgent installation
    echo "🔧 Installing LaunchAgents..."
    
    LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
    mkdir -p "$LAUNCH_AGENTS_DIR"
    
    # Dashboard LaunchAgent
    cat > "$LAUNCH_AGENTS_DIR/com.oc.dashboard.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.oc.dashboard</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_BIN</string>
        <string>run_dashboard.py</string>
        <string>--host</string>
        <string>0.0.0.0</string>
        <string>--port</string>
        <string>8080</string>
    </array>
    
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/logs/dashboard.log</string>
    
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/logs/dashboard-error.log</string>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    
    <key>ProcessType</key>
    <string>Background</string>
    
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
EOF
    
    # Scheduler LaunchAgent
    cat > "$LAUNCH_AGENTS_DIR/com.oc.scheduler.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.oc.scheduler</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_BIN</string>
        <string>-m</string>
        <string>operation_console_monitor.scheduler</string>
        <string>--config</string>
        <string>config/monitor.yaml</string>
    </array>
    
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/logs/scheduler.log</string>
    
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/logs/scheduler-error.log</string>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    
    <key>ProcessType</key>
    <string>Background</string>
    
    <key>ThrottleInterval</key>
    <integer>30</integer>
</dict>
</plist>
EOF
    
    echo -e "${GREEN}✅ LaunchAgent files created${NC}"
    echo ""
    
    # Load LaunchAgents
    echo "🚀 Loading LaunchAgents..."
    launchctl load "$LAUNCH_AGENTS_DIR/com.oc.dashboard.plist"
    launchctl load "$LAUNCH_AGENTS_DIR/com.oc.scheduler.plist"
    echo -e "${GREEN}✅ LaunchAgents loaded${NC}"
    echo ""
    
    # Wait a moment for services to start
    sleep 3
    
    # Show status
    echo "📊 Service Status:"
    launchctl list | grep com.oc
    echo ""
    
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✅ Installation Complete!${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "📋 Service Management Commands:"
    echo "   Stop:     launchctl unload ~/Library/LaunchAgents/com.oc.dashboard.plist"
    echo "             launchctl unload ~/Library/LaunchAgents/com.oc.scheduler.plist"
    echo "   Start:    launchctl load ~/Library/LaunchAgents/com.oc.dashboard.plist"
    echo "             launchctl load ~/Library/LaunchAgents/com.oc.scheduler.plist"
    echo "   Status:   launchctl list | grep com.oc"
    echo "   Logs:     tail -f logs/dashboard.log"
    echo "             tail -f logs/scheduler.log"
    echo ""
    echo "🌐 Dashboard URL: http://localhost:8080"
    echo ""
fi

# Test dashboard health
echo "🔍 Testing dashboard health..."
sleep 2
if curl -f -s http://localhost:8080/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Dashboard is responding!${NC}"
else
    echo -e "${YELLOW}⚠️  Dashboard may still be starting up...${NC}"
    echo "   Check logs: tail -f logs/dashboard.log"
fi

echo ""
echo "📚 Documentation:"
echo "   Quick Start:  DASHBOARD_QUICKREF.md"
echo "   Full Guide:   DASHBOARD_GUIDE.md"
echo "   24/7 Setup:   PRODUCTION_24_7_GUIDE.md"
echo ""

echo -e "${GREEN}🎉 Your monitoring system is now running 24/7!${NC}"

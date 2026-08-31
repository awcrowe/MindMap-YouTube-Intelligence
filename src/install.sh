#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# MindMap — VPS Setup Script for Ubuntu 24
# Run as root or with sudo
# Usage: bash install.sh
# ═══════════════════════════════════════════════════════════════
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }
step() { echo -e "\n${BLUE}══ $1 ══${NC}"; }

# ── CHECK ROOT ───────────────────────────────────────────────────
[[ $EUID -ne 0 ]] && err "Run as root: sudo bash install.sh"

step "System Update"
apt-get update -qq && apt-get upgrade -y -qq
apt-get install -y -qq python3 python3-pip python3-venv git curl ufw nginx certbot python3-certbot-nginx

step "Create App User"
if ! id "mindmap" &>/dev/null; then
    useradd -m -s /bin/bash mindmap
    log "Created user: mindmap"
else
    warn "User mindmap already exists"
fi

step "Application Directory"
APP_DIR="/opt/mindmap"
mkdir -p "$APP_DIR"
cp -r ./* "$APP_DIR/" 2>/dev/null || true
chown -R mindmap:mindmap "$APP_DIR"

step "Python Virtual Environment"
sudo -u mindmap python3 -m venv "$APP_DIR/venv"
sudo -u mindmap "$APP_DIR/venv/bin/pip" install --upgrade pip -q
sudo -u mindmap "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt" -q
log "Dependencies installed"

step "Environment Configuration"
if [ ! -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    
    # Generate a secure random token
    TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/your-secret-token-here/$TOKEN/" "$APP_DIR/.env"
    
    warn "Generated API token: $TOKEN"
    warn "Save this — you'll need it in your HTML app!"
    echo ""
    echo "  Edit $APP_DIR/.env to add your DeepSeek API key"
    echo ""
fi

step "Systemd Service"
cat > /etc/systemd/system/mindmap.service << EOF
[Unit]
Description=MindMap Transcript API
After=network.target
Wants=network.target

[Service]
Type=simple
User=mindmap
WorkingDirectory=/opt/mindmap
Environment="PATH=/opt/mindmap/venv/bin"
ExecStart=/opt/mindmap/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=mindmap

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/opt/mindmap

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable mindmap
systemctl start mindmap
log "Systemd service active"

step "Firewall (UFW)"
ufw --force enable
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
# Port 8000 only accessible via nginx — NOT exposed directly
log "Firewall configured"

step "Nginx Reverse Proxy"
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || echo "YOUR_VPS_IP")

cat > /etc/nginx/sites-available/mindmap << EOF
server {
    listen 80;
    server_name $SERVER_IP _;

    # Security headers
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";

    # Rate limiting — 20 requests per minute per IP
    limit_req_zone \$binary_remote_addr zone=mindmap:10m rate=20r/m;
    limit_req zone=mindmap burst=10 nodelay;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;    # transcripts can take time
        proxy_connect_timeout 10s;
    }

    # Larger body for batch requests
    client_max_body_size 1M;
}
EOF

ln -sf /etc/nginx/sites-available/mindmap /etc/nginx/sites-enabled/mindmap
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx
log "Nginx configured"

step "Health Check"
sleep 3
HEALTH=$(curl -s http://127.0.0.1:8000/health 2>/dev/null || echo "failed")
if echo "$HEALTH" | grep -q "ok"; then
    log "Server responding: $HEALTH"
else
    warn "Health check failed. Check: journalctl -u mindmap -n 50"
fi

step "HTTPS Setup (Optional)"
echo ""
echo "  To add HTTPS with Let's Encrypt (requires a domain name):"
echo "  1. Point your domain DNS to: $SERVER_IP"
echo "  2. Run: certbot --nginx -d yourdomain.com"
echo "  3. Update API_BASE_URL in yt-mindmap.html to https://yourdomain.com"
echo ""

step "Installation Complete"
echo ""
echo "  ┌─────────────────────────────────────────────────────┐"
echo "  │  Server:    http://$SERVER_IP                       │"
echo "  │  Health:    http://$SERVER_IP/health                │"
echo "  │  API docs:  http://$SERVER_IP/docs                  │"
echo "  │  Logs:      journalctl -u mindmap -f                │"
echo "  │  Config:    nano /opt/mindmap/.env                  │"
echo "  └─────────────────────────────────────────────────────┘"
echo ""
warn "Next step: add your DeepSeek key to /opt/mindmap/.env then:"
echo "  systemctl restart mindmap"

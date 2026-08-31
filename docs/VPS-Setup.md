
---

### `docs/VPS-Setup.md`
```markdown
# VPS Setup (Ubuntu 24)

Deploy the MindMap backend on a virtual private server to enable transcript fetching, batch analysis, and persistent caching.

## Requirements

- Ubuntu 24.04 LTS (or compatible)
- Root/sudo access
- A domain name (optional, but recommended for HTTPS)
- DeepSeek API key (get from platform.deepseek.com)

## Step-by-Step

### 1. Copy the Source Files

SSH into your VPS and place the `src/` contents into `/opt/mindmap`:

```bash
sudo mkdir -p /opt/mindmap
sudo cp -r ./src/* /opt/mindmap/
sudo chown -R mindmap:mindmap /opt/mindmap  # user will be created by install.sh


2. Run the Install Script

```bash
cd /opt/mindmap
sudo bash install.sh
```

The script will:

· Update system packages
· Install Python, nginx, certbot, etc.
· Create a mindmap system user
· Set up Python virtual environment and install dependencies
· Generate a random API_TOKEN and save it in .env
· Start the systemd service mindmap
· Configure nginx as a reverse proxy (port 80)
· Optionally prompt you for SSL (see below)

At the end, it shows the generated API token—copy it for the client configuration.

3. Add Your DeepSeek Key

Edit /opt/mindmap/.env:

```
API_TOKEN=your_generated_token
DEEPSEEK_API_KEY=sk-...
DB_PATH=mindmap.db
MAX_WORKERS=3
RATE_DELAY=1.5
LOG_LEVEL=INFO
```

Then restart:

```bash
sudo systemctl restart mindmap
```

4. Configure HTTPS (Optional but Recommended)

If you have a domain pointing to your VPS, run:

```bash
sudo certbot --nginx -d yourdomain.com
```

Update the client’s VPS URL to https://yourdomain.com.

5. Check the Service

```bash
sudo systemctl status mindmap
journalctl -u mindmap -f
```

Test the API:

```bash
curl http://your-vps-ip/health
```

Should return {"status":"ok",...}.

---

Security Considerations

· The API token is essential—keep it secret.
· The service listens only on 127.0.0.1; nginx acts as a reverse proxy.
· UFW allows only SSH, HTTP, and HTTPS.
· Consider using fail2ban and regular system updates.
· For production, enable SSL and restrict CORS origins in main.py (change allow_origins=["*"] to your domain).

Upgrading

· Pull new code and run sudo -u mindmap /opt/mindmap/venv/bin/pip install -r requirements.txt
· Restart the service: sudo systemctl restart mindmap

```
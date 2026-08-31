```markdown
# Security Best Practices

## API Token
- The token is used for all authenticated endpoints.  
- Store it securely in your `.env` file and never commit it.  
- Use a strong, randomly generated token (install.sh does this for you).  
- Rotate the token periodically.

## Environment Variables
- Keep `.env` outside version control (`.gitignore` already excludes it).  
- Set restrictive permissions: `chmod 600 .env`.

## Firewall
- The install script configures UFW to allow only SSH, HTTP, and HTTPS.  
- Port 8000 is bound to `127.0.0.1` only – not exposed to the internet.

## Reverse Proxy (Nginx)
- Nginx terminates SSL if you enable HTTPS.  
- It also adds rate limiting (20 req/min per IP) to prevent abuse.

## CORS
- For production, restrict CORS origins in `main.py`:
  ```python
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["https://yourdomain.com"],
      ...
  )
```

User Isolation

· The service runs as a non‑root user mindmap with restricted system access.

HTTPS

· Always use HTTPS in production – the client sends API tokens over the wire.
· Use Certbot to obtain free SSL certificates.

Regular Updates

· Keep the OS and Python packages updated:
  ```bash
  sudo apt update && sudo apt upgrade
  sudo -u mindmap /opt/mindmap/venv/bin/pip install --upgrade -r /opt/mindmap/requirements.txt
  sudo systemctl restart mindmap
  ```

Audit Logs

· The server logs all requests (except health) – monitor them for anomalies.

```
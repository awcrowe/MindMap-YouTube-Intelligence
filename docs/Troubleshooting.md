### `docs/Troubleshooting.md`
```markdown
# Troubleshooting

## Client Issues

### The dashboard shows no data after upload
- Make sure you selected the correct JSON file from Google Takeout (watch-history.json).  
- Try a different browser (Chrome/Edge recommended).  
- Open the browser console (F12) for error messages.

### OAuth fails (Google Sign-In)
- OAuth only works on `http://localhost:8080` (or `https` with a valid domain).  
- Ensure your Client ID has the correct Authorised JavaScript Origin and Redirect URI.  
- Use file upload instead – it works for all environments.

### Charts don’t render
- Check that Chart.js loaded correctly (network tab).  
- If offline, ensure you have internet to load the CDN (or download Chart.js locally).

---

## VPS Server Issues

### Health check returns 502 Bad Gateway
- Nginx cannot reach the FastAPI process. Check if the service is running:  
  `sudo systemctl status mindmap`  
  If not, start it: `sudo systemctl start mindmap`  
- Ensure the service listens on `127.0.0.1:8000` and nginx proxy_pass matches.

### “Invalid or missing bearer token”
- Double-check the API token in your client settings – it must match the one in `/opt/mindmap/.env`.  
- Token is case‑sensitive.

### Transcript fetch fails with “Transcripts disabled”
- The video may have no transcripts available. This is normal – the error is cached.  
- You can retry later if the video gets transcripts.

### DeepSeek returns non‑JSON
- Check your API key and quota.  
- The server logs (`journalctl -u mindmap -f`) will show the actual error.

### Service fails to start
- Check the logs: `journalctl -u mindmap -n 50`  
- Common issues: missing .env file, invalid syntax in .env, port already in use.

---

## Performance

### Slow batch processing
- Increase `MAX_WORKERS` in .env (but beware YouTube rate limits).  
- Reduce `RATE_DELAY` to 1.0 (minimum).  
- The backend is synchronous per request – upgrade to Tier 4 (Celery) for high volume.

### Database grows too large
- Use `DELETE /cache/video/{video_id}` to remove old entries.  
- Consider periodic pruning via a cron job.
```

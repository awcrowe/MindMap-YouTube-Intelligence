### `docs/Client-Server-Mode.md`
```markdown
# Client‑Server Mode

Connect the HTML client to your VPS backend to unlock transcript analysis and aggregate reporting.

## Configuration

1. Open the HTML client (`src/client/index.html`) in your browser.
2. Click the **gear icon** (⚙) in the top bar.
3. Fill in the fields:
   - **VPS Server URL**: `http://your-vps-ip` or `https://yourdomain.com`
   - **VPS API Token**: the token generated during install (copy it from the install output or from `/opt/mindmap/.env`).
4. Click **Save & Close**.

## Check Connection

Use the **Ping VPS** button in the settings modal or the **Ping VPS** button in the “Transcript Analysis” section. A green indicator means the backend is reachable.

## Transcript Analysis

- In the “Select Videos for Transcript Analysis” box, choose a filter (Top Channels, Recent, Uncategorised).
- Select videos by ticking the checkboxes.
- Choose an analysis type: `Synopsis + Topics`, `Psychometric Analysis`, or `Re‑classify Category`.
- Click **Send to VPS**.
- The job will start and you’ll see progress and results in the “Job Progress” card.

## Aggregate Report

After you’ve analysed several videos, click **Aggregate Report** in the AI Insights section. The VPS will compile all stored analyses and generate a holistic psychographic profile of the viewer.

## Notes

- The client polls the job status every 2.5 seconds.
- Results are cached per video—subsequent requests are instant.
- Transcripts are stored in the database, so you won’t re‑fetch them.
```
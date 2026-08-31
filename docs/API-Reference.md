```markdown
# API Reference

All endpoints (except `/health`) require a Bearer token in the `Authorization` header.

## `GET /health`
Public health check.

**Response:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "cached_transcripts": 42,
  "total_jobs": 15,
  "deepseek_configured": true,
  "timestamp": "2026-04-26T12:34:56Z"
}
```

---

POST /transcript/single

Fetch and cache a single transcript.

Request Body:

```json
{
  "video_id": "abc123",
  "title": "Optional Title",
  "channel": "Optional Channel"
}
```

Response:

```json
{
  "video_id": "abc123",
  "cached": false,
  "available": true,
  "text_preview": "...",
  "word_count": 1234,
  "language": "en (manual)",
  "error": null
}
```

---

POST /batch/submit

Submit a batch of videos for analysis. Returns a job_id for polling.

Request Body:

```json
{
  "videos": [
    {"video_id": "abc", "title": "...", "channel": "..."}
  ],
  "analysis_type": "synopsis",
  "use_cache": true
}
```

Response:

```json
{
  "job_id": "a1b2c3",
  "total": 20,
  "status": "running",
  "poll_url": "/batch/status/a1b2c3"
}
```

---

GET /batch/status/{job_id}

Poll job progress and get partial results.

Response:

```json
{
  "job_id": "a1b2c3",
  "status": "complete",
  "total": 20,
  "completed": 20,
  "failed": 0,
  "progress_pct": 100,
  "results": {
    "video_id_1": {
      "video_id": "video_id_1",
      "title": "...",
      "channel": "...",
      "transcript": {"available": true, "word_count": 500, ...},
      "analysis": {"summary": "...", "topics": [...], ...}
    }
  }
}
```

---

GET /cache/stats

Get cache statistics.

Response:

```json
{
  "transcripts": {
    "total": 120,
    "with_transcript": 110,
    "with_error": 10,
    "total_words": 150000,
    "avg_words": 1363.6,
    "oldest": "2026-01-01",
    "newest": "2026-04-26"
  },
  "analyses": {
    "synopsis": 45,
    "psychometric": 20,
    "classify": 30
  }
}
```

---

DELETE /cache/video/{video_id}

Invalidate transcript and analysis cache for a specific video.

Response:

```json
{"cleared": "video_id"}
```

---

GET /aggregate/insights?limit=100

Generate an aggregate psychographic report from stored analyses.

Response:

```json
{
  "videos_analysed": 100,
  "report": "... (DeepSeek-generated text)",
  "tokens_used": 850
}
```

```
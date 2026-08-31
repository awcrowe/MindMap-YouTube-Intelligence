"""
MindMap — Transcript Intelligence Server
FastAPI backend for YouTube transcript fetching + DeepSeek analysis.

Architecture: Tier 2 (single VPS, synchronous with async endpoints)
Upgrade path: Extract worker pool → Redis queue → Tier 4 with minimal changes.

Ubuntu 24 setup: see install.sh
"""

import os
import json
import time
import hashlib
import logging
import asyncio
from datetime import datetime
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
from youtube_transcript_api.formatters import TextFormatter
import sqlite3
from contextlib import contextmanager
from dotenv import load_dotenv

# ─── CONFIG ──────────────────────────────────────────────────────────────────
load_dotenv()

API_TOKEN    = os.getenv("API_TOKEN", "changeme-set-in-env")
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DB_PATH      = os.getenv("DB_PATH", "mindmap.db")
LOG_LEVEL    = os.getenv("LOG_LEVEL", "INFO")
MAX_WORKERS  = int(os.getenv("MAX_WORKERS", "3"))       # parallel transcript fetches
RATE_DELAY   = float(os.getenv("RATE_DELAY", "1.5"))    # seconds between YT requests

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger("mindmap")

# ─── DATABASE ─────────────────────────────────────────────────────────────────
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS transcripts (
                video_id    TEXT PRIMARY KEY,
                title       TEXT,
                channel     TEXT,
                text        TEXT,
                language    TEXT,
                fetched_at  TEXT,
                word_count  INTEGER,
                error       TEXT
            );

            CREATE TABLE IF NOT EXISTS analyses (
                video_id      TEXT PRIMARY KEY,
                analysis_type TEXT,
                result        TEXT,
                model         TEXT,
                tokens_used   INTEGER,
                created_at    TEXT,
                FOREIGN KEY (video_id) REFERENCES transcripts(video_id)
            );

            CREATE TABLE IF NOT EXISTS jobs (
                job_id      TEXT PRIMARY KEY,
                status      TEXT DEFAULT 'pending',
                total       INTEGER DEFAULT 0,
                completed   INTEGER DEFAULT 0,
                failed      INTEGER DEFAULT 0,
                created_at  TEXT,
                updated_at  TEXT,
                results     TEXT DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_transcripts_fetched ON transcripts(fetched_at);
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        """)
    log.info(f"Database initialised at {DB_PATH}")

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# ─── APP ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="MindMap Transcript API",
    version="1.0.0",
    description="YouTube transcript fetching + DeepSeek analysis backend"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Tighten in production: ["https://yourdomain.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── AUTH ─────────────────────────────────────────────────────────────────────
security = HTTPBearer(auto_error=False)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials or credentials.credentials != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing bearer token")
    return credentials.credentials

# ─── MODELS ──────────────────────────────────────────────────────────────────
class VideoRequest(BaseModel):
    video_id: str
    title: Optional[str] = ""
    channel: Optional[str] = ""

class BatchRequest(BaseModel):
    videos: list[VideoRequest]
    analysis_type: str = "synopsis"   # synopsis | psychometric | classify
    use_cache: bool = True

class AnalysisRequest(BaseModel):
    video_id: str
    analysis_type: str = "synopsis"
    force: bool = False

# ─── TRANSCRIPT FETCHER ───────────────────────────────────────────────────────
formatter = TextFormatter()

LANG_PRIORITY = ['en', 'en-US', 'en-GB', 'en-AU', 'en-CA']

def fetch_transcript(video_id: str) -> dict:
    """
    Fetch transcript with multi-language fallback.
    Returns dict with text, language, word_count, error.
    Tier 4 upgrade: this function becomes a Celery/RQ task.
    """
    try:
        # Try preferred languages first
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        transcript = None
        language = None

        # 1. Manual English
        for lang in LANG_PRIORITY:
            try:
                transcript = transcript_list.find_manually_created_transcript([lang])
                language = lang + " (manual)"
                break
            except Exception:
                pass

        # 2. Auto-generated English
        if not transcript:
            try:
                transcript = transcript_list.find_generated_transcript(LANG_PRIORITY)
                language = "en (auto)"
            except Exception:
                pass

        # 3. Any language → translate to English
        if not transcript:
            try:
                for t in transcript_list:
                    transcript = t.translate('en')
                    language = f"{t.language_code} → en (translated)"
                    break
            except Exception:
                pass

        if not transcript:
            return {"text": None, "language": None, "word_count": 0,
                    "error": "No transcript available in any language"}

        data = transcript.fetch()
        text = " ".join(entry['text'] for entry in data)
        text = text.replace('\n', ' ').strip()

        return {
            "text": text,
            "language": language,
            "word_count": len(text.split()),
            "error": None
        }

    except TranscriptsDisabled:
        return {"text": None, "language": None, "word_count": 0,
                "error": "Transcripts disabled for this video"}
    except NoTranscriptFound:
        return {"text": None, "language": None, "word_count": 0,
                "error": "No transcript found"}
    except Exception as e:
        return {"text": None, "language": None, "word_count": 0,
                "error": str(e)[:200]}

# ─── DEEPSEEK ANALYSIS ────────────────────────────────────────────────────────
ANALYSIS_PROMPTS = {
    "synopsis": """Analyse this YouTube video transcript and produce:
1. A 2-sentence summary of core content
2. Main topics covered (up to 5, as a JSON array)
3. Emotional tone (one of: educational, entertaining, alarming, inspiring, neutral, critical)
4. Complexity level (1-5, where 5 is graduate-level)
5. Key quotes or phrases (up to 3, verbatim from transcript)

Respond ONLY as JSON:
{{"summary":"...","topics":[],"tone":"...","complexity":1,"key_quotes":[]}}""",

    "psychometric": """Based on this YouTube transcript, infer psychographic signals:
1. What does watching this suggest about the viewer's current mental state?
2. Is the content anxiety-inducing, calming, stimulating, or escapist?
3. Cognitive engagement level required (passive/active/deep)
4. What underlying need does this content serve? (curiosity/validation/escapism/information/entertainment)

Respond ONLY as JSON:
{{"mental_state_signal":"...","emotional_valence":"...","cognitive_engagement":"passive|active|deep","underlying_need":"...","confidence":0.0}}""",

    "classify": """Classify this YouTube video into exactly one category.
Categories: Science, History, Politics, Philosophy, Food, Technology, Finance, Health, Nature, Music, Psychology, Other

Also provide a confidence score 0.0-1.0 and one-sentence rationale.

Respond ONLY as JSON:
{{"category":"...","confidence":0.0,"rationale":"..."}}"""
}

async def analyse_with_deepseek(
    text: str,
    title: str,
    channel: str,
    analysis_type: str
) -> dict:
    """
    Send transcript to DeepSeek for analysis.
    Tier 4 upgrade: becomes async Celery task with retry queue.
    """
    if not DEEPSEEK_KEY:
        return {"error": "DeepSeek API key not configured"}

    # Truncate to ~6000 words to stay within token limits affordably
    words = text.split()
    if len(words) > 6000:
        text = " ".join(words[:6000]) + "... [truncated]"

    system_prompt = ANALYSIS_PROMPTS.get(analysis_type, ANALYSIS_PROMPTS["synopsis"])

    user_content = f"""Title: {title}
Channel: {channel}
Transcript:
{text}"""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "max_tokens": 500,
                    "temperature": 0.2,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ]
                }
            )
        data = r.json()
        raw = data["choices"][0]["message"]["content"]
        tokens = data.get("usage", {}).get("total_tokens", 0)

        # Strip markdown fences if present
        raw = raw.strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        result["_tokens"] = tokens
        return result

    except json.JSONDecodeError:
        return {"error": "DeepSeek returned non-JSON", "raw": raw[:200]}
    except Exception as e:
        return {"error": str(e)[:200]}

# ─── BACKGROUND JOB PROCESSOR ─────────────────────────────────────────────────
async def process_batch_job(job_id: str, videos: list, analysis_type: str, use_cache: bool):
    """
    Tier 2: sequential with asyncio.sleep for rate limiting.
    Tier 4 upgrade: replace with Celery chord over worker pool.
    """
    results = {}
    semaphore = asyncio.Semaphore(MAX_WORKERS)

    async def process_one(video: VideoRequest):
        async with semaphore:
            vid = video.video_id

            # Check cache first
            if use_cache:
                with get_db() as db:
                    cached = db.execute(
                        "SELECT text, language, word_count, error FROM transcripts WHERE video_id = ?",
                        (vid,)
                    ).fetchone()
                if cached and cached["text"]:
                    transcript_data = dict(cached)
                    transcript_data["cached"] = True
                    log.debug(f"Cache hit: {vid}")
                else:
                    cached = None

            if not use_cache or not cached:
                # Fetch transcript (blocking — run in thread pool)
                transcript_data = await asyncio.get_event_loop().run_in_executor(
                    None, fetch_transcript, vid
                )
                transcript_data["cached"] = False

                # Store in DB
                with get_db() as db:
                    db.execute("""
                        INSERT OR REPLACE INTO transcripts
                        (video_id, title, channel, text, language, fetched_at, word_count, error)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        vid, video.title, video.channel,
                        transcript_data.get("text"),
                        transcript_data.get("language"),
                        datetime.utcnow().isoformat(),
                        transcript_data.get("word_count", 0),
                        transcript_data.get("error")
                    ))

                await asyncio.sleep(RATE_DELAY)  # Rate limiting

            # Analyse if we have transcript text
            analysis = None
            if transcript_data.get("text"):
                # Check analysis cache
                with get_db() as db:
                    cached_analysis = db.execute(
                        "SELECT result FROM analyses WHERE video_id = ? AND analysis_type = ?",
                        (vid, analysis_type)
                    ).fetchone()

                if cached_analysis and use_cache:
                    analysis = json.loads(cached_analysis["result"])
                    analysis["_cached"] = True
                else:
                    analysis = await analyse_with_deepseek(
                        transcript_data["text"],
                        video.title,
                        video.channel,
                        analysis_type
                    )
                    tokens = analysis.pop("_tokens", 0)
                    # Store analysis
                    with get_db() as db:
                        db.execute("""
                            INSERT OR REPLACE INTO analyses
                            (video_id, analysis_type, result, model, tokens_used, created_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            vid, analysis_type, json.dumps(analysis),
                            "deepseek-chat", tokens,
                            datetime.utcnow().isoformat()
                        ))
            else:
                # Fallback: title-only DeepSeek analysis
                fallback_text = f"[No transcript] Title: {video.title} Channel: {video.channel}"
                analysis = await analyse_with_deepseek(
                    fallback_text, video.title, video.channel, "classify"
                )
                analysis["_fallback"] = True

            results[vid] = {
                "video_id": vid,
                "title": video.title,
                "channel": video.channel,
                "transcript": {
                    "available": bool(transcript_data.get("text")),
                    "word_count": transcript_data.get("word_count", 0),
                    "language": transcript_data.get("language"),
                    "error": transcript_data.get("error"),
                    "cached": transcript_data.get("cached", False),
                },
                "analysis": analysis
            }

            # Update job progress
            with get_db() as db:
                completed = len(results)
                db.execute("""
                    UPDATE jobs SET completed = ?, updated_at = ?, results = ?
                    WHERE job_id = ?
                """, (completed, datetime.utcnow().isoformat(), json.dumps(results), job_id))

            log.info(f"Job {job_id}: {len(results)}/{len(videos)} — {vid}")

    # Process all videos concurrently up to MAX_WORKERS
    await asyncio.gather(*[process_one(v) for v in videos])

    # Mark job complete
    with get_db() as db:
        db.execute(
            "UPDATE jobs SET status = 'complete', updated_at = ? WHERE job_id = ?",
            (datetime.utcnow().isoformat(), job_id)
        )
    log.info(f"Job {job_id} complete: {len(results)} videos processed")

# ─── ROUTES ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Public health check — no auth required."""
    with get_db() as db:
        transcript_count = db.execute("SELECT COUNT(*) FROM transcripts WHERE text IS NOT NULL").fetchone()[0]
        job_count = db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    return {
        "status": "ok",
        "version": "1.0.0",
        "cached_transcripts": transcript_count,
        "total_jobs": job_count,
        "deepseek_configured": bool(DEEPSEEK_KEY),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/transcript/single")
async def get_single_transcript(
    req: VideoRequest,
    token: str = Depends(verify_token)
):
    """Fetch + cache a single transcript. Synchronous."""
    with get_db() as db:
        cached = db.execute(
            "SELECT * FROM transcripts WHERE video_id = ?", (req.video_id,)
        ).fetchone()

    if cached and cached["text"]:
        return {
            "video_id": req.video_id,
            "cached": True,
            "text_preview": cached["text"][:500] + "...",
            "word_count": cached["word_count"],
            "language": cached["language"],
            "fetched_at": cached["fetched_at"]
        }

    result = await asyncio.get_event_loop().run_in_executor(
        None, fetch_transcript, req.video_id
    )

    with get_db() as db:
        db.execute("""
            INSERT OR REPLACE INTO transcripts
            (video_id, title, channel, text, language, fetched_at, word_count, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            req.video_id, req.title, req.channel,
            result.get("text"), result.get("language"),
            datetime.utcnow().isoformat(),
            result.get("word_count", 0), result.get("error")
        ))

    return {
        "video_id": req.video_id,
        "cached": False,
        "available": bool(result.get("text")),
        "text_preview": (result["text"][:500] + "...") if result.get("text") else None,
        "word_count": result.get("word_count", 0),
        "language": result.get("language"),
        "error": result.get("error")
    }

@app.post("/batch/submit")
async def submit_batch(
    req: BatchRequest,
    background_tasks: BackgroundTasks,
    token: str = Depends(verify_token)
):
    """
    Submit a batch job. Returns job_id immediately.
    Client polls /batch/status/{job_id} for progress.
    Tier 4 upgrade: replace background_tasks with Celery.apply_async()
    """
    job_id = hashlib.md5(
        (str(time.time()) + str([v.video_id for v in req.videos])).encode()
    ).hexdigest()[:12]

    with get_db() as db:
        db.execute("""
            INSERT INTO jobs (job_id, status, total, completed, failed, created_at, updated_at)
            VALUES (?, 'running', ?, 0, 0, ?, ?)
        """, (job_id, len(req.videos), datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))

    background_tasks.add_task(
        process_batch_job, job_id, req.videos, req.analysis_type, req.use_cache
    )

    log.info(f"Job {job_id} submitted: {len(req.videos)} videos, type={req.analysis_type}")
    return {
        "job_id": job_id,
        "total": len(req.videos),
        "status": "running",
        "poll_url": f"/batch/status/{job_id}"
    }

@app.get("/batch/status/{job_id}")
async def batch_status(job_id: str, token: str = Depends(verify_token)):
    """Poll job status. Returns partial results as they complete."""
    with get_db() as db:
        job = db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    results = json.loads(job["results"]) if job["results"] else {}
    return {
        "job_id": job_id,
        "status": job["status"],
        "total": job["total"],
        "completed": job["completed"],
        "failed": job["failed"],
        "progress_pct": round(100 * job["completed"] / max(job["total"], 1)),
        "results": results,
        "created_at": job["created_at"],
        "updated_at": job["updated_at"]
    }

@app.get("/cache/stats")
async def cache_stats(token: str = Depends(verify_token)):
    """Transcript cache statistics."""
    with get_db() as db:
        stats = db.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN text IS NOT NULL THEN 1 ELSE 0 END) as with_transcript,
                SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as with_error,
                SUM(word_count) as total_words,
                AVG(word_count) as avg_words,
                MIN(fetched_at) as oldest,
                MAX(fetched_at) as newest
            FROM transcripts
        """).fetchone()

        analysis_stats = db.execute("""
            SELECT analysis_type, COUNT(*) as count
            FROM analyses GROUP BY analysis_type
        """).fetchall()

    return {
        "transcripts": dict(stats),
        "analyses": {r["analysis_type"]: r["count"] for r in analysis_stats}
    }

@app.delete("/cache/video/{video_id}")
async def clear_cache_entry(video_id: str, token: str = Depends(verify_token)):
    """Force re-fetch on next request for a specific video."""
    with get_db() as db:
        db.execute("DELETE FROM transcripts WHERE video_id = ?", (video_id,))
        db.execute("DELETE FROM analyses WHERE video_id = ?", (video_id,))
    return {"cleared": video_id}

@app.get("/aggregate/insights")
async def aggregate_insights(
    limit: int = 100,
    token: str = Depends(verify_token)
):
    """
    Aggregate all stored analyses into a holistic psychographic report.
    Sends summary to DeepSeek for meta-analysis.
    """
    with get_db() as db:
        analyses = db.execute("""
            SELECT t.title, t.channel, a.analysis_type, a.result
            FROM analyses a
            JOIN transcripts t ON t.video_id = a.video_id
            ORDER BY a.created_at DESC LIMIT ?
        """, (limit,)).fetchall()

    if not analyses:
        raise HTTPException(status_code=404, detail="No analyses in cache yet")

    summaries = []
    for a in analyses:
        try:
            r = json.loads(a["result"])
            summaries.append({
                "title": a["title"],
                "channel": a["channel"],
                "type": a["analysis_type"],
                **r
            })
        except Exception:
            pass

    # Meta-analysis prompt
    prompt = f"""You have {len(summaries)} YouTube video analyses from a single viewer's history.

Here is the aggregated data:
{json.dumps(summaries[:50], indent=2)}

Produce a holistic psychographic profile of this viewer covering:
1. Dominant intellectual interests and their depth
2. Emotional patterns and psychological needs being served
3. Notable behavioural patterns (timing, volume, topic shifts)
4. Viewer archetype (e.g. "The Anxious Intellectual", "The Curious Generalist")
5. Three actionable observations about this person's relationship with media

Be specific, analytical, and grounded in the data. Avoid generic statements."""

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_KEY}"},
            json={
                "model": "deepseek-chat",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]
            }
        )
    data = r.json()
    return {
        "videos_analysed": len(summaries),
        "report": data["choices"][0]["message"]["content"],
        "tokens_used": data.get("usage", {}).get("total_tokens", 0)
    }

# ─── STARTUP ──────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    init_db()
    log.info("MindMap server ready")
    log.info(f"Auth token: {'SET' if API_TOKEN != 'changeme-set-in-env' else 'WARNING: using default!'}")
    log.info(f"DeepSeek: {'configured' if DEEPSEEK_KEY else 'NOT configured'}")
    log.info(f"Workers: {MAX_WORKERS}, Rate delay: {RATE_DELAY}s")

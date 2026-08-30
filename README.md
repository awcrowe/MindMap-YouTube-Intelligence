# MindMap — YouTube Viewing Intelligence

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688)](https://fastapi.tiangolo.com)

**MindMap** transforms your YouTube watch history into a rich psychographic dashboard with AI‑generated insights.  
It works in **two modes**:

- **Standalone (client‑only)** – upload your YouTube history JSON file directly in the browser.  
  Uses local classification and optional DeepSeek API for advanced categorisation.  
- **Client‑Server (full stack)** – deploy the FastAPI backend on your own VPS.  
  Fetch transcripts, analyse with DeepSeek, and store results for deeper aggregate reporting.

---

## ✨ Features

- 📊 **Interactive Dashboard** – viewing habits, hourly patterns, category mix, channel ranking.
- 🧠 **Psychometric Indicators** – curiosity, political engagement, escapism, nocturnal viewing.
- 🔥 **Activity Heatmap** – daily density with drill‑down tooltips.
- 🤖 **AI Classification** – uses DeepSeek to classify “Other” videos into 12 categories.
- 📜 **Transcript Analysis** – when connected to the VPS backend, analyse full video transcripts for synopsis, tone, topics, and psychometric signals.
- 📦 **Offline Support** – the standalone HTML works fully offline (except optional AI calls) – just drop your history file.

---

## 🚀 Quick Start

### 1. Standalone (no server)
- Open `src/client/index.html` in your browser (best served via `python3 -m http.server 8080`).
- Export your YouTube history from [Google Takeout](https://takeout.google.com) → YouTube → History (JSON).
- Drag & drop the JSON file into the app – the dashboard will build instantly.
- Optionally add your DeepSeek API key in the settings for AI classification.

### 2. Full Client‑Server (VPS)
- Deploy the backend on an Ubuntu 24 VPS using the provided `install.sh`.
- Set your environment variables (DeepSeek key, API token) in `.env`.
- Open the HTML client, click the gear icon, enter your VPS URL and API token.
- Now you can send videos for transcript analysis and generate aggregate reports.

---

## 🖥️ Server Deployment (Ubuntu 24)

```bash
# Clone this repo (or copy the src/ folder)
cd /opt/mindmap
sudo bash install.sh

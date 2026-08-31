# Standalone Mode (No Server)

The HTML file (`src/client/index.html`) works entirely in your browser. You can use it without any backend—perfect for local analysis or sharing a single file.

## How to Use

1. **Open the HTML**  
   For best results, serve it via a local web server:
   ```bash
   cd src/client
   python3 -m http.server 8080
   
   Then open http://localhost:8080.

2. Export Your YouTube History
   · Go to Google Takeout
   · Select YouTube → History → choose JSON format.
   · Download the archive and extract the watch-history.json file.
3. Upload the File
   · Drag and drop the JSON file (or CSV) onto the upload area.
   · You can also upload a gzipped bundle (mindmap-enriched.json.gz) for faster loading if you have pre‑enriched data.
4. Explore the Dashboard
   · KPI row: total videos, active days, peak hour, top category.
   · Heatmap: daily activity with colour intensity.
   · Charts: monthly volume, category mix, hour distribution, weekday radar.
   · Psychometric indicators: curiosity, political engagement, escapism, nocturnal viewing.
   · Top channels list.
5. AI Classification (Optional)
   · Click the gear icon and paste your DeepSeek API key.
   · Use the “Re‑classify Categories (AI)” button to have DeepSeek assign categories to “Other” videos.

Limitations

· Transcript analysis requires the VPS backend—standalone mode cannot fetch transcripts.
· Without AI, classification uses a local keyword heuristic (accuracy ~60–70%).

Benefits

· No data leaves your machine (except optional DeepSeek API calls).
· Works offline (once loaded).
· Instant—no deployment needed.

```
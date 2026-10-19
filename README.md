# Kubernetes in 15s — Daily Reel Bot (100% free)

Every day this bot makes a 15-second vertical reel on one Kubernetes topic and posts it to YouTube Shorts automatically.

```
topics.txt ──► Gemini (script) ──► Edge TTS (voice) ──► Pillow + FFmpeg (motion graphics)
                                                               │
                        GitHub Actions (daily, 7 PM IST) ──► YouTube Shorts
```

| Part | Tool | Cost |
|---|---|---|
| Daily scheduler | GitHub Actions (cron) | Free |
| Script | Gemini API (Google AI Studio free tier) | Free |
| Voice | Microsoft Edge TTS (`en-IN-PrabhatNeural`) | Free |
| Video | Python Pillow + FFmpeg | Free |
| Posting | YouTube Data API | Free |

## Files

- `topics.txt` — 60 topics; the bot takes the next one each day. Add or edit as you like.
- `queue/day_N.json` — if a file exists for that day, your hand-checked script is used instead of the AI one. Day 1 is ready.
- `src/main.py` — the full daily pipeline
- `src/render.py` — motion graphics design (change colours, timing and animation here)
- `src/voice.py` — voiceover
- `state.json` — which day has been posted (the bot updates it)
- `scripts_log/` — record of each day's generated script

---

## Setup (about 2–3 hours, one time)

### Step 1 — GitHub repo. aman42january@gmail.com
1. Create a new **private** repo on github.com, e.g. `k8s-reels`.
2. Push this folder to it:
   ```bash
   cd k8s-reels
   git init && git add . && git commit -m "Reel bot"
   git branch -M main
   git remote add origin https://github.com/<your-username>/k8s-reels.git
   git push -u origin main
   ```

### Step 2 — Gemini API key (for scripts)
1. Open https://aistudio.google.com/apikey → **Create API key**.
2. GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**
   - `GEMINI_API_KEY` = your key

### Step 3 — YouTube
1. Create a new project at https://console.cloud.google.com.
2. **APIs & Services → Library** → "YouTube Data API v3" → **Enable**.
3. **OAuth consent screen** → User type: External → add your Gmail as a **Test user** → **Publish app** (In production). Otherwise the refresh token expires after 7 days.
4. **Credentials → Create credentials → OAuth client ID** → Application type: **Desktop app** → download the JSON and save it in this folder as `client_secret.json` (it is git-ignored).
5. Run once on your Mac:
   ```bash
   pip3 install google-auth-oauthlib
   python3 scripts/get_youtube_token.py client_secret.json
   ```
   Sign in with the Google account that owns your YouTube channel. If you see "Google hasn't verified this app", click **Advanced → Go to app**.
   Example values will be printed like this:
   - `YT_CLIENT_ID = your_client_id_here`
   - `YT_CLIENT_SECRET = your_client_secret_here`
   - `YT_REFRESH_TOKEN = your_refresh_token_here`
6. Add the three printed values as GitHub secrets: `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.

> **Note:** Until Google audits your app, videos uploaded through the API stay **private**, so `YT_PRIVACY` defaults to `private`. Request the audit with the free "YouTube API Services Audit and Quota Extension Form" in Google Cloud. Until then, you can make each Short public with one click in YouTube Studio.

### Step 4 — Optional future expansion
This version is configured for **YouTube only**. Instagram publishing is intentionally disabled by default.

If you want to re-enable it later, bring back the Instagram upload logic and the `POST_INSTAGRAM` / `IG_*` variables.

### Step 5 — Variables (optional)
**Settings → Secrets and variables → Actions → Variables** tab:

| Variable | Meaning | Default |
|---|---|---|
| `CHANNEL_HANDLE` | Name shown on the video, e.g. `@amandeep.cloud` | empty |
| `REEL_LANGUAGE` | `english` or `hinglish` | `english` |
| `YT_PRIVACY` | `private` / `unlisted` / `public` | `private` |
| `POST_YOUTUBE` | set `false` to turn YouTube posting off | `true` |
| `DRY_RUN` | `true` = only make the video, don't post | `false` |
| `GEMINI_MODEL` | Gemini model name (update here if it changes) | `gemini-2.0-flash` |

### Step 6 — Test (without posting)
1. Repo → **Actions → Daily Kubernetes Reel → Run workflow** → tick `dry_run` → Run.
2. After 3–5 minutes, open the run → download the `reel-…` zip under **Artifacts** and watch the video.

### Step 7 — Go live
- Run the workflow once with `dry_run` unticked. The post should appear on YouTube.
- From then on it runs automatically every day at **13:10 UTC (6:40 PM IST / 12:10 AM Sydney)**. To change the time, edit `cron` in `.github/workflows/daily-reel.yml`.

---

## Tips

- **Check scripts for the first 2–3 weeks.** AI sometimes makes technical mistakes. Easiest way: write or review the next few days' scripts and save them as `queue/day_N.json` (see `queue/day_1.json` for the format).
- **Your own voice:** later, replace Edge TTS in `src/voice.py` with open-source voice cloning (XTTS / F5-TTS).
- **Monetization:** YouTube does not monetize fully automated content with no human contribution. Post some videos with your own voice or face too.
- **Free limits:** GitHub Actions gives 2,000 minutes/month free for private repos; this bot uses about 5 minutes a day (~150 minutes/month). The YouTube API gives 10,000 quota units a day; one upload uses about 1,600.

## Troubleshooting

| Error | Fix |
|---|---|
| `Gemini busy (429)` | Free-tier limit; the script retries 4 times automatically. If it keeps happening, change `GEMINI_MODEL`. |
| `invalid_grant` (YouTube) | Refresh token expired. Check step 3.3 (Publish app), then repeat step 3.5. |
| Video shows as private | Normal until the audit is approved (see Step 3 note). |

# Deploying PhytoSense AR (free)

PhytoSense AR deploys to **Render's free web service**. It costs nothing, and Render provides a public `https://` link, so the camera works on any phone.

The AI model runs as an 87 MB int8 ONNX file (no PyTorch). Measured peak memory is about **230 MB**, under Render's 512 MB free limit.

| Option | Cost | Public link | Phone camera |
| --- | --- | --- | --- |
| **A. Render free web service** (recommended) | Free | Yes, `https://phytosense-ar.onrender.com` | Yes |
| B. Laptop + HTTPS on Wi-Fi (`run_https.cmd`) | Free | Same Wi-Fi only | Yes (accept warning once) |
| C. Any Docker host (`Dockerfile`) | Depends | Yes | Needs HTTPS |

> Hugging Face Docker Spaces now need a paid PRO plan. Vercel's Python functions cannot hold the model (250 MB bundle limit). Render is the free option that fits.

---

## A. Render (about 15 minutes)

### 1. Put the project on GitHub
1. Create a free account at <https://github.com> and a **new empty repository** named `phytosense-ar` (no README).
2. In a terminal:
```bat
cd c:\project\Major_project\PhytoSense-AR
git init
git add .
git commit -m "PhytoSense AR MVP"
git branch -M main
git remote add origin https://github.com/<your-github-username>/phytosense-ar.git
git push -u origin main
```
The push takes a minute: it includes the 87 MB model file (`backend/model/model.onnx`), which is under GitHub's 100 MB limit. GitHub may print a "large file" warning; that is fine.

### 2. Deploy on Render
1. Sign up at <https://render.com> with your GitHub account. The free plan may ask you to verify with a card; free services are not charged.
2. Click **New → Blueprint**, pick the `phytosense-ar` repository, then click **Apply**.
   Render reads [`render.yaml`](render.yaml) and creates a **free** web service called `phytosense-ar`.
3. It asks for `GEMINI_API_KEY`. Paste a free key from <https://aistudio.google.com/app/apikey>, or leave it empty to use the offline assistant.
4. Wait for **Live** in the dashboard. The first deploy takes about 3–5 minutes.

Your app is live at **`https://phytosense-ar.onrender.com`**. Render adds a suffix if that name is taken; the exact link is shown at the top of the service page.

<details>
<summary>Manual setup instead of Blueprint</summary>

**New → Web Service** → pick the repo, then set:
- Runtime **Python 3**, Instance type **Free**
- Build command: `pip install -r backend/requirements.txt`
- Start command: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Environment variables: `PYTHON_VERSION=3.11.9`, `PHYTO_THREADS=1`, optional `GEMINI_API_KEY`
</details>

### 3. Use it on a phone
Open the link in Chrome, allow the camera, then **⋮ → Add to Home screen** to install it like an app.

### 4. Update after code changes
```bat
git add . && git commit -m "update" && git push
```
Render redeploys automatically.

### Free-tier behaviour (say this in the viva)
- **Sleeps after 15 minutes without visitors.** The next visit takes about 1 minute to wake it. Open the link 5 minutes before your demo.
- **Slow shared CPU (0.1 CPU).** A full diagnosis takes a few seconds and the live AR overlay updates slowly. For the smoothest live AR demo, run it from your laptop (option B).
- **History is temporary.** It resets on every redeploy or restart. Everyone using the link shares one history, capped at 500 scans.

### Settings (Render → service → Environment)
| Variable | Default | Meaning |
| --- | --- | --- |
| `GEMINI_API_KEY` | – | Enables the Gemini assistant (free key). |
| `GEMINI_MODEL` | auto | Force a specific Gemini model. |
| `PHYTO_THREADS` | `1` on Render | CPU threads for the model. |
| `PHYTO_MIN_CONFIDENCE` | `0.55` | Below this the app says "Not sure – retake". |
| `PHYTO_MAX_SCANS` | `500` | Older scans are deleted beyond this. |

### Troubleshooting
| Symptom | Fix |
| --- | --- |
| Build fails at `pip install` | Check that `PYTHON_VERSION` is `3.11.9`, then **Manual Deploy → Clear build cache & deploy**. |
| `Out of memory` in Logs | Set `PHYTO_THREADS=1`. |
| Page loads but says "AI model is loading…" | Wait about 20 seconds after waking; check Logs for `[classifier] loaded ONNX model`. |
| `git push` rejected: file too large | Make sure `backend/model/model.onnx` is the 87 MB int8 file (re-create it with `python scripts/export_onnx.py`). |
| Camera does not open | Use the `https://` link, and allow camera permission in the browser's site settings. |

---

## B. Demo from your laptop (fastest, works offline)

```bat
setup.cmd          :: one time
run.cmd            :: laptop → http://localhost:8000
run_https.cmd      :: phones on the same Wi-Fi → https://<laptop-ip>:8443 (printed in the console)
```
On the phone, accept the "connection not private" warning once (self-signed certificate). If Windows Firewall asks, allow Python on **Private networks**.

---

## C. Any Docker host

```bash
docker build -t phytosense-ar .
docker run -d -p 7860:7860 -e GEMINI_API_KEY=your_key -v phyto-data:/home/user/app/backend/storage phytosense-ar
```
The container listens on `$PORT` (default 7860), needs under 512 MB RAM, and the `-v` volume keeps history across restarts. If the build fails with `Network is unreachable` (Docker Desktop behind a VPN), build with `docker build --network=host -t phytosense-ar .`

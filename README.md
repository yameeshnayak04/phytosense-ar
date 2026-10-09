# 🌿 PhytoSense AR
### AR-Based AI Plant Health Identification and Disease Diagnosis System

*College major project – MVP.* Point a phone camera at a leaf: PhytoSense AR outlines the leaf, highlights the diseased spots **live on the camera view (augmented reality)**, names the disease, scores its severity, and tells you how to treat and prevent it, with an AI assistant you can ask follow-up questions in English or Indian languages.

Everything is **free and open-source**: no paid API, no GPU, no hardware needed.

---

## ✨ Features (MVP)

| Module | What it does |
| --- | --- |
| **AR Live Scanner** | Camera feed with a live overlay: dashed leaf outline, pulsing red lesion patches, corner brackets and a floating label (*crop · disease · confidence · infected % · health*). |
| **Disease Diagnosis** | 38 PlantVillage classes across 14 crops (Vision Transformer, int8 ONNX – 87 MB, no PyTorch). Leaf is segmented first and the crop of the leaf is classified. |
| **Severity & Health score** | Infected-area % from lesion segmentation → severity (early / moderate / severe) and a 0–100 health score. |
| **Treatment knowledge base** | Symptoms, cause, chemical + organic treatment, prevention for every class; Hindi crop names. |
| **Crop info** | Scientific name + Wikipedia summary of the crop. |
| **AI Assistant** | Google Gemini (free tier) with the scan as context, farming-only prompt, 9 languages, voice input. Works **offline** from the knowledge base when no API key is set. |
| **History** | Every saved scan with photo, stats and a health-trend chart (SQLite). |
| **Disease Library** | Searchable list of all 38 classes, filter by crop. |
| **Installable PWA** | Add to home screen on Android; app shell works offline. Read-aloud of results. |

## 🧱 Architecture

```
Phone / laptop browser (PWA)                 FastAPI backend (Python)                Free services
┌──────────────────────────┐   frame/photo   ┌──────────────────────────────┐
│ Camera (getUserMedia)    │ ──────────────▶ │ vision.py  leaf + lesion     │
│ AR canvas overlay        │                 │            segmentation (CV) │
│ Result sheet, History,   │ ◀────────────── │ classifier.py  ViT ONNX int8 │   (model file ships in backend/model)
│ Assistant, Library       │   JSON result   │ knowledge.py   treatment KB  │──▶ Wikipedia REST API
└──────────────────────────┘                 │ assistant.py   chat          │──▶ Gemini API (optional)
                                             │ db.py          SQLite history│
                                             └──────────────────────────────┘
```

**Pipeline per image:** HSV + Excess-Green segmentation finds the leaf (background model from the image border removes shadows/table) → symptom-coloured pixels inside the leaf become lesion polygons → leaf is cropped and classified by the ViT → knowledge-base lookup → severity, health score, overlay geometry returned as JSON → the browser draws the AR layer.

Live AR sends a 448-px frame to `/api/frame` as soon as the previous answer arrives (≈2–3 overlay updates/s on a laptop CPU). The shutter sends a full-resolution photo to `/api/diagnose`, which is saved to history.

## 🚀 Run it (Windows)

Requires **Python 3.10+**.

```bat
setup.cmd        :: one time – creates backend\.venv and installs the requirements
run.cmd          :: starts the server and opens http://localhost:8000
```

The model file is included, so the app runs fully offline (except Wikipedia/Gemini). Uses about 230 MB RAM.

Manual / Linux / macOS:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Use your phone's camera
Browsers only allow the camera on `https://` or `localhost`. On the same Wi-Fi:

```bat
run_https.cmd    :: creates a self-signed certificate and serves https://<laptop-ip>:8443
```
Open the printed address on the phone, accept the "not secure" warning once, then **Add to Home screen**. (Alternative: a free tunnel such as `cloudflared tunnel --url http://localhost:8000`.)

### Turn on the Gemini assistant (optional, free)
1. Get a key at <https://aistudio.google.com/app/apikey>.
2. Copy `backend/.env.example` to `backend/.env` and set `GEMINI_API_KEY=...`.
3. Restart. The header shows `assistant: gemini`. The newest available *flash* model is picked automatically (or set `GEMINI_MODEL`).

### Deploy for free (public HTTPS link)
Push the folder to GitHub, then on <https://render.com> choose **New → Blueprint** and pick the repo. [`render.yaml`](render.yaml) sets up a free web service at `https://phytosense-ar.onrender.com`.
Full step-by-step guide, options and troubleshooting: **[DEPLOYMENT.md](DEPLOYMENT.md)**.

## 🧪 Tests & evaluation

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest -q                     # 8 tests: segmentation, knowledge base, API, history cap, chat
python ../scripts/evaluate.py --n 100   # accuracy on random PlantVillage test images
```

Measured with the int8 ONNX model (laptop CPU, no GPU), 100 random images from the PlantVillage test split:

| Metric | Value |
| --- | --- |
| Top-1 accuracy | **99.0 %** (1 error: northern leaf blight ↔ gray leaf spot) |
| Mean confidence | 98.3 % |
| Time per image (segmentation + classification) | ~190 ms on a laptop CPU (int8 ONNX); a few seconds on Render free (0.1 CPU) |

> ⚠️ PlantVillage photos are single detached leaves on plain backgrounds, and the model card notes possible train/test overlap. **Expect lower accuracy on real field photos** – report field results separately (see *Limitations*).

## 🔌 API (auto docs at `/docs`)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/status` | model ready, classes, assistant mode, languages |
| POST | `/api/diagnose` | full diagnosis of an uploaded image (multipart `file`), saved to history |
| POST | `/api/frame` | fast live-AR analysis of a camera frame (not saved) |
| GET | `/api/scans`, `/api/scans/{id}` | history list + stats / one scan |
| PATCH / DELETE | `/api/scans/{id}` | add note / delete scan |
| GET | `/api/diseases` | knowledge base (library) |
| POST | `/api/chat` | assistant `{message, history, context, lang}` |

## 📁 Project structure

```
PhytoSense-AR/
├── backend/
│   ├── app/
│   │   ├── main.py          FastAPI app, routes, serves the frontend
│   │   ├── vision.py        leaf + lesion segmentation (OpenCV) → AR geometry, severity
│   │   ├── classifier.py    ViT disease classifier (ONNX Runtime)
│   │   ├── diagnosis.py     pipeline: segment → classify → score → knowledge
│   │   ├── knowledge.py     knowledge base lookup + Wikipedia
│   │   ├── assistant.py     Gemini / offline assistant
│   │   ├── db.py            SQLite scan history
│   │   └── config.py        settings from .env
│   ├── data/knowledge_base.json
│   ├── tests/test_api.py
│   ├── model/               model.onnx (int8 ViT) + labels.json
│   └── requirements.txt, requirements-dev.txt
├── frontend/                 PWA (plain HTML/CSS/JS modules – no build step)
│   ├── index.html, css/, js/ (app, ar, overlay, result, history, chat, library, util)
│   ├── samples/              demo leaf images
│   ├── manifest.webmanifest, sw.js, icons/
├── scripts/                  export_onnx.py (model export), make_cert.py (HTTPS), evaluate.py (accuracy)
├── samples/                  PlantVillage test images used in tests
├── render.yaml, Dockerfile, DEPLOYMENT.md, setup.cmd, run.cmd, run_https.cmd
```

## 📚 What came from the reference projects

| Reference | Used in PhytoSense AR |
| --- | --- |
| **Plant-disease-detction (PlantDoc)** | `/api/predict`-style flow, severity idea (confidence + infected area), class→treatment mapping, Gemini farming chatbot |
| **Agri-Lens** | FastAPI serving pattern, segmentation (pixel-level) instead of plain boxes, UML/report structure |
| **KisanAI** | knowledge-base fields (symptoms, treatment, organic, prevention), farming-only prompt + offline fallback, multilingual answers |
| **PlantVerse AR** | Hugging Face `image-classification` pipeline approach, Wikipedia crop info |
| **AgriPro** | ideas: treatment suggestions, progress tracking (history + trend), knowledge hub (library) |

**New in this project:** the camera-anchored AR overlay (leaf outline + lesion highlighting on the live video), the background-aware leaf/lesion segmentation, and the health score.

## ⚠️ Limitations (state these in the viva)

- Classifier knows **38 PlantVillage classes / 14 crops only**; any other plant is forced into one of them. Low confidence (< 55 %) is shown as *"Not sure – retake"*.
- Lesion highlighting is colour-based: excellent for spots/blight/rust, weak for diffuse symptoms (mites, mosaic, citrus greening mottling) and for photos with many overlapping leaves.
- Live AR needs the server (~0.3–0.4 s per frame on CPU); it is a 2D overlay on the video, not world-anchored 3D AR.
- Treatment advice is general guidance – always confirm with the local agriculture officer / KVK.
- No user accounts (single-user history) – fine for an MVP demo.

## 🔮 Future work

1. Fine-tune a **YOLOv8n-seg / YOLO11n-seg** model on PlantDoc + own field photos (notebooks in the PlantDoc and Agri-Lens references) for true per-lesion detection.
2. Export to **ONNX Runtime Web / TF.js** to run the live AR fully on the phone.
3. Add an "unknown plant" class / species identifier (Pl@ntNet API) before disease classification.
4. Login + cloud database (Supabase free tier), weather-based disease-risk alerts, multi-leaf detection.

## 📄 Credits & licences
- Disease model: [`kimcomehome/plantvillage-vit-leaf-disease`](https://huggingface.co/kimcomehome/plantvillage-vit-leaf-disease) (ViT-base fine-tuned on PlantVillage, CC BY-SA 3.0), exported to int8 ONNX by `scripts/export_onnx.py`.
- Dataset: PlantVillage (Hughes & Salathé, 2015). Sample images from the PlantVillage test split.
- Crop summaries: Wikipedia REST API.

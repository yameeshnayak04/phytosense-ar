# 🌿 PhytoSense AR
### AR-Based AI Plant Health Identification and Disease Diagnosis System

*College major project.* Point a phone camera at a plant: PhytoSense AR **identifies the plant** (68 species: 55 plants common in Indore / central India such as money plant, rose, banyan, peepal, neem, tulsi and gulmohar, plus 13 crops), outlines the leaf, highlights the diseased spots **live on the camera view (augmented reality)**, names the disease or leaf condition, scores its severity, and tells you how to treat and prevent it, with an AI assistant you can ask follow-up questions in English or Indian languages.

Everything is **free and open-source**: no paid API, no GPU, no hardware needed.

---

## ✨ Features

| Module | What it does |
| --- | --- |
| **Plant identification** | ConvNeXt-Tiny (int8 ONNX, 34 MB) trained on iNaturalist field photos: 68 species + *not a plant*. Shows Hindi name, scientific name, top-3 alternatives, care tips, common problems and toxicity warnings (kaner, aak, parthenium…). |
| **Leaf condition (any plant)** | Second head of the same model: healthy, leaf spot / blight, powdery mildew, rust, sooty mould, mosaic / yellowing, pest infestation – used for plants without a crop-specific disease model. |
| **AR Live Scanner** | Camera feed with a live overlay: dashed leaf outline, pulsing red lesion patches, corner brackets and a floating label (*crop · disease · confidence · infected % · health*). |
| **Crop disease diagnosis** | 38 classes across 14 crops (Vision Transformer fine-tuned on PlantVillage + PlantDoc field photos, int8 ONNX). Once the plant model says "tomato", only tomato diseases are considered. Live labels are stabilised by a vote over the last 6 frames. |
| **Severity & Health score** | Infected-area % from lesion segmentation → severity (early / moderate / severe) and a 0–100 health score. |
| **Treatment knowledge base** | Symptoms, cause, chemical + organic treatment, prevention for every class; Hindi crop names. |
| **Crop info** | Scientific name + Wikipedia summary of the crop. |
| **AI Assistant** | Google Gemini (free tier) with the scan as context, farming-only prompt, 9 languages, voice input. Works **offline** from the knowledge base when no API key is set. |
| **History** | Every saved scan with photo, stats and a health-trend chart (SQLite). |
| **Library** | Searchable plants (by type), crop diseases (by crop) and leaf conditions. |
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

**Pipeline per image:** HSV + Excess-Green segmentation finds the leaf (background model from the image border removes shadows/table) → symptom-coloured pixels inside the leaf become lesion polygons → the **plant model** identifies the species from the whole frame + leaf crop → crops with a disease model (tomato, potato, maize, grape, citrus, …) go to the **ViT restricted to that crop's diseases**; every other plant gets the **leaf-condition** result → knowledge-base lookup → severity, health score, overlay geometry returned as JSON → the browser draws the AR layer. For plants with naturally coloured leaves (croton, coleus, variegated money plant …) colour-based severity is switched off.

Without `backend/model/plant_model.onnx` the app falls back to the crop-disease model only.

Live AR sends a 448-px frame to `/api/frame` as soon as the previous answer arrives (≈2–3 overlay updates/s on a laptop CPU). The shutter sends a full-resolution photo to `/api/diagnose`, which is saved to history.

## 🚀 Run it (Windows)

Requires **Python 3.10+**.

```bat
setup.cmd        :: one time – creates backend\.venv and installs the requirements
run.cmd          :: starts the server and opens http://localhost:8000
```

The model files are included, so the app runs fully offline (except Wikipedia/Gemini). Uses about 320 MB RAM with both models loaded.

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

### Train the plant-identification model (free Colab GPU) – **required for plant ID**

[training/train_plant_id_model.ipynb](training/train_plant_id_model.ipynb) downloads ~20,000 openly licensed iNaturalist field photos (Indian observations first) for the 68 species and 6 symptom groups, plus PlantVillage, PlantDoc and Imagenette (*not a plant*), and trains ConvNeXt-Tiny with a species head and a leaf-condition head.

1. Open it in [Google Colab](https://colab.research.google.com), *Runtime → Change runtime type → T4 GPU → Run all* (~60–80 min).
2. Unzip the downloaded `phytosense_plant_model.zip` into `backend/model/` (`plant_model.onnx`, `plant_labels.json`, `plant_metrics.json`, `inat_attribution.csv`).
3. Restart the app; the status line shows *68 plants*.

To change the plant list, edit `LOCAL_PLANTS` in [training/build_plant_notebook.py](training/build_plant_notebook.py), regenerate the notebook, and add the plant to [backend/data/plants.json](backend/data/plants.json) (a test checks both lists match).

### Train for real field photos (free Colab GPU)

[training/train_field_model.ipynb](training/train_field_model.ipynb) fine-tunes the model on **PlantVillage + PlantDoc** (real field photos with cluttered backgrounds), using augmentation for zoom, rotation, lighting and blur. It prints before/after accuracy on the PlantDoc test set (real photos the model never saw during training).

1. Open the notebook in [Google Colab](https://colab.research.google.com) (*File → Upload notebook*), then *Runtime → Change runtime type → T4 GPU → Run all* (~30–45 min).
2. Unzip the downloaded `phytosense_model.zip` into `backend/model/` (replaces `model.onnx` + `labels.json`; `metrics.json` holds the report numbers).
3. Restart the app. The labels are the same, so no code changes are needed.

**Results of this fine-tuning (the model now in `backend/model/`; old one in `backend/model_backup_plantvillage/`):**

| Test set | Original model | Fine-tuned | Fine-tuned, int8 ONNX (what the app runs) |
| --- | --- | --- | --- |
| PlantDoc test – **real field photos** (236 images, unseen) | 37.7 % | 75.4 % | **76.7 %** |
| PlantVillage held-out – lab photos (760 images) | 100 % | 100 % | 99.9 % |

Strongest on real photos: apple, grape, squash, strawberry, corn rust, healthy leaves (80–100 %). Weakest: corn gray leaf spot, potato early blight, tomato bacterial spot (25–45 %), which look alike in the field. Full numbers are in `backend/model/metrics.json`.

**Plant-identification model results** (`backend/model/plant_metrics.json`, held-out test split of 4,808 images, int8 ONNX):

| Metric | Value |
| --- | --- |
| Species top-1 / top-5 (68 plants + *not a plant*) | **90.5 %** / 98.2 % |
| Local plants, iNaturalist field photos | 88.7 % top-1, 97.7 % top-5 |
| Crop recognised on PlantDoc field photos | 93.2 % |
| Leaf condition (7 groups) | **96.6 %** |
| Unseen Wikipedia photos (20 local plants + car, cat, laptop) | 23 / 23 correct |
| Model size / CPU time | 34 MB / ~165 ms for 2 views |

Hardest species: mango, arjun, jamun, banyan, eucalyptus (52–75 %) – large trees photographed from far away, often confused with similar trees.

## 🔌 API (auto docs at `/docs`)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/status` | models ready, crop classes, plant species, assistant mode, languages |
| POST | `/api/diagnose` | full diagnosis of an uploaded image (multipart `file`), saved to history |
| POST | `/api/frame` | fast live-AR analysis of a camera frame (not saved) |
| GET | `/api/scans`, `/api/scans/{id}` | history list + stats / one scan |
| DELETE | `/api/scans/{id}` | delete scan |
| GET | `/api/plants` | plants the model identifies + leaf conditions (library) |
| GET | `/api/diseases` | crop-disease knowledge base (library) |
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
│   ├── app/                  main (API), diagnosis (pipeline), vision (segmentation), classifier (crop diseases),
│   │                         plant_id (plant + leaf condition), knowledge, assistant, db, config
│   ├── data/                 knowledge_base.json (crop diseases), plants.json (68 plants), conditions.json (7 conditions)
│   ├── tests/test_api.py
│   ├── model/                model.onnx (int8 ViT, crop diseases) + labels.json,
│   │                         plant_model.onnx (int8 ConvNeXt-Tiny, plants + conditions) + plant_labels.json, metrics, iNaturalist attribution
│   └── requirements.txt, requirements-dev.txt
├── frontend/                 PWA (plain HTML/CSS/JS modules – no build step)
│   ├── index.html, css/, js/ (app, ar, overlay, result, history, chat, library, util)
│   ├── samples/              demo leaf images
│   ├── manifest.webmanifest, sw.js, icons/
├── training/                 Colab notebooks: train_field_model.ipynb (crop diseases), train_plant_id_model.ipynb (plants)
├── scripts/                  export_onnx.py (model export), make_cert.py (HTTPS), evaluate.py (accuracy)
├── docs/                     IEEE paper draft + figures
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

- Plant ID covers 68 species; other plants are shown as *Unknown plant* below 35 % confidence, but may still be confused with a similar-looking species. Leaf conditions are general groups, not exact disease names, and nutrient deficiencies are only covered under *mosaic / yellowing*.
- Crop disease classifier knows **38 PlantVillage classes / 14 crops**. Field accuracy is ~77 % (PlantDoc test); orange greening, grape Esca/leaf blight and tomato target spot have no field training photos. Low confidence (< 55 %) is shown as *"Not sure – retake"*.
- Lesion highlighting is colour-based: excellent for spots/blight/rust, weak for diffuse symptoms (mites, mosaic, citrus greening mottling) and for photos with many overlapping leaves.
- Live AR needs the server (~0.4–0.6 s per frame on a laptop CPU, much slower on the free Render plan); it is a 2D overlay on the video, not world-anchored 3D AR.
- Treatment advice is general guidance – always confirm with the local agriculture officer / KVK.
- No user accounts (single-user history).

## 🔮 Future work

1. Fine-tune a **YOLOv8n-seg / YOLO11n-seg** model on PlantDoc + own field photos (notebooks in the PlantDoc and Agri-Lens references) for true per-lesion detection.
2. Export to **ONNX Runtime Web / TF.js** to run the live AR fully on the phone.
3. Collect own field photos of Indore plants to measure and improve local accuracy; add more species and exact diseases for common ornamentals (e.g. rose black spot vs. other leaf spots).
4. Login + cloud database (Supabase free tier), weather-based disease-risk alerts, multi-leaf detection.

## 📄 Credits & licences
- Disease model: [`kimcomehome/plantvillage-vit-leaf-disease`](https://huggingface.co/kimcomehome/plantvillage-vit-leaf-disease) (ViT-base fine-tuned on PlantVillage, CC BY-SA 3.0), exported to int8 ONNX by `scripts/export_onnx.py`.
- Datasets: PlantVillage (Hughes & Salathé, 2015), PlantDoc (Singh et al., 2020), iNaturalist research-grade observations (CC0 / CC BY / CC BY-NC / CC BY-SA photos – per-photo attribution in `backend/model/inat_attribution.csv`), Imagenette (*not a plant* class). Sample images from the PlantVillage test split.
- Plant model: ConvNeXt-Tiny (`convnext_tiny.fb_in22k_ft_in1k`, timm, Apache-2.0) fine-tuned by `training/train_plant_id_model.ipynb`.
- Crop summaries: Wikipedia REST API.

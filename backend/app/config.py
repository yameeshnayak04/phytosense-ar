"""Central settings, read from environment variables (or backend/.env)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent
load_dotenv(BACKEND_DIR / ".env")

FRONTEND_DIR = PROJECT_DIR / "frontend"
DATA_DIR = BACKEND_DIR / "data"
STORAGE_DIR = BACKEND_DIR / "storage"
UPLOAD_DIR = STORAGE_DIR / "uploads"
DB_PATH = STORAGE_DIR / "phytosense.db"

# Source model on Hugging Face (PlantVillage, 38 classes). The app runs its int8
# ONNX export from MODEL_DIR; scripts/export_onnx.py regenerates it.
MODEL_ID = os.getenv("PHYTO_MODEL", "kimcomehome/plantvillage-vit-leaf-disease")
MODEL_DIR = BACKEND_DIR / "model"
ONNX_THREADS = int(os.getenv("PHYTO_THREADS", "2"))

# Plant identification + leaf-condition model (training/train_plant_id_model.ipynb).
PLANT_MODEL_FILE = "plant_model.onnx"

# Below this confidence the app asks the user to retake the photo.
MIN_CONFIDENCE = float(os.getenv("PHYTO_MIN_CONFIDENCE", "0.55"))
# Below this the species is shown as "Unknown plant" (best guess listed as an alternative).
MIN_SPECIES_CONFIDENCE = float(os.getenv("PHYTO_MIN_SPECIES_CONFIDENCE", "0.35"))

# Oldest scans (and their photos) are deleted beyond this many – keeps a public
# deployment's disk from filling up.
MAX_SCANS = int(os.getenv("PHYTO_MAX_SCANS", "500"))

# Optional: Google Gemini (free tier) for the assistant. Without a key the
# assistant answers from the local knowledge base.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "").strip()

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

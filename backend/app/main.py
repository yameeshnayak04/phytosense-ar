"""PhytoSense AR – FastAPI backend.

Run from the backend folder:  uvicorn app.main:app --reload
Then open http://localhost:8000
"""
from __future__ import annotations

import io
import threading
import uuid
from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field

from . import assistant, config, db, knowledge
from .classifier import classifier
from .diagnosis import diagnose
from .plant_id import plant_identifier

MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_SIDE = 1600


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init()
    # Load the models in the background so the server answers immediately.
    threading.Thread(target=lambda: (plant_identifier.load(), classifier.load()), daemon=True).start()
    yield


app = FastAPI(title="PhytoSense AR API", version="0.2.0", lifespan=lifespan,
              description="AR-based AI plant identification and plant health / disease diagnosis.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _read_image(data: bytes) -> Image.Image:
    if not data:
        raise HTTPException(400, "Empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Image larger than 12 MB")
    try:
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise HTTPException(400, "Not a valid image file")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    return img


def _models_ready() -> bool:
    return classifier.ready and (plant_identifier.ready or not plant_identifier.available)


@app.get("/api/status")
def status():
    return {"app": "PhytoSense AR", "version": app.version, "model": config.MODEL_ID,
            "model_ready": _models_ready(), "classes": len(classifier.labels) or None,
            "plant_model": plant_identifier.ready, "species": len(plant_identifier.species) - 1 if plant_identifier.ready else None,
            "assistant": "gemini" if assistant.gemini_enabled() else "offline",
            "languages": assistant.LANGUAGES}


@app.post("/api/diagnose")
def diagnose_image(file: UploadFile = File(...), save: bool = Form(True)):
    """Full diagnosis of one photo; saved to history by default."""
    img = _read_image(file.file.read())
    result = diagnose(np.asarray(img), with_details=True)
    if save:
        name = f"{uuid.uuid4().hex}.jpg"
        img.save(config.UPLOAD_DIR / name, "JPEG", quality=88)
        result["scan_id"] = db.add_scan(name, result)
        result["image_url"] = f"/uploads/{name}"
        for old in db.prune(config.MAX_SCANS):
            (config.UPLOAD_DIR / old).unlink(missing_ok=True)
    return result


@app.post("/api/frame")
def analyze_frame(file: UploadFile = File(...)):
    """Fast path for the live AR camera: small frame in, overlay + label out, nothing saved."""
    if not _models_ready():
        raise HTTPException(503, "Model is still loading")
    img = _read_image(file.file.read())
    img.thumbnail((448, 448))
    return diagnose(np.asarray(img), with_details=False)


@app.get("/api/scans")
def scans(limit: int = 100):
    return {"scans": db.list_scans(limit), "stats": db.stats()}


@app.get("/api/scans/{scan_id}")
def scan(scan_id: int):
    s = db.get_scan(scan_id)
    if not s:
        raise HTTPException(404, "Scan not found")
    return s


@app.delete("/api/scans/{scan_id}")
def remove_scan(scan_id: int):
    image = db.delete_scan(scan_id)
    if image is None:
        raise HTTPException(404, "Scan not found")
    (config.UPLOAD_DIR / image).unlink(missing_ok=True)
    return {"ok": True}


@app.get("/api/plants")
def plants():
    return {"plants": list(knowledge.PLANTS.values()), "conditions": list(knowledge.CONDITIONS.values()),
            "identifier_ready": plant_identifier.ready}


@app.get("/api/diseases")
def diseases():
    return {"crops": knowledge.CROPS, "entries": knowledge.ENTRIES, "note": knowledge.NOTE}


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[dict] = []
    context: dict | None = None
    lang: str = "en"


@app.post("/api/chat")
def chat(body: ChatIn):
    return assistant.answer(body.message, body.history, body.context, body.lang)


app.mount("/uploads", StaticFiles(directory=config.UPLOAD_DIR), name="uploads")
app.mount("/", StaticFiles(directory=config.FRONTEND_DIR, html=True), name="frontend")

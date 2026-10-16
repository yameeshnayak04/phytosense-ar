"""Smoke tests for the PhytoSense AR backend.  Run:  cd backend && python -m pytest -q"""
import io
import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app import knowledge
from app.main import app
from app.vision import segment_leaf

SAMPLES = Path(__file__).resolve().parents[2] / "samples"


def synthetic_leaf(spots: bool) -> np.ndarray:
    img = Image.new("RGB", (400, 300), (150, 150, 155))
    d = ImageDraw.Draw(img)
    d.ellipse([60, 40, 340, 260], fill=(50, 140, 50))
    if spots:
        for x, y in [(150, 120), (220, 170), (260, 110)]:
            d.ellipse([x - 18, y - 18, x + 18, y + 18], fill=(120, 75, 30))
    return np.asarray(img)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_segmentation_finds_leaf_and_spots():
    healthy = segment_leaf(synthetic_leaf(False))
    sick = segment_leaf(synthetic_leaf(True))
    assert healthy["found"] and sick["found"]
    assert healthy["severity"] < 1
    assert 3 < sick["severity"] < 20
    assert len(sick["lesions"]) == 3


def test_no_leaf_on_blank_image():
    assert not segment_leaf(np.full((200, 200, 3), 128, np.uint8))["found"]


def test_every_model_label_has_knowledge():
    assert len(knowledge.ENTRIES) == 38
    assert all(knowledge.lookup(e["id"]) is e for e in knowledge.ENTRIES)


def test_status(client):
    r = client.get("/api/status").json()
    assert r["app"] == "PhytoSense AR"


def test_diagnose_sample_and_history(client):
    labels = json.loads((SAMPLES / "labels.json").read_text())
    name, truth = next(iter(labels.items()))
    with open(SAMPLES / name, "rb") as f:
        res = client.post("/api/diagnose", files={"file": (name, f, "image/jpeg")})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["label"] == truth
    assert body["info"]["symptoms"]
    scan_id = body["scan_id"]
    assert client.get(f"/api/scans/{scan_id}").json()["id"] == scan_id
    assert client.delete(f"/api/scans/{scan_id}").json()["ok"]


def test_history_is_capped(client, monkeypatch):
    monkeypatch.setattr("app.config.MAX_SCANS", 2)
    img = io.BytesIO()
    Image.fromarray(synthetic_leaf(True)).save(img, "JPEG")
    ids = []
    for _ in range(3):
        img.seek(0)
        ids.append(client.post("/api/diagnose", files={"file": ("leaf.jpg", img, "image/jpeg")}).json()["scan_id"])
    kept = [s["id"] for s in client.get("/api/scans").json()["scans"]]
    assert ids[0] not in kept and ids[1] in kept and ids[2] in kept
    for i in ids[1:]:
        client.delete(f"/api/scans/{i}")


def test_rejects_non_image(client):
    r = client.post("/api/diagnose", files={"file": ("x.txt", io.BytesIO(b"hello"), "text/plain")})
    assert r.status_code == 400


def test_offline_chat_answers_from_knowledge_base(client, monkeypatch):
    monkeypatch.setattr("app.config.GEMINI_API_KEY", "")
    r = client.post("/api/chat", json={"message": "How do I treat tomato early blight?"}).json()
    assert r["source"] == "offline"
    assert "Early blight" in r["reply"]

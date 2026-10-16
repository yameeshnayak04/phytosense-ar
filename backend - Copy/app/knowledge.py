"""Disease knowledge base + crop info (Wikipedia), keyed by PlantVillage labels."""
from __future__ import annotations

import json
import re
from urllib.parse import quote

import requests

from . import config

_KB = json.loads((config.DATA_DIR / "knowledge_base.json").read_text(encoding="utf-8"))
CROPS: dict = _KB["crops"]
NOTE: str = _KB["note"]

# The 12 healthy PlantVillage classes share one template.
_HEALTHY_IDS = {
    "Apple": "Apple___healthy", "Blueberry": "Blueberry___healthy",
    "Cherry": "Cherry_(including_sour)___healthy", "Corn": "Corn_(maize)___healthy",
    "Grape": "Grape___healthy", "Peach": "Peach___healthy",
    "Bell pepper": "Pepper,_bell___healthy", "Potato": "Potato___healthy",
    "Raspberry": "Raspberry___healthy", "Soybean": "Soybean___healthy",
    "Strawberry": "Strawberry___healthy", "Tomato": "Tomato___healthy",
}

_CROP_KEYWORDS = {
    "apple": "Apple", "blueberry": "Blueberry", "cherry": "Cherry", "corn": "Corn", "maize": "Corn",
    "grape": "Grape", "orange": "Orange", "citrus": "Orange", "peach": "Peach", "pepper": "Bell pepper",
    "potato": "Potato", "raspberry": "Raspberry", "soybean": "Soybean", "squash": "Squash",
    "strawberry": "Strawberry", "tomato": "Tomato",
}


def _healthy_entry(crop: str) -> dict:
    return {
        "id": _HEALTHY_IDS[crop], "crop": crop, "disease": "Healthy", "type": "None", "pathogen": "",
        "urgency": "none", "healthy": True,
        "symptoms": "No disease symptoms detected. Leaf colour and texture look normal.",
        "chemical": [],
        "organic": ["No treatment needed"],
        "prevention": ["Keep scouting the crop weekly", "Water at the base of the plant, early in the day",
                       "Balanced fertiliser and good spacing for air flow", "Remove weeds and plant debris"],
    }


ENTRIES: list[dict] = [dict(e, healthy=False) for e in _KB["classes"]] + [_healthy_entry(c) for c in _HEALTHY_IDS]


def _norm(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


_BY_NORM = {_norm(e["id"]): e for e in ENTRIES}


def lookup(label: str) -> dict | None:
    """Find the knowledge entry for a model label (PlantVillage id or friendly name)."""
    hit = _BY_NORM.get(_norm(label))
    if hit:
        return hit
    low = label.lower()
    crop = next((c for k, c in _CROP_KEYWORDS.items() if k in low), None)
    if not crop:
        return None
    if "healthy" in low:
        return next((e for e in ENTRIES if e["crop"] == crop and e["healthy"]), None)
    for e in ENTRIES:
        if e["crop"] == crop and not e["healthy"]:
            words = [w for w in re.findall(r"[a-z]+", e["disease"].lower()) if len(w) > 3]
            if words and all(w in low for w in words[:2]):
                return e
    return None


def pretty_label(label: str) -> tuple[str, str]:
    entry = lookup(label)
    if entry:
        return entry["crop"], entry["disease"]
    parts = label.replace("_", " ").split("   ")
    return (parts[0].strip(), parts[-1].strip()) if len(parts) > 1 else ("Unknown", label)


_wiki_cache: dict[str, dict] = {}


def wiki_summary(crop: str) -> dict:
    """Short Wikipedia summary for the crop (cached). Empty dict when offline."""
    if crop in _wiki_cache:
        return _wiki_cache[crop]
    info = CROPS.get(crop, {})
    title = info.get("wiki", crop)
    try:
        r = requests.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title)}",
            headers={"User-Agent": "PhytoSense-AR/0.1 (college project)"}, timeout=4,
        )
        if r.ok:
            d = r.json()
            _wiki_cache[crop] = {"title": d.get("title"), "extract": d.get("extract"),
                                 "url": d.get("content_urls", {}).get("desktop", {}).get("page"),
                                 "thumbnail": (d.get("thumbnail") or {}).get("source")}
            return _wiki_cache[crop]
    except requests.RequestException:
        pass
    return {}

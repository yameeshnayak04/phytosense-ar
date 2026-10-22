"""Knowledge bases: crop diseases (PlantVillage labels), plants of the region, general leaf conditions."""
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


def crop_label_indices(crop: str, labels: list[str]) -> list[int]:
    """Indices of the disease-model labels that belong to one crop (e.g. all Tomato classes)."""
    return [i for i, label in enumerate(labels) if (lookup(label) or {}).get("crop") == crop]


# ---------- plants of the region + general leaf conditions (plant-identification model) ----------
_PLANTS = json.loads((config.DATA_DIR / "plants.json").read_text(encoding="utf-8"))
PLANTS: dict[str, dict] = {p["id"]: p for p in _PLANTS["plants"]}
_CONDITIONS = json.loads((config.DATA_DIR / "conditions.json").read_text(encoding="utf-8"))
CONDITIONS: dict[str, dict] = {c["id"]: c for c in _CONDITIONS["conditions"]}
CONDITION_NOTE: str = _CONDITIONS["note"]

UNKNOWN_PLANT = {"id": "unknown", "name": "Unknown plant", "hindi": "", "scientific": "", "category": "",
                 "care": {}, "uses": "", "problems": []}


def plant(plant_id: str) -> dict:
    return PLANTS.get(plant_id, UNKNOWN_PLANT)


def condition_entry(condition_id: str, plant_entry: dict) -> dict:
    """A general condition presented like a disease entry, for the given plant."""
    c = CONDITIONS[condition_id]
    return dict(c, id=f"{plant_entry['id']}:{condition_id}", crop=plant_entry["name"])


def entry_for_label(label: str) -> dict | None:
    """Knowledge entry for a scan label: PlantVillage id, or "<plant id>:<condition id>"."""
    if ":" in label:
        plant_id, condition_id = label.split(":", 1)
        return condition_entry(condition_id, plant(plant_id)) if condition_id in CONDITIONS else None
    return lookup(label)


def _plant_names(p: dict) -> list[str]:
    names = [p["id"].replace("_", " "), *re.split(r"[()/]", p["name"]), *p.get("hindi", "").split("/")]
    return [n.strip().lower() for n in names if len(n.strip()) > 2]


def find_plant(text: str) -> dict | None:
    """Plant mentioned in free text (English, local or Hindi name); longest match wins."""
    low = text.lower()
    hits = [(len(n), p) for p in PLANTS.values() for n in _plant_names(p) if re.search(rf"(?<!\w){re.escape(n)}(?!\w)", low)]
    return max(hits, key=lambda h: h[0])[1] if hits else None


_wiki_cache: dict[str, dict] = {}


def wiki_summary(crop: str, title: str | None = None) -> dict:
    """Short Wikipedia summary for a crop or plant (cached). Empty dict when offline."""
    title = title or CROPS.get(crop, {}).get("wiki", crop)
    if title in _wiki_cache:
        return _wiki_cache[title]
    try:
        r = requests.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title)}",
            headers={"User-Agent": "PhytoSense-AR/0.1 (college project)"}, timeout=4,
        )
        if r.ok:
            d = r.json()
            _wiki_cache[title] = {"title": d.get("title"), "extract": d.get("extract"),
                                 "url": d.get("content_urls", {}).get("desktop", {}).get("page"),
                                 "thumbnail": (d.get("thumbnail") or {}).get("source")}
            return _wiki_cache[title]
    except requests.RequestException:
        pass
    return {}

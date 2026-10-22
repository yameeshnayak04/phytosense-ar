"""Full pipeline: segment leaf -> identify plant -> diagnose (crop disease model or leaf condition) -> score.

With the plant-identification model present:
  1. the species is identified from the whole frame and the leaf crop;
  2. for crops of the disease model (tomato, potato, …) the 38-class disease classifier is run and its
     probabilities are weighted by the plant model's crop probabilities (look-alike crops can still win);
  3. for every other plant the general leaf-condition head is used (healthy, leaf spot, mildew, rust, …).
Without it, the original crop-disease-only pipeline runs.
"""
from __future__ import annotations

import time

import numpy as np

from . import config, knowledge
from .classifier import classifier
from .plant_id import plant_identifier
from .vision import crop_to_bbox, segment_leaf

_URGENCY_PENALTY = {"high": 25, "medium": 12, "low": 5}


def severity_level(severity: float, healthy: bool) -> str:
    if healthy:
        return "none"
    if severity < 5:
        return "early"
    if severity < 20:
        return "moderate"
    return "severe"


def health_score(severity: float, entry: dict | None, healthy: bool) -> int:
    if healthy:
        return 100 if severity < 10 else 90
    penalty = _URGENCY_PENALTY.get((entry or {}).get("urgency"), 10)
    return int(max(5, min(95, 100 - penalty - 1.5 * severity)))


def _status(leaf_found: bool, confidence: float, healthy: bool) -> str:
    if not leaf_found:
        return "no_leaf"
    if confidence < config.MIN_CONFIDENCE:
        return "uncertain"
    return "healthy" if healthy else "diseased"


def _species_view(pred: dict) -> dict:
    p = knowledge.plant(pred["id"])
    return {"id": pred["id"], "name": p["name"], "hindi": p.get("hindi", ""), "scientific": p.get("scientific", ""),
            "confidence": pred["confidence"]}


def _disease_top3(preds: list[dict]) -> list[dict]:
    return [dict(p, crop=knowledge.pretty_label(p["label"])[0], disease=knowledge.pretty_label(p["label"])[1]) for p in preds]


def diagnose(img_rgb: np.ndarray, with_details: bool = True) -> dict:
    t0 = time.perf_counter()
    seg = segment_leaf(img_rgb)
    leaf = crop_to_bbox(img_rgb, seg["bbox"]) if seg["found"] else img_rgb
    if not plant_identifier.ready:
        result = _crop_only(seg, leaf, with_details)
    else:
        result = _with_plant_id(img_rgb, seg, leaf, with_details)
    result["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
    return result


def _crop_only(seg: dict, leaf: np.ndarray, with_details: bool) -> dict:
    """Original pipeline: 38-class crop-disease classifier on the leaf crop."""
    preds = classifier.predict(leaf)
    top = preds[0]
    entry = knowledge.lookup(top["label"])
    crop, disease = knowledge.pretty_label(top["label"])
    healthy = bool(entry and entry["healthy"])
    result = {
        "status": _status(seg["found"], top["confidence"], healthy),
        "label": top["label"], "crop": crop, "disease": disease, "healthy": healthy,
        "confidence": top["confidence"], "top3": _disease_top3(preds),
        "severity": seg["severity"], "severity_reliable": True,
        "severity_level": severity_level(seg["severity"], healthy),
        "health_score": health_score(seg["severity"], entry, healthy),
        "overlay": {k: seg[k] for k in ("leaf_polygon", "lesions", "bbox")},
        "leaf_found": seg["found"], "urgency": (entry or {}).get("urgency", "unknown"),
        "source": "crop_disease_model", "species": None, "species_top": [], "condition_top": [],
    }
    if with_details:
        result["info"] = entry
        result["crop_info"] = dict(knowledge.CROPS.get(crop, {}), wikipedia=knowledge.wiki_summary(crop))
        result["note"] = knowledge.NOTE
    return result


def _with_plant_id(img_rgb: np.ndarray, seg: dict, leaf: np.ndarray, with_details: bool) -> dict:
    pid = plant_identifier.predict(img_rgb, leaf if seg["found"] else None)
    best = pid["species"][0]
    species_top = [_species_view(p) for p in pid["species"] if p["id"] != "not_plant"][:3]
    overlay = {k: seg[k] for k in ("leaf_polygon", "lesions", "bbox")}

    if best["id"] == "not_plant" and best["confidence"] >= 0.5:
        return {
            "status": "no_plant", "label": "not_plant", "crop": "No plant", "disease": "–", "healthy": False,
            "confidence": best["confidence"], "top3": [], "severity": 0.0, "severity_reliable": False,
            "severity_level": "none", "health_score": 0, "overlay": {"leaf_polygon": [], "lesions": [], "bbox": None},
            "leaf_found": False, "urgency": "unknown", "source": "plant_id_model", "species": None,
            "species_top": species_top, "condition_top": [], "info": None, "note": "",
        }

    known = best["id"] != "not_plant" and best["confidence"] >= config.MIN_SPECIES_CONFIDENCE
    plant = knowledge.plant(best["id"]) if known else knowledge.UNKNOWN_PLANT

    if plant.get("pv_crop") and classifier.ready:
        # Crop with a dedicated disease model. Similar crops (tomato / potato) can swap places in the plant
        # model, so every crop it gives >= 5 % competes: score = P(disease | leaf) x P(crop | plant model).
        crop_p: dict[str, float] = {}
        for s in pid["species"]:
            c = knowledge.plant(s["id"]).get("pv_crop")
            if c and s["confidence"] >= 0.05:
                crop_p[c] = crop_p.get(c, 0.0) + s["confidence"]
        probs = classifier.probabilities(leaf)
        fused = np.zeros_like(probs)
        for c, p in crop_p.items():
            idx = knowledge.crop_label_indices(c, classifier.labels)
            fused[idx] = probs[idx] * p
        preds = classifier.top(fused / fused.sum())
        top = preds[0]
        entry = knowledge.lookup(top["label"])
        if entry["crop"] != plant["pv_crop"]:          # the disease model settled on the other crop
            sid = next(s["id"] for s in pid["species"] if knowledge.plant(s["id"]).get("pv_crop") == entry["crop"])
            best, plant = next(s for s in pid["species"] if s["id"] == sid), knowledge.plant(sid)
        label, disease, confidence = top["label"], entry["disease"], top["confidence"]
        top3, source = _disease_top3(preds), "crop_disease_model"
    else:
        cond = pid["condition"]
        entry = knowledge.condition_entry(cond[0]["id"], plant)
        label, disease, confidence = f"{plant['id']}:{cond[0]['id']}", entry["disease"], cond[0]["confidence"]
        top3 = [{"label": c["id"], "crop": plant["name"], "disease": knowledge.CONDITIONS[c["id"]]["disease"],
                 "confidence": c["confidence"]} for c in cond[:3]]
        source = "condition_model"

    healthy = bool(entry["healthy"])
    # Colour-based lesion mapping cannot tell natural leaf colours (croton, variegated money plant …) from disease.
    reliable = seg["found"] and not plant.get("variegated", False)
    severity = seg["severity"] if reliable else 0.0
    if not reliable:
        overlay["lesions"] = []

    result = {
        "status": _status(seg["found"], confidence, healthy),
        "label": label, "crop": plant["name"], "disease": disease, "healthy": healthy,
        "confidence": confidence, "top3": top3,
        "severity": severity, "severity_reliable": reliable,
        "severity_level": severity_level(severity, healthy),
        "health_score": health_score(severity, entry, healthy),
        "overlay": overlay, "leaf_found": seg["found"], "urgency": entry.get("urgency", "unknown"),
        "source": source,
        "species": _species_view(best) if known else None,
        "species_top": species_top,
        "condition_top": pid["condition"][:3],
    }
    if with_details:
        result["info"] = entry
        wiki_title = plant.get("wiki")
        result["crop_info"] = {"scientific": plant.get("scientific", ""), "hi": plant.get("hindi", ""),
                               "wikipedia": knowledge.wiki_summary(plant["name"], wiki_title) if known else {}}
        result["plant_info"] = plant if known else None
        result["note"] = knowledge.NOTE if source == "crop_disease_model" else knowledge.CONDITION_NOTE
    return result

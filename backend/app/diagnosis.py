"""Full pipeline: segment leaf -> classify cropped leaf -> score -> attach knowledge."""
from __future__ import annotations

import time

import numpy as np

from . import config, knowledge
from .classifier import classifier
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


def diagnose(img_rgb: np.ndarray, with_details: bool = True) -> dict:
    t0 = time.perf_counter()
    seg = segment_leaf(img_rgb)
    preds = classifier.predict(crop_to_bbox(img_rgb, seg["bbox"]))
    top = preds[0]
    entry = knowledge.lookup(top["label"])
    crop, disease = knowledge.pretty_label(top["label"])
    healthy = bool(entry and entry["healthy"])

    if not seg["found"]:
        status = "no_leaf"
    elif top["confidence"] < config.MIN_CONFIDENCE:
        status = "uncertain"
    else:
        status = "healthy" if healthy else "diseased"

    result = {
        "status": status,
        "label": top["label"],
        "crop": crop,
        "disease": disease,
        "healthy": healthy,
        "confidence": top["confidence"],
        "top3": [dict(p, crop=knowledge.pretty_label(p["label"])[0],
                      disease=knowledge.pretty_label(p["label"])[1]) for p in preds],
        "severity": seg["severity"],
        "severity_level": severity_level(seg["severity"], healthy),
        "health_score": health_score(seg["severity"], entry, healthy),
        "overlay": {k: seg[k] for k in ("leaf_polygon", "lesions", "bbox")},
        "leaf_found": seg["found"],
        "urgency": (entry or {}).get("urgency", "unknown"),
    }
    if with_details:
        result["info"] = entry
        result["crop_info"] = dict(knowledge.CROPS.get(crop, {}), wikipedia=knowledge.wiki_summary(crop))
        result["note"] = knowledge.NOTE
    result["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
    return result

"""Classical computer-vision step: find the leaf and the diseased spots on it.

The classifier says *what* the disease is; this module says *where* it is, so
the frontend can draw the AR overlay (leaf outline + lesion patches) and
compute an infected-area severity score. It uses colour segmentation in HSV
and the Excess-Green index, so it needs no extra trained model.
"""
from __future__ import annotations

import cv2
import numpy as np

MAX_SIDE = 512


def _resize(img: np.ndarray) -> tuple[np.ndarray, float]:
    h, w = img.shape[:2]
    scale = MAX_SIDE / max(h, w)
    if scale >= 1:
        return img, 1.0
    return cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA), scale


def _largest_component(mask: np.ndarray) -> np.ndarray:
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n <= 1:
        return np.zeros_like(mask)
    idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return np.where(labels == idx, 255, 0).astype(np.uint8)


def _fill_holes(mask: np.ndarray) -> np.ndarray:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(mask)
    cv2.drawContours(filled, contours, -1, 255, thickness=cv2.FILLED)
    return filled


def _polygon(contour: np.ndarray, w: int, h: int, eps: float) -> list[list[float]]:
    approx = cv2.approxPolyDP(contour, eps * cv2.arcLength(contour, True), True)
    return [[round(float(x) / w, 4), round(float(y) / h, 4)] for x, y in approx.reshape(-1, 2)]


def segment_leaf(img_rgb: np.ndarray) -> dict:
    """Return leaf/lesion masks and overlay geometry for an RGB uint8 image."""
    small, _ = _resize(img_rgb)
    h, w = small.shape[:2]
    blurred = cv2.GaussianBlur(small, (5, 5), 0)
    hsv = cv2.cvtColor(blurred, cv2.COLOR_RGB2HSV)
    hue, sat, val = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    r, g, b = (blurred[..., i].astype(np.int16) for i in range(3))

    # OpenCV hue runs 0-179: red ~0, yellow ~30, green ~60.
    # Healthy tissue: green hue, or Excess-Green index 2G-R-B clearly positive (not yellow).
    exg = 2 * g - r - b
    green = (hue >= 33) & (hue <= 95) & (((sat >= 40) & (val >= 40)) | (exg > 25))
    # Symptom tones: yellowing, tan/brown necrosis, rust, purple-red spots.
    tone = ((hue < 33) | (hue >= 165)) & (sat >= 35) & (val >= 50)
    # Background model from the image border: pixels with the border's chroma
    # (including its shadows) are never grown into the leaf.
    lab = cv2.cvtColor(blurred, cv2.COLOR_RGB2LAB).astype(np.int16)
    border = np.concatenate([lab[:6].reshape(-1, 3), lab[-6:].reshape(-1, 3),
                             lab[:, :6].reshape(-1, 3), lab[:, -6:].reshape(-1, 3)])
    a_bg, b_bg = np.median(border[:, 1]), np.median(border[:, 2])
    bg_like = np.hypot(lab[..., 1] - a_bg, lab[..., 2] - b_bg) < 9
    # Dark necrotic spots and white powdery coating.
    dark = val < 60
    white = (sat < 40) & (val > 175)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    green_u8 = cv2.morphologyEx(green.astype(np.uint8) * 255, cv2.MORPH_OPEN, kernel)
    core = _largest_component(green_u8)
    empty = {"found": False, "leaf_polygon": [], "lesions": [], "bbox": None,
             "severity": 0.0, "leaf_coverage": 0.0}
    if core.sum() == 0 or (core > 0).mean() < 0.02:
        return empty

    # Grow the leaf to include symptom-coloured tissue touching the green core
    # (e.g. blighted margins), but not a brown table behind it.
    plant = cv2.morphologyEx(((green | (tone & ~bg_like)) * 255).astype(np.uint8), cv2.MORPH_CLOSE, kernel)
    n, labels = cv2.connectedComponents(plant)
    core_labels = np.unique(labels[core > 0])
    core_labels = core_labels[core_labels > 0]
    grown = np.isin(labels, core_labels).astype(np.uint8) * 255
    core_filled = _fill_holes(cv2.morphologyEx(core, cv2.MORPH_CLOSE, kernel))
    touches_border = grown[0].mean() + grown[-1].mean() + grown[:, 0].mean() + grown[:, -1].mean()
    if (grown > 0).sum() > 3.0 * (core_filled > 0).sum() or touches_border > 2 * 255:
        leaf = core_filled
    else:
        leaf = _fill_holes(grown)

    leaf_area = int((leaf > 0).sum())
    if leaf_area / (h * w) < 0.02:
        return empty

    inner = cv2.erode(leaf, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    lesion = ((tone | dark | white) & ~green & (inner > 0)).astype(np.uint8) * 255
    lesion = cv2.morphologyEx(lesion, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    lesion = cv2.morphologyEx(lesion, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))

    min_spot = max(6, int(leaf_area * 0.0005))
    contours, _ = cv2.findContours(lesion, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = [c for c in contours if cv2.contourArea(c) >= min_spot]
    contours.sort(key=cv2.contourArea, reverse=True)
    lesion_area = sum(cv2.contourArea(c) for c in contours)

    leaf_contours, _ = cv2.findContours(leaf, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    leaf_contour = max(leaf_contours, key=cv2.contourArea)
    x, y, bw, bh = cv2.boundingRect(leaf_contour)

    return {
        "found": True,
        "leaf_polygon": _polygon(leaf_contour, w, h, 0.004),
        "lesions": [_polygon(c, w, h, 0.006) for c in contours[:40]],
        "bbox": [round(x / w, 4), round(y / h, 4), round(bw / w, 4), round(bh / h, 4)],
        "severity": round(min(100.0, 100.0 * lesion_area / leaf_area), 1),
        "leaf_coverage": round(leaf_area / (h * w), 3),
    }


def crop_to_bbox(img_rgb: np.ndarray, bbox: list[float] | None, margin: float = 0.08) -> np.ndarray:
    """Crop the original image around the leaf so the classifier sees mostly leaf."""
    if not bbox:
        return img_rgb
    H, W = img_rgb.shape[:2]
    x, y, bw, bh = bbox
    x0 = max(0, int((x - margin) * W))
    y0 = max(0, int((y - margin) * H))
    x1 = min(W, int((x + bw + margin) * W))
    y1 = min(H, int((y + bh + margin) * H))
    if x1 - x0 < 32 or y1 - y0 < 32:
        return img_rgb
    return img_rgb[y0:y1, x0:x1]

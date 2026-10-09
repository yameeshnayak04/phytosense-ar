"""Evaluate the disease classifier on random PlantVillage test images (for the project report).

    cd backend
    python ../scripts/evaluate.py --n 100

Downloads N random images from the PlantVillage test split on Hugging Face,
runs the same pipeline as the app (leaf crop + classifier) and prints
accuracy, mean confidence, speed and the misclassified images.
"""
import argparse
import io
import json
import random
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.diagnosis import diagnose  # noqa: E402

DATASET = "BrandonFors/Plant-Diseases-PlantVillage-Dataset"
API = "https://datasets-server.huggingface.co"


def fetch(url: str) -> bytes:
    """GET with retry, because the free datasets API rate-limits (HTTP 429)."""
    for attempt in range(6):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 5:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def get_json(url: str) -> dict:
    return json.loads(fetch(url))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    info = get_json(f"{API}/info?dataset={DATASET}")["dataset_info"]["default"]
    names = info["features"]["label"]["names"]
    total = info["splits"]["test"]["num_examples"]
    random.seed(args.seed)
    # Random starting points, 5 consecutive rows each (fewer API calls).
    rows = []
    for start in random.sample(range(total - 5), (args.n + 4) // 5):
        batch = get_json(f"{API}/rows?dataset={DATASET}&config=default&split=test&offset={start}&length=5")["rows"]
        rows += [(r["row_idx"], r["row"]) for r in batch]
    rows = rows[:args.n]

    correct, confs, times, wrong = 0, [], [], []
    for i, (off, row) in enumerate(rows, 1):
        truth = names[row["label"]]
        img = np.asarray(Image.open(io.BytesIO(fetch(row["image"]["src"]))).convert("RGB"))
        t0 = time.perf_counter()
        res = diagnose(img, with_details=False)
        times.append(time.perf_counter() - t0)
        confs.append(res["confidence"])
        if res["label"] == truth:
            correct += 1
        else:
            wrong.append((off, truth, res["label"], res["confidence"]))
        print(f"\r{i}/{args.n}  accuracy so far {correct / i:.1%}", end="", flush=True)

    print(f"\n\nImages evaluated : {args.n} (PlantVillage test split, seed {args.seed})")
    print(f"Top-1 accuracy   : {correct / args.n:.1%}")
    print(f"Mean confidence  : {np.mean(confs):.1%}")
    print(f"Mean time / image: {1000 * np.mean(times):.0f} ms (segmentation + classification, CPU)")
    if wrong:
        print("\nMisclassified:")
        for off, t, p, c in wrong:
            print(f"  #{off}: true={t}  predicted={p} ({c:.0%})")


if __name__ == "__main__":
    main()

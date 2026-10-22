"""Disease classifier: PlantVillage ViT exported to int8 ONNX (scripts/export_onnx.py).

ONNX Runtime needs ~5x less memory than PyTorch, so the app fits on free
512 MB hosting plans.
"""
from __future__ import annotations

import json
import threading
import time

import numpy as np
from PIL import Image

from . import config


class DiseaseClassifier:
    def __init__(self):
        self._lock = threading.Lock()
        self.session = None
        self.labels: list[str] = []

    def load(self) -> None:
        with self._lock:
            if self.session is not None:
                return
            import onnxruntime as ort

            t0 = time.time()
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = config.ONNX_THREADS
            self.labels = json.loads((config.MODEL_DIR / "labels.json").read_text(encoding="utf-8"))
            self.session = ort.InferenceSession(str(config.MODEL_DIR / "model.onnx"), opts,
                                                providers=["CPUExecutionProvider"])
            print(f"[classifier] loaded ONNX model ({len(self.labels)} classes) in {time.time() - t0:.1f}s")

    @property
    def ready(self) -> bool:
        return self.session is not None

    @staticmethod
    def preprocess(img_rgb: np.ndarray) -> np.ndarray:
        # ViT preprocessing: resize 224x224 bilinear, rescale 1/255, normalise mean=std=0.5, NCHW.
        x = np.asarray(Image.fromarray(img_rgb).resize((224, 224), Image.BILINEAR), dtype=np.float32)
        x = x / 127.5 - 1.0
        return x.transpose(2, 0, 1)[None]

    def probabilities(self, img_rgb: np.ndarray) -> np.ndarray:
        self.load()
        logits = self.session.run(None, {"pixel_values": self.preprocess(img_rgb)})[0][0]
        probs = np.exp(logits - logits.max())
        return probs / probs.sum()

    def top(self, probs: np.ndarray, top_k: int = 3) -> list[dict]:
        idx = np.argsort(probs)[::-1][:top_k]
        return [{"index": int(i), "label": self.labels[int(i)], "confidence": round(float(probs[i]), 4)}
                for i in idx if probs[i] > 0]

    def predict(self, img_rgb: np.ndarray, top_k: int = 3) -> list[dict]:
        return self.top(self.probabilities(img_rgb), top_k)


classifier = DiseaseClassifier()

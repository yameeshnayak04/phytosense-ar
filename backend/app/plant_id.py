"""Plant identification + leaf condition: ConvNeXt-Tiny with two heads, int8 ONNX.

Trained by training/train_plant_id_model.ipynb. One forward pass returns
  * species logits   – common plants of Indore / central India, the disease-model crops and "not_plant"
  * condition logits – healthy / leaf spot / powdery mildew / rust / sooty mould / mosaic / pests
The app works without this model (crop-disease classifier only) until the files are present.
"""
from __future__ import annotations

import json
import threading
import time

import numpy as np
from PIL import Image

from . import config


def _softmax(z: np.ndarray) -> np.ndarray:
    e = np.exp(z - z.max(axis=-1, keepdims=True))
    return e / e.sum(axis=-1, keepdims=True)


class PlantIdentifier:
    def __init__(self):
        self._lock = threading.Lock()
        self.session = None
        self.species: list[str] = []
        self.conditions: list[str] = []
        self.size = 224
        self.mean = np.array([0.485, 0.456, 0.406], np.float32)
        self.std = np.array([0.229, 0.224, 0.225], np.float32)

    @property
    def available(self) -> bool:
        return (config.MODEL_DIR / config.PLANT_MODEL_FILE).exists()

    @property
    def ready(self) -> bool:
        return self.session is not None

    def load(self) -> None:
        with self._lock:
            if self.session is not None or not self.available:
                return
            import onnxruntime as ort

            t0 = time.time()
            meta = json.loads((config.MODEL_DIR / "plant_labels.json").read_text(encoding="utf-8"))
            self.species, self.conditions = meta["species"], meta["conditions"]
            self.size = int(meta.get("input_size", 224))
            self.mean = np.array(meta.get("mean", self.mean), np.float32)
            self.std = np.array(meta.get("std", self.std), np.float32)
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = config.ONNX_THREADS
            self.session = ort.InferenceSession(str(config.MODEL_DIR / config.PLANT_MODEL_FILE), opts,
                                                providers=["CPUExecutionProvider"])
            print(f"[plant_id] loaded ({len(self.species)} species, {len(self.conditions)} conditions) "
                  f"in {time.time() - t0:.1f}s")

    def _prep(self, img_rgb: np.ndarray) -> np.ndarray:
        # Same as the training notebook: squash to size x size (bilinear), scale 0-1, ImageNet mean/std, CHW.
        x = np.asarray(Image.fromarray(img_rgb).resize((self.size, self.size), Image.BILINEAR), dtype=np.float32) / 255.0
        return ((x - self.mean) / self.std).transpose(2, 0, 1)

    def predict(self, full_rgb: np.ndarray, leaf_rgb: np.ndarray | None = None, top_k: int = 5) -> dict:
        """Species from the whole frame and the leaf crop (averaged); condition from the leaf crop when there is one."""
        self.load()
        views = [full_rgb] if leaf_rgb is None else [full_rgb, leaf_rgb]
        ls, lc = self.session.run(None, {"pixel_values": np.stack([self._prep(v) for v in views])})
        p_species = _softmax(ls).mean(axis=0)
        p_condition = _softmax(lc)[-1]

        def top(p: np.ndarray, names: list[str]) -> list[dict]:
            return [{"id": names[i], "confidence": round(float(p[i]), 4)} for i in np.argsort(p)[::-1][:top_k]]

        return {"species": top(p_species, self.species), "condition": top(p_condition, self.conditions)}


plant_identifier = PlantIdentifier()

"""Export the Hugging Face disease model to a small int8 ONNX file (runs in 512 MB RAM).

    python scripts/export_onnx.py

Writes backend/model/model.onnx (+ labels.json) and checks that the quantised model
agrees with the original PyTorch model on the sample images.
"""
import json
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from transformers import AutoModelForImageClassification

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from app import config  # noqa: E402

OUT = ROOT / "backend" / "model"


def preprocess(img: Image.Image) -> np.ndarray:
    """Same steps as app/classifier.py: resize 224x224 bilinear, scale to [-1, 1], NCHW."""
    x = np.asarray(img.convert("RGB").resize((224, 224), Image.BILINEAR), dtype=np.float32) / 255.0
    x = (x - 0.5) / 0.5
    return x.transpose(2, 0, 1)[None]


def main() -> None:
    import onnxruntime as ort
    from onnxruntime.quantization import QuantType, quantize_dynamic

    OUT.mkdir(parents=True, exist_ok=True)
    model = AutoModelForImageClassification.from_pretrained(config.MODEL_ID).eval()
    fp32 = OUT / "model_fp32.onnx"
    torch.onnx.export(model, (torch.zeros(1, 3, 224, 224),), str(fp32), input_names=["pixel_values"],
                      output_names=["logits"], opset_version=17, dynamo=False)
    quantize_dynamic(str(fp32), str(OUT / "model.onnx"), weight_type=QuantType.QUInt8)
    fp32.unlink()
    for extra in OUT.glob("model_fp32.onnx*"):
        extra.unlink()

    labels = [model.config.id2label[i] for i in range(len(model.config.id2label))]
    (OUT / "labels.json").write_text(json.dumps(labels, indent=0), encoding="utf-8")
    print(f"model.onnx: {(OUT / 'model.onnx').stat().st_size / 1e6:.1f} MB, {len(labels)} labels")

    # Agreement check on the sample images.
    sess = ort.InferenceSession(str(OUT / "model.onnx"))
    agree = 0
    samples = sorted((ROOT / "samples").glob("*.jpg"))
    for f in samples:
        x = preprocess(Image.open(f))
        with torch.inference_mode():
            ref = int(model(pixel_values=torch.from_numpy(x)).logits.argmax())
        got = int(sess.run(None, {"pixel_values": x})[0].argmax())
        agree += ref == got
    print(f"int8 vs original agreement: {agree}/{len(samples)} sample images")


if __name__ == "__main__":
    main()

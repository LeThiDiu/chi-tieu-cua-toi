"""Nạp model phân loại danh mục (đã export ở Bước 1) và dự đoán."""
import json
import os
import sys

import joblib

MODEL_DIR = os.path.abspath(
    os.environ.get("MODEL_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "model"))
)
# joblib cần import được textnorm.normalize_text khi nạp model
if MODEL_DIR not in sys.path:
    sys.path.insert(0, MODEL_DIR)

_pipe = None
META: dict = {}


class ModelNotReady(RuntimeError):
    pass


def load_model():
    """Nạp 1 lần (không nạp lại trong mỗi request)."""
    global _pipe, META
    model_path = os.path.join(MODEL_DIR, "category_model.joblib")
    meta_path = os.path.join(MODEL_DIR, "model_metadata.json")
    if not (os.path.exists(model_path) and os.path.exists(meta_path)):
        raise ModelNotReady(
            "Chưa có model. Hãy chạy:  cd model && python gen_dataset.py && python train_export.py"
        )
    _pipe = joblib.load(model_path)
    with open(meta_path, encoding="utf-8") as f:
        META = json.load(f)


def is_ready() -> bool:
    return _pipe is not None


def categories() -> list[str]:
    cats = list(META.get("categories", []))
    fb = META.get("fallback_category", "Khác")
    if fb not in cats:
        cats.append(fb)
    return cats


def categorize(names: list[str]) -> list[dict]:
    if _pipe is None:
        raise ModelNotReady("Model chưa được nạp.")
    if not names:
        return []
    proba = _pipe.predict_proba(names)
    classes = _pipe.classes_
    min_conf = float(META.get("min_confidence", 0.35))
    fallback = META.get("fallback_category", "Khác")
    out = []
    for row in proba:
        i = int(row.argmax())
        conf = float(row[i])
        top3 = sorted(zip(classes, row), key=lambda kv: kv[1], reverse=True)[:3]
        out.append({
            "category": str(classes[i]) if conf >= min_conf else fallback,
            "confidence": round(conf, 3),
            "top3": [{"category": str(c), "confidence": round(float(p), 3)} for c, p in top3],
        })
    return out

"""Bước 1: Huấn luyện + export model phân loại danh mục chi tiêu.

Pipeline = TF-IDF n-gram ký tự + Logistic Regression (so sánh thêm Naive Bayes).
Xuất:  category_model.joblib  và  model_metadata.json

Chạy (từ thư mục model/):   python train_export.py
"""
import json
import os
from datetime import datetime

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import FeatureUnion, Pipeline

from textnorm import normalize_text

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "product_names.csv")
VERSION = "1.0.0"


def make_pipeline(clf):
    # n-gram ký tự (chịu lỗi OCR) + n-gram từ (bắt tên thương hiệu / từ khóa)
    features = FeatureUnion([
        ("char", TfidfVectorizer(preprocessor=normalize_text, analyzer="char_wb",
                                 ngram_range=(2, 5), sublinear_tf=True)),
        ("word", TfidfVectorizer(preprocessor=normalize_text, analyzer="word",
                                 ngram_range=(1, 2), sublinear_tf=True)),
    ])
    return Pipeline([("features", features), ("clf", clf)])


def load_data():
    """Dữ liệu gốc + dữ liệu người dùng đã sửa/xác nhận trong app (data/feedback.csv)."""
    df = pd.read_csv(DATA)
    fb = os.path.join(HERE, "data", "feedback.csv")
    if os.path.exists(fb):
        extra = pd.read_csv(fb).dropna()
        extra["group"] = extra["name"]
        df = pd.concat([df, extra[["name", "category", "group"]]], ignore_index=True)
        print(f"Đã gộp {len(extra)} dòng phản hồi từ người dùng")
    return df


def main():
    df = load_data()
    X, y, groups = df["name"], df["category"], df["group"]

    # Chia theo `group` (tên gốc): biến thể của cùng một sản phẩm không lọt cả vào train lẫn test
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(splitter.split(X, y, groups))
    X_tr, X_te, y_tr, y_te = X.iloc[train_idx], X.iloc[test_idx], y.iloc[train_idx], y.iloc[test_idx]
    print(f"Train: {len(X_tr)} | Test: {len(X_te)} | Số danh mục: {y.nunique()}")

    candidates = {
        "LogisticRegression": LogisticRegression(max_iter=3000, C=30),
        "MultinomialNB": MultinomialNB(alpha=0.1),
    }
    results, best_name, best_pipe, best_f1 = {}, None, None, -1
    for name, clf in candidates.items():
        pipe = make_pipeline(clf).fit(X_tr, y_tr)
        pred = pipe.predict(X_te)
        acc, f1 = accuracy_score(y_te, pred), f1_score(y_te, pred, average="macro")
        results[name] = {"accuracy": round(acc, 4), "macro_f1": round(f1, 4)}
        print(f"  {name:20s} accuracy={acc:.4f}  macro-F1={f1:.4f}")
        if f1 > best_f1:
            best_name, best_pipe, best_f1 = name, pipe, f1

    pred = best_pipe.predict(X_te)

    print(f"\nModel được chọn: {best_name}\n")
    print(classification_report(y_te, pred, digits=3))
    labels = sorted(y.unique().tolist())
    cm = confusion_matrix(y_te, pred, labels=labels)
    report = classification_report(y_te, pred, output_dict=True)

    # Huấn luyện lại trên toàn bộ dữ liệu trước khi export
    final = make_pipeline(candidates[best_name].__class__(**candidates[best_name].get_params())).fit(X, y)
    joblib.dump(final, os.path.join(HERE, "category_model.joblib"))

    metadata = {
        "model_name": "expense_category_classifier",
        "version": VERSION,
        "algorithm": best_name,
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "n_samples": int(len(df)),
        "categories": labels,
        "fallback_category": "Khác",
        "min_confidence": 0.35,
        "metrics_test": {
            "split": "GroupShuffleSplit theo tên sản phẩm gốc (sản phẩm CHƯA từng gặp)",
            "accuracy": round(accuracy_score(y_te, pred), 4),
            "macro_f1": round(f1_score(y_te, pred, average="macro"), 4),
            "per_class_f1": {c: round(report[c]["f1-score"], 3) for c in labels},
        },
        "model_comparison": results,
        "confusion_matrix": {"labels": labels, "matrix": cm.tolist()},
    }
    with open(os.path.join(HERE, "model_metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print("Đã export: category_model.joblib, model_metadata.json")

    # Nạp lại để kiểm tra (mô phỏng việc server sẽ làm)
    loaded = joblib.load(os.path.join(HERE, "category_model.joblib"))
    for t in ["Ca phe sua da", "Cuoc GrabBike", "Paracetamol 500mg", "Vở ô ly 120 trang"]:
        p = loaded.predict_proba([t])[0]
        print(f"  {t:25s} -> {loaded.classes_[p.argmax()]} ({p.max():.0%})")


if __name__ == "__main__":
    main()

from __future__ import annotations

from pathlib import Path
from typing import Any


def _lazy_plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def save_residual_histogram(residuals: list[float], out_path: str | Path, title: str = "Residual Error Distribution") -> str:
    plt = _lazy_plt()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(residuals, bins=40, color="#6366f1", edgecolor="white", alpha=0.85)
    ax.axvline(0.0, color="#ef4444", linestyle="--", linewidth=2, label="Zero error")
    if residuals:
        ax.axvline(sum(residuals) / len(residuals), color="#f59e0b", linestyle=":", linewidth=2, label="Mean residual")
    ax.set_title(title)
    ax.set_xlabel("Residual (actual − predicted, minutes)")
    ax.set_ylabel("Count")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return str(out_path)


def save_actual_vs_predicted(actual: list[float], predicted: list[float], out_path: str | Path) -> str:
    plt = _lazy_plt()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.scatter(actual, predicted, alpha=0.55, s=28, c="#0ea5e9", edgecolors="white", linewidths=0.3)
    max_val = max(max(actual or [1]), max(predicted or [1]), 1.0)
    ax.plot([0, max_val], [0, max_val], color="#ef4444", linestyle="--", linewidth=2, label="y = x")
    ax.set_title("Actual vs Predicted Duration")
    ax.set_xlabel("Actual duration (minutes)")
    ax.set_ylabel("Predicted duration (minutes)")
    ax.legend()
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return str(out_path)


def save_shap_importance(features: list[str], values: list[float], out_path: str | Path) -> str:
    plt = _lazy_plt()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pairs = sorted(zip(features, values), key=lambda x: abs(x[1]), reverse=True)[:15]
    labels, vals = zip(*pairs) if pairs else ([], [])
    fig, ax = plt.subplots(figsize=(12, 8))
    y_pos = range(len(labels))
    colors = ["#ef4444" if v < 0 else "#22c55e" for v in vals]
    ax.barh(list(y_pos), list(vals), color=colors)
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(list(labels))
    ax.set_xlabel("mean |SHAP value|")
    ax.set_title("Feature Importance (SHAP)")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return str(out_path)


def save_feature_importance_fallback(features: list[str], values: list[float], out_path: str | Path) -> str:
    plt = _lazy_plt()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 8))
    y_pos = range(len(features))
    ax.barh(list(y_pos), values, color="#0ea5e9")
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(features)
    ax.set_xlabel("Gain")
    ax.set_title("Feature Importance (LightGBM Gain)")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return str(out_path)


def save_confusion_heatmap(matrix: list[list[int]], labels: list[str], out_path: str | Path) -> str:
    plt = _lazy_plt()
    import numpy as np
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = np.asarray(matrix, dtype=float)
    fig, ax = plt.subplots(figsize=(8, 7))
    im = ax.imshow(data, cmap="Blues")
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Predicted severity")
    ax.set_ylabel("Actual severity")
    ax.set_title("Severity Confusion Matrix")
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            ax.text(j, i, int(data[i, j]), ha="center", va="center",
                    color="white" if data[i, j] > data.max() / 2 else "black")
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return str(out_path)


def save_bar_chart(labels: list[str], values: list[float], title: str, xlabel: str, ylabel: str, out_path: str | Path) -> str:
    plt = _lazy_plt()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(range(len(labels)), values, color="#2f6fed")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return str(out_path)

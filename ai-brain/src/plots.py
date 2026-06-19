from __future__ import annotations

from pathlib import Path
from typing import Any


def _lazy_plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _prepare_output_dir(outdir: str | Path) -> Path:
    path = Path(outdir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_bar_chart(labels: list[str], values: list[float], title: str, xlabel: str, ylabel: str, out_path: str | Path) -> str:
    plt = _lazy_plt()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 6))
    positions = range(len(labels))
    ax.bar(list(positions), values, color="#2f6fed")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_xticks(list(positions))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return str(out_path)


def save_horizontal_bar_chart(labels: list[str], values: list[float], title: str, xlabel: str, out_path: str | Path) -> str:
    plt = _lazy_plt()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 8))
    positions = range(len(labels))
    ax.barh(list(positions), values, color="#0ea5e9")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_yticks(list(positions))
    ax.set_yticklabels(labels)
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return str(out_path)


def save_line_chart(x_values: list[Any], y_values: list[float], title: str, xlabel: str, ylabel: str, out_path: str | Path) -> str:
    plt = _lazy_plt()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(x_values, y_values, marker="o", linewidth=2, color="#10b981")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return str(out_path)


def save_scatter_chart(x_values: list[float], y_values: list[float], title: str, xlabel: str, ylabel: str, out_path: str | Path, *, c_values: list[float] | None = None) -> str:
    plt = _lazy_plt()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 6))
    scatter = ax.scatter(x_values, y_values, c=c_values, cmap="viridis" if c_values else None, s=30, alpha=0.8)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(alpha=0.2)
    if c_values:
        fig.colorbar(scatter, ax=ax, label="Score")
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return str(out_path)


"""
SentinelDesk — Dataset Exploration Pipeline
Loads the Customer Support Tickets dataset, profiles it, and outputs
publication-quality visuals to the `outputs/` directory.
"""

import matplotlib
import pandas as pd

matplotlib.use("Agg")
from pathlib import Path

import matplotlib.pyplot as plt

OUT = Path("outputs")
OUT.mkdir(exist_ok=True)

FIGSIZE = (10, 6)
DPI = 150
PALETTE = {
    "blue": "#2a78d6",
    "orange": "#eb6834",
    "green": "#1baf7a",
    "yellow": "#eda100",
    "magenta": "#e87ba4",
    "violet": "#6250d6",
    "red": "#e34948",
    "aqua": "#008300",
}
COLORS = list(PALETTE.values())


def load_data():
    cache = Path("dataset_cache.parquet")
    if cache.exists():
        print("Loading from local parquet cache...")
        return pd.read_parquet(cache)
    print("Downloading from HuggingFace...")
    from datasets import load_dataset

    ds = load_dataset("Tobi-Bueck/customer-support-tickets")
    df = ds["train"].to_pandas()
    df.to_parquet(cache)
    return df


def split_populations(df):
    core = df[df["type"].notna()].copy()
    extra = df[df["type"].isna()].copy()
    return core, extra


def print_summary(df, core, extra):
    print("\n" + "=" * 60)
    print("DATASET SUMMARY")
    print("=" * 60)
    print(f"Total rows:        {len(df):,}")
    print(f"Core (labeled):    {len(core):,}")
    print(f"Extra (unlabeled): {len(extra):,}")
    print(f"Columns:           {len(df.columns)}")
    print(f"Column names:      {list(df.columns)}")

    print("\n--- Null counts (full dataset) ---")
    for col in df.columns:
        n = df[col].isna().sum()
        pct = 100 * n / len(df)
        print(f"  {col:15s}: {n:6,} ({pct:.1f}%)")

    print("\n--- Core target distributions ---")
    for col in ["type", "queue", "priority"]:
        print(f"\n  {col.upper()}:")
        for val, cnt in core[col].value_counts().items():
            pct = 100 * cnt / len(core)
            print(f"    {val:40s} {cnt:6,}  ({pct:.1f}%)")

    print("\n--- Language split ---")
    print(f"  Core:  {core['language'].value_counts().to_dict()}")
    print(f"  Extra: {extra['language'].value_counts().to_dict()}")

    print("\n--- Text lengths (core) ---")
    for col in ["subject", "body", "answer"]:
        s = core[col].dropna().str.len()
        print(
            f"  {col:10s}: mean={s.mean():.0f}, median={s.median():.0f}, "
            f"min={s.min():.0f}, max={s.max():.0f}"
        )

    print("\n--- Duplicates (core) ---")
    unique_bodies = core["body"].nunique()
    print(
        f"  Unique bodies: {unique_bodies:,} / {len(core):,} "
        f"({100 * (1 - unique_bodies / len(core)):.1f}% duplicates)"
    )

    print("\n--- Key observations ---")
    print("  - 13,178 extra rows are ALL German, have no type/answer/tags")
    print("  - Extra rows use 42 niche queues (Pets, News, etc.)")
    print("  - 'critical' and 'very_low' priorities exist ONLY in extra rows")
    print("  - Core has 10 queues, 4 types, 3 priorities")
    print("  - 8.6% of core subjects are null")
    print("  - <name> placeholder appears in 21% of core answers")


def plot_type_distribution(core):
    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    vc = core["type"].value_counts()
    bars = ax.bar(vc.index, vc.values, color=COLORS[: len(vc)], width=0.6, zorder=3)
    for bar, val in zip(bars, vc.values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            val + 200,
            f"{val:,}",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
        )
    ax.set_title("Ticket type distribution (core: 48,587 rows)", fontsize=14, pad=12)
    ax.set_ylabel("Count")
    ax.grid(axis="y", alpha=0.3, zorder=0)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(OUT / "01_type_distribution.png")
    plt.close(fig)
    print("  Saved 01_type_distribution.png")


def plot_priority_distribution(core):
    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    order = ["high", "medium", "low"]
    vc = core["priority"].value_counts().reindex(order)
    colors_map = {
        "high": PALETTE["red"],
        "medium": PALETTE["yellow"],
        "low": PALETTE["green"],
    }
    bars = ax.bar(
        vc.index, vc.values, color=[colors_map[p] for p in order], width=0.6, zorder=3
    )
    for bar, val in zip(bars, vc.values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            val + 200,
            f"{val:,}",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
        )
    ax.set_title("Priority distribution (core)", fontsize=14, pad=12)
    ax.set_ylabel("Count")
    ax.grid(axis="y", alpha=0.3, zorder=0)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(OUT / "02_priority_distribution.png")
    plt.close(fig)
    print("  Saved 02_priority_distribution.png")


def plot_queue_distribution(core):
    fig, ax = plt.subplots(figsize=(10, 7), dpi=DPI)
    vc = core["queue"].value_counts()
    y_pos = range(len(vc))
    bars = ax.barh(y_pos, vc.values, color=PALETTE["blue"], height=0.7, zorder=3)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(vc.index, fontsize=10)
    ax.invert_yaxis()
    for bar, val in zip(bars, vc.values):
        ax.text(
            val + 100,
            bar.get_y() + bar.get_height() / 2,
            f"{val:,}",
            va="center",
            fontsize=10,
        )
    ax.set_title("Queue distribution (core: 10 queues)", fontsize=14, pad=12)
    ax.set_xlabel("Count")
    ax.grid(axis="x", alpha=0.3, zorder=0)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(OUT / "03_queue_distribution.png")
    plt.close(fig)
    print("  Saved 03_queue_distribution.png")


def plot_language_split(core, extra):
    fig, axes = plt.subplots(1, 2, figsize=(10, 5), dpi=DPI)

    core_lang = core["language"].value_counts()
    axes[0].pie(
        core_lang.values,
        labels=[f"{l} ({v:,})" for l, v in core_lang.items()],
        colors=[PALETTE["blue"], PALETTE["orange"]],
        autopct="%1.1f%%",
        startangle=90,
        textprops={"fontsize": 11},
    )
    axes[0].set_title("Core data (48,587)", fontsize=13)

    extra_lang = extra["language"].value_counts()
    axes[1].pie(
        extra_lang.values,
        labels=[f"{l} ({v:,})" for l, v in extra_lang.items()],
        colors=[PALETTE["orange"]],
        autopct="%1.1f%%",
        startangle=90,
        textprops={"fontsize": 11},
    )
    axes[1].set_title("Extra data (13,178)", fontsize=13)

    fig.suptitle("Language distribution", fontsize=14, y=1.02)
    fig.tight_layout()
    fig.savefig(OUT / "04_language_split.png", bbox_inches="tight")
    plt.close(fig)
    print("  Saved 04_language_split.png")


def plot_type_x_priority(core):
    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    ct = pd.crosstab(core["type"], core["priority"])
    ct = ct[["high", "medium", "low"]]
    ct.plot(
        kind="bar",
        ax=ax,
        color=[PALETTE["red"], PALETTE["yellow"], PALETTE["green"]],
        width=0.7,
        zorder=3,
    )
    ax.set_title("Type x Priority (core)", fontsize=14, pad=12)
    ax.set_ylabel("Count")
    ax.set_xlabel("")
    ax.legend(title="Priority")
    ax.set_xticklabels(ax.get_xticklabels(), rotation=0)
    ax.grid(axis="y", alpha=0.3, zorder=0)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(OUT / "05_type_x_priority.png")
    plt.close(fig)
    print("  Saved 05_type_x_priority.png")


def plot_type_x_queue(core):
    fig, ax = plt.subplots(figsize=(12, 7), dpi=DPI)
    ct = pd.crosstab(core["queue"], core["type"])
    ct = ct.sort_values(ct.columns.tolist(), ascending=False)
    ct.plot(kind="barh", ax=ax, stacked=True, color=COLORS[:4], width=0.7, zorder=3)
    ax.set_title("Queue x Type (core)", fontsize=14, pad=12)
    ax.set_xlabel("Count")
    ax.set_ylabel("")
    ax.legend(title="Type", loc="lower right")
    ax.grid(axis="x", alpha=0.3, zorder=0)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(OUT / "06_type_x_queue.png")
    plt.close(fig)
    print("  Saved 06_type_x_queue.png")


def plot_null_heatmap(df):
    fig, ax = plt.subplots(figsize=(10, 5), dpi=DPI)
    cols = [
        "subject",
        "body",
        "answer",
        "type",
        "queue",
        "priority",
        "language",
        "version",
        "tag_1",
        "tag_2",
        "tag_3",
        "tag_4",
        "tag_5",
        "tag_6",
        "tag_7",
        "tag_8",
    ]
    null_pcts = [(df[c].isna().sum() / len(df)) * 100 for c in cols]
    bars = ax.barh(cols, null_pcts, color=PALETTE["orange"], height=0.7, zorder=3)
    for bar, pct in zip(bars, null_pcts):
        if pct > 1:
            ax.text(
                pct + 0.5,
                bar.get_y() + bar.get_height() / 2,
                f"{pct:.1f}%",
                va="center",
                fontsize=9,
            )
    ax.set_title("Null/missing values by column (full dataset)", fontsize=14, pad=12)
    ax.set_xlabel("% null")
    ax.set_xlim(0, 105)
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.3, zorder=0)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(OUT / "07_null_heatmap.png")
    plt.close(fig)
    print("  Saved 07_null_heatmap.png")


def plot_text_length_distributions(core):
    fig, axes = plt.subplots(1, 3, figsize=(14, 5), dpi=DPI)
    for ax, col, color in zip(
        axes,
        ["subject", "body", "answer"],
        [PALETTE["blue"], PALETTE["green"], PALETTE["violet"]],
    ):
        data = core[col].dropna().str.len()
        ax.hist(data, bins=50, color=color, alpha=0.8, edgecolor="white", linewidth=0.5)
        ax.axvline(
            data.mean(),
            color="black",
            linestyle="--",
            linewidth=1,
            label=f"mean={data.mean():.0f}",
        )
        ax.axvline(
            data.median(),
            color="gray",
            linestyle=":",
            linewidth=1,
            label=f"median={data.median():.0f}",
        )
        ax.set_title(f"{col} length", fontsize=13)
        ax.set_xlabel("Characters")
        ax.set_ylabel("Count")
        ax.legend(fontsize=9)
        ax.grid(axis="y", alpha=0.3)
    fig.suptitle("Text length distributions (core)", fontsize=14, y=1.02)
    fig.tight_layout()
    fig.savefig(OUT / "08_text_lengths.png", bbox_inches="tight")
    plt.close(fig)
    print("  Saved 08_text_lengths.png")


def plot_tag_sparsity(core):
    fig, ax = plt.subplots(figsize=(8, 4), dpi=DPI)
    tags = [f"tag_{i}" for i in range(1, 9)]
    fill_pcts = [100 * core[t].notna().sum() / len(core) for t in tags]
    bars = ax.bar(tags, fill_pcts, color=PALETTE["aqua"], width=0.6, zorder=3)
    for bar, pct in zip(bars, fill_pcts):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            pct + 1,
            f"{pct:.0f}%",
            ha="center",
            va="bottom",
            fontsize=10,
        )
    ax.set_title("Tag fill rate (core)", fontsize=14, pad=12)
    ax.set_ylabel("% non-null")
    ax.set_ylim(0, 110)
    ax.grid(axis="y", alpha=0.3, zorder=0)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(OUT / "09_tag_sparsity.png")
    plt.close(fig)
    print("  Saved 09_tag_sparsity.png")


def plot_class_imbalance_summary(core):
    fig, axes = plt.subplots(1, 3, figsize=(14, 5), dpi=DPI)
    targets = [
        ("type", COLORS[:4]),
        ("priority", [PALETTE["red"], PALETTE["yellow"], PALETTE["green"]]),
        ("queue", [PALETTE["blue"]] * 10),
    ]
    for ax, (col, colors) in zip(axes, targets):
        vc = core[col].value_counts()
        pcts = 100 * vc / vc.sum()
        bars = ax.barh(
            range(len(vc)), pcts.values, color=colors[: len(vc)], height=0.6, zorder=3
        )
        ax.set_yticks(range(len(vc)))
        labels = [v[:20] + "..." if len(v) > 20 else v for v in vc.index]
        ax.set_yticklabels(labels, fontsize=9)
        ax.invert_yaxis()
        for bar, pct in zip(bars, pcts.values):
            ax.text(
                pct + 0.3,
                bar.get_y() + bar.get_height() / 2,
                f"{pct:.1f}%",
                va="center",
                fontsize=9,
            )
        ax.set_title(col.upper(), fontsize=13)
        ax.set_xlabel("% of core")
        ax.grid(axis="x", alpha=0.3, zorder=0)
        ax.set_axisbelow(True)
    fig.suptitle("Class distribution comparison (core)", fontsize=14, y=1.02)
    fig.tight_layout()
    fig.savefig(OUT / "10_class_imbalance.png", bbox_inches="tight")
    plt.close(fig)
    print("  Saved 10_class_imbalance.png")


def plot_high_priority_incidents(core):
    hi = core[(core["type"] == "Incident") & (core["priority"] == "high")]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), dpi=DPI)

    vc = hi["queue"].value_counts()
    axes[0].barh(range(len(vc)), vc.values, color=PALETTE["red"], height=0.6, zorder=3)
    axes[0].set_yticks(range(len(vc)))
    labels = [v[:25] + "..." if len(v) > 25 else v for v in vc.index]
    axes[0].set_yticklabels(labels, fontsize=9)
    axes[0].invert_yaxis()
    axes[0].set_title(f"High-priority incidents by queue (n={len(hi):,})", fontsize=12)
    axes[0].set_xlabel("Count")
    axes[0].grid(axis="x", alpha=0.3, zorder=0)
    axes[0].set_axisbelow(True)

    lang_vc = hi["language"].value_counts()
    axes[1].pie(
        lang_vc.values,
        labels=[f"{l} ({v:,})" for l, v in lang_vc.items()],
        colors=[PALETTE["blue"], PALETTE["orange"]],
        autopct="%1.1f%%",
        startangle=90,
        textprops={"fontsize": 11},
    )
    axes[1].set_title("Language split", fontsize=12)

    fig.suptitle("Escalation cases: high-priority incidents", fontsize=14, y=1.02)
    fig.tight_layout()
    fig.savefig(OUT / "11_escalation_cases.png", bbox_inches="tight")
    plt.close(fig)
    print("  Saved 11_escalation_cases.png")


def main():
    print("=" * 60)
    print("SentinelDesk — Data Exploration Pipeline")
    print("=" * 60)

    df = load_data()
    core, extra = split_populations(df)
    print_summary(df, core, extra)

    print(f"\nGenerating visualizations to {OUT}/...")
    plot_type_distribution(core)
    plot_priority_distribution(core)
    plot_queue_distribution(core)
    plot_language_split(core, extra)
    plot_type_x_priority(core)
    plot_type_x_queue(core)
    plot_null_heatmap(df)
    plot_text_length_distributions(core)
    plot_tag_sparsity(core)
    plot_class_imbalance_summary(core)
    plot_high_priority_incidents(core)

    print(f"\nDone! {len(list(OUT.glob('*.png')))} charts saved to {OUT}/")


if __name__ == "__main__":
    main()

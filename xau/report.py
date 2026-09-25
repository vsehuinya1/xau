"""Markdown tables for research results."""
import numpy as np


def fmt(v):
    if isinstance(v, (bool, np.bool_)):
        return "yes" if v else "no"
    if isinstance(v, (float, np.floating)):
        return "" if np.isnan(v) else f"{v:.0f}" if float(v).is_integer() and abs(v) >= 10 else f"{v:.3f}"
    return str(v)


def md(df):
    """DataFrame as a markdown table; tuple labels are joined with ' / '."""
    label = lambda x: " / ".join(map(str, x)) if isinstance(x, (tuple, list)) else str(x)  # noqa: E731
    cols = [label(list(df.index.names) if df.index.nlevels > 1 else df.index.name or "")] + [label(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for idx, row in df.iterrows():
        lines.append("| " + " | ".join([label(idx)] + [fmt(v) for v in row]) + " |")
    return "\n".join(lines)

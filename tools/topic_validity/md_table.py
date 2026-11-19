from __future__ import annotations

import pandas as pd


def df_to_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return "_(empty)_"
    cols = list(df.columns)
    lines = [
        "| " + " | ".join(str(c) for c in cols) + " |",
        "| " + " | ".join("---" for _ in cols) + " |",
    ]
    for _, row in df.iterrows():
        lines.append(
            "| "
            + " | ".join(str(row[c]).replace("|", "\\|").replace("\n", " ") for c in cols)
            + " |"
        )
    return "\n".join(lines)
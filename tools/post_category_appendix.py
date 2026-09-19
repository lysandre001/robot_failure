#!/usr/bin/env python3
"""YouTube 帖子分类附录表：config 五档校验，人的形象分析档合并为服务照护。"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency

from phase1.config import ROOT
from phase1.post_category_labels import (
    HUMAN_ROLE_ANALYSIS_EN,
    HUMAN_ROLE_ANALYSIS_ORDER,
    HUMAN_ROLE_MERGE_RULE,
    HUMAN_ROLES_CANONICAL,
    normalize_human_role,
)

ROBOT_STATES = ["失败", "弱势", "常态", "强势", "混合"]
ROBOT_STATES_EN = {
    "失败": "Failure",
    "弱势": "Weak",
    "常态": "Normal",
    "强势": "Strong",
    "混合": "Mixed",
}

HUMAN_IMAGES_ANALYSIS = list(HUMAN_ROLES_CANONICAL)

YOUTUBE_CONFIG_EVENTS = {
    "youtube_2604-marathon.csv": ("Marathon", "Beijing Humanoid Robot Marathon"),
    "youtube_2608-olympic.csv": ("Games", "World Humanoid Robot Games"),
}

HUMAN_IMAGE_ANALYSIS_COL = "人的形象"


def attach_human_role_analysis(df: pd.DataFrame, *, source_col: str = "人的形象") -> pd.DataFrame:
    out = df.copy()
    out[source_col] = out[source_col].map(lambda x: normalize_human_role(x) or "")
    return out


def load_analyzed_competition_posts(config_dir: Path | None = None) -> pd.DataFrame:
    config_dir = config_dir or (ROOT / "config" / "post_category")
    frames = []
    for fname in YOUTUBE_CONFIG_EVENTS:
        df = pd.read_csv(config_dir / fname, dtype=str).fillna("")
        assert df["帖子id"].is_unique, f"{fname}: 帖子id 重复"
        bad_rs = set(df["机器人状态"]) - set(ROBOT_STATES) - {""}
        df["人的形象"] = df["人的形象"].map(lambda x: normalize_human_role(x) or "")
        bad_hi = set(df["人的形象"]) - set(HUMAN_ROLES_CANONICAL) - {""}
        if bad_rs or bad_hi:
            raise ValueError(f"{fname}: 越界标签 robot={bad_rs} human={bad_hi}")
        df["event"] = YOUTUBE_CONFIG_EVENTS[fname][0]
        frames.append(df)
    posts = pd.concat(frames, ignore_index=True)
    labeled = posts[posts["是否比赛视频"] == "是"].copy()
    incomplete = labeled[(labeled["机器人状态"] == "") | (labeled["人的形象"] == "")]
    analyzed = labeled.drop(incomplete.index).copy()
    return attach_human_role_analysis(analyzed)


def dist_tables(df: pd.DataFrame, dim: str, order: list[str]):
    ct = pd.crosstab(df[dim], df["event"]).reindex(order).fillna(0).astype(int)
    ct["Merged"] = ct.sum(axis=1)
    pct = ct.div(ct.sum(axis=0), axis=1).mul(100).round(1)
    disp = pd.DataFrame(
        {
            c: ct[c].astype(str) + " (" + pct[c].round(1).astype(str) + "%)"
            for c in ct.columns
        }
    )
    disp.loc["Total"] = ct.sum().astype(str) + " (100.0%)"
    return ct, pct, disp


def crosstabs_by_event(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    tabs: dict[str, pd.DataFrame] = {}
    for ev in ["Marathon", "Games", "Merged"]:
        sub = df if ev == "Merged" else df[df["event"] == ev]
        t = pd.crosstab(sub["机器人状态"], sub["人的形象"])
        t = t.reindex(index=ROBOT_STATES, columns=HUMAN_IMAGES_ANALYSIS).fillna(0).astype(int)
        t["Total"] = t.sum(axis=1)
        t.loc["Total"] = t.sum()
        tabs[ev] = t
    return tabs


def _tex_dist_table(ct, pct, en_map, caption, label) -> str:
    bs = chr(92)
    nl = chr(10)
    lines = [
        bs + "begin{table}[t]",
        "  " + bs + "centering",
        "  " + bs + f"caption{{{caption}}}",
        "  " + bs + f"label{{{label}}}",
        "  " + bs + "begin{tabular}{lrrr}",
        "    " + bs + "toprule",
        "    Category & Marathon & Games & Merged " + bs * 2,
        "    " + bs + "midrule",
    ]
    for cat in ct.index:
        cells = " & ".join(
            f"{ct.loc[cat, c]} ({pct.loc[cat, c]:.1f}{bs}%)" for c in ct.columns
        )
        lines.append(f"    {en_map[cat]} & {cells} " + bs * 2)
    lines.append("    " + bs + "midrule")
    tot = " & ".join(f"{ct[c].sum()} (100.0{bs}%)" for c in ct.columns)
    lines.append(f"    Total & {tot} " + bs * 2)
    lines.extend(["    " + bs + "bottomrule", "  " + bs + "end{tabular}", bs + "end{table}"])
    return nl.join(lines)


def _tex_crosstab_panel(t: pd.DataFrame, ev: str, n: int) -> str:
    bs = chr(92)
    nl = chr(10)
    n_hi = len(HUMAN_IMAGES_ANALYSIS)
    lines = [
        f"  {bs}multicolumn{{{n_hi + 1}}}{{c}}{{ {bs}textit{{{ev}}} (n={n}) }} " + bs * 2,
        "  " + bs + "midrule",
        "  & "
        + " & ".join(HUMAN_ROLE_ANALYSIS_EN[h] for h in HUMAN_IMAGES_ANALYSIS)
        + " & Total "
        + bs * 2,
        "  " + bs + "midrule",
    ]
    for rs in ROBOT_STATES:
        row = " & ".join(str(t.loc[rs, h]) for h in HUMAN_IMAGES_ANALYSIS) + f" & {t.loc[rs, 'Total']}"
        lines.append(f"  {ROBOT_STATES_EN[rs]} & {row} " + bs * 2)
    lines.append("  " + bs + "midrule")
    row = " & ".join(str(t.loc["Total", h]) for h in HUMAN_IMAGES_ANALYSIS) + f" & {t.loc['Total', 'Total']}"
    lines.append(f"  Total & {row} " + bs * 2)
    return nl.join(lines)


def write_appendix_artifacts(out_dir: Path, *, analyzed: pd.DataFrame | None = None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    analyzed = analyzed if analyzed is not None else load_analyzed_competition_posts()

    rs_ct, rs_pct, _ = dist_tables(analyzed, "机器人状态", ROBOT_STATES)
    hi_ct, hi_pct, _ = dist_tables(analyzed, "人的形象", HUMAN_IMAGES_ANALYSIS)
    xtabs = crosstabs_by_event(analyzed)

    rs_ct.to_csv(out_dir / "table_a_robot_state_counts.csv", encoding="utf-8-sig")
    hi_ct.to_csv(out_dir / "table_b_human_image_counts.csv", encoding="utf-8-sig")
    for ev, t in xtabs.items():
        t.to_csv(out_dir / f"table_c_crosstab_{ev.lower()}.csv", encoding="utf-8-sig")

    bs = chr(92)
    nl = chr(10)
    tex_parts = [
        _tex_dist_table(
            rs_ct,
            rs_pct,
            ROBOT_STATES_EN,
            "Distribution of robot state across events (post counts with within-event percentages).",
            "tab:app-state-dist",
        ),
        _tex_dist_table(
            hi_ct,
            hi_pct,
            HUMAN_ROLE_ANALYSIS_EN,
            "Distribution of human image across events (post counts; service roles merged).",
            "tab:app-image-dist",
        ),
    ]
    xt_lines = [
        bs + "begin{table}[t]",
        "  " + bs + "centering",
        "  "
        + bs
        + "caption{Cross-tabulation of robot state "
        + bs
        + "times human image (analysis groups), by event and merged.}",
        "  " + bs + "label{tab:app-cross}",
        "  " + bs + f"begin{{tabular}}{{l{'r' * (len(HUMAN_IMAGES_ANALYSIS) + 1)}}}",
        "    " + bs + "toprule",
    ]
    for i, ev in enumerate(["Marathon", "Games", "Merged"]):
        if i:
            xt_lines.append("    " + bs + "midrule")
        xt_lines.append(_tex_crosstab_panel(xtabs[ev], ev, int(xtabs[ev].loc["Total", "Total"])))
    xt_lines.extend(["    " + bs + "bottomrule", "  " + bs + "end{tabular}", bs + "end{table}"])
    tex_parts.append(nl.join(xt_lines))

    (out_dir / "post_category_distribution.tex").write_text((nl * 2).join(tex_parts), encoding="utf-8")

    for dim, order in [("机器人状态", ROBOT_STATES), ("人的形象", HUMAN_IMAGES_ANALYSIS)]:
        ct = pd.crosstab(analyzed[dim], analyzed["event"]).reindex(order).fillna(0)
        chi2, p, dof, exp = chi2_contingency(ct)
        n = int(ct.to_numpy().sum())
        cramers_v = np.sqrt(chi2 / (n * (min(ct.shape) - 1)))
        print(f"{dim}: chi2({dof}) = {chi2:.2f}, p = {p:.4f}, Cramer V = {cramers_v:.3f}, n = {n}")
        if (exp < 5).any():
            print(f"  [warn] {(exp < 5).sum()} 格期望频数 < 5 (min={exp.min():.1f})")

    print(f"written appendix → {out_dir}")
    print(HUMAN_ROLE_MERGE_RULE)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Regenerate YouTube post category appendix CSV/LaTeX")
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "output" / "experiments" / "appendix_postdist_0919",
    )
    args = ap.parse_args()
    write_appendix_artifacts(args.out_dir)


if __name__ == "__main__":
    main()

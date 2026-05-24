"""[已弃用] Notebook 一键：Phase1 + relation_v1。请改用 run_preprocess.py + topic_modeling。"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from phase1.config import OUT, ROOT
from phase1.pipeline import run_phase1_pipeline
from phase1._archived.relation_detection import RelationExperimentConfig, run_relation_v1_experiment


def resolve_clean_comments_unified_csv() -> Path:
    """与 pipeline 输出一致：优先 output/phase1/clean_comments_unified.csv，否则 data/ 子目录。"""
    primary = OUT / "clean_comments_unified.csv"
    if primary.is_file():
        return primary
    alt = OUT / "data" / "clean_comments_unified.csv"
    if alt.is_file():
        return alt
    return primary


@dataclass
class NotebookRunConfig:
    """Notebook 里只改这一个配置即可。"""

    xlsx_path: Path
    min_chars: int = 5
    drop_repeated_single_char: bool = True
    run_phase1_full: bool = True
    run_relation_v1: bool = True
    relation_lexicon: Path | None = None
    run_id: str | None = None
    mirror_to_phase1_data: bool = False
    run_topics: bool = True
    verbose: bool = True

    def resolved_lexicon(self) -> Path:
        return self.relation_lexicon or (ROOT / "config" / "relation_lexicon_v1.csv")


def run_notebook(cfg: NotebookRunConfig | dict[str, Any]) -> dict[str, Path]:
    """
    一键运行：可选完整 Phase1，再可选 relation_v1。

    Returns
    -------
    dict with keys: run_dir (optional), phase1_out, unified_csv, summary_md, overall_csv, ...
    """
    if isinstance(cfg, dict):
        raw = dict(cfg)
        if "xlsx_path" in raw and not isinstance(raw["xlsx_path"], Path):
            raw["xlsx_path"] = Path(raw["xlsx_path"])
        if raw.get("relation_lexicon") is not None and not isinstance(raw["relation_lexicon"], Path):
            raw["relation_lexicon"] = Path(raw["relation_lexicon"])
        cfg = NotebookRunConfig(
            **{k: v for k, v in raw.items() if k in NotebookRunConfig.__dataclass_fields__}
        )

    if not cfg.xlsx_path.is_file():
        raise FileNotFoundError(f"找不到 Excel: {cfg.xlsx_path}")

    os.environ["ROBOTIC_FAILURE_XLSX"] = str(cfg.xlsx_path.resolve())

    out: dict[str, Path] = {"phase1_out": OUT}

    if cfg.run_phase1_full:
        run_phase1_pipeline(
            xlsx=cfg.xlsx_path,
            min_chars=cfg.min_chars,
            drop_repeated_single_char=cfg.drop_repeated_single_char,
            run_topics=cfg.run_topics,
            run_lda_topics=False,
            verbose=cfg.verbose,
        )

    unified_csv = resolve_clean_comments_unified_csv()
    out["unified_csv"] = unified_csv

    if not cfg.run_relation_v1:
        return out

    if not unified_csv.is_file():
        raise FileNotFoundError(
            f"找不到过滤后统一评论表，请先 run_phase1_full=True 或生成 {unified_csv}"
        )

    run_id = cfg.run_id or f"{datetime.now().strftime('%Y-%m-%d')}_relation_v1_notebook"
    experiments_root = ROOT / "output" / "experiments"
    phase1_data_dir = OUT / "data"

    rel_cfg = RelationExperimentConfig(
        run_id=run_id,
        input_comments_csv=unified_csv,
        relation_lexicon_csv=cfg.resolved_lexicon(),
        experiments_root=experiments_root,
        phase1_data_dir=phase1_data_dir,
        mirror_to_phase1_data=cfg.mirror_to_phase1_data,
    )
    run_dir = run_relation_v1_experiment(rel_cfg)
    out["run_dir"] = run_dir
    out["summary_md"] = run_dir / "summary.md"
    out["overall_csv"] = run_dir / "relation_v1_overall.csv"
    out["audit_csv"] = run_dir / "relation_v1_error_audit.csv"
    out["config_json"] = run_dir / "config.json"
    return out

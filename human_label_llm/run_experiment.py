#!/usr/bin/env python3
"""统一 experiment 启动入口（从仓库根目录执行）。

  python human_label_llm/run_experiment.py dryrun object
  python human_label_llm/run_experiment.py infer emotion
  python human_label_llm/run_experiment.py compare -c human_label_llm/experiment/20260530_emotion_v1_comment_only_test.yaml
  python human_label_llm/run_experiment.py all object

别名：object → 评估对象；emotion → 情感。
若存在 .venv，会自动改用 .venv/bin/python。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_VENV_PY = ROOT / ".venv" / "bin" / "python"
EXPERIMENT_DIR = Path(__file__).resolve().parent / "experiment"

ALIASES: dict[str, str] = {
    "object": "20260529_object_v1_comment_only_test.yaml",
    "emotion": "20260530_emotion_v1_comment_only_test.yaml",
    "object_caption": "20260531_object_v1_comment_caption.yaml",
    "emotion_caption": "20260531_emotion_v1_comment_caption.yaml",
}


def _ensure_project_venv() -> None:
    if not _VENV_PY.is_file():
        return
    try:
        if Path(sys.executable).resolve() == _VENV_PY.resolve():
            return
    except OSError:
        pass
    os.execv(str(_VENV_PY), [str(_VENV_PY), *sys.argv])


_ensure_project_venv()

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from human_label_llm.run import (  # noqa: E402
    cmd_compare,
    cmd_dryrun,
    cmd_infer,
    load_config,
    resolve_config_path,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "step",
        nargs="?",
        default="all",
        choices=("dryrun", "infer", "compare", "all"),
        help="默认 all = dryrun → infer → compare",
    )
    parser.add_argument(
        "experiment",
        nargs="?",
        default=None,
        help="experiment 别名（object/emotion）或 yaml 文件名（可省略 .yaml）",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=None,
        help="experiment yaml 路径（优先于 positional experiment）",
    )
    parser.add_argument("-n", type=int, default=2, help="dryrun 抽样行数")
    args = parser.parse_args()

    if args.config is None and args.experiment is None:
        parser.error("请指定 experiment（object/emotion）或 -c path/to/config.yaml")

    cfg_path = resolve_config_path(
        args.config or args.experiment,
        experiment_dir=EXPERIMENT_DIR,
        aliases=ALIASES,
    )
    cfg = load_config(cfg_path)
    run_id = cfg.get("run_id", cfg_path.stem)

    if args.step in ("dryrun", "all"):
        cmd_dryrun(cfg, n=args.n)
    if args.step in ("infer", "all"):
        cmd_infer(cfg, cfg_path)
    if args.step in ("compare", "all"):
        cmd_compare(cfg)

    if args.step == "all":
        print(f"\nDone. Output: human_label_llm/output/{run_id}/")


if __name__ == "__main__":
    main()

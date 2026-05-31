#!/usr/bin/env python3
"""本实验一键入口（从仓库根目录执行）：

  python human_label_llm/experiment/20260529_object_v1_comment_only_test.py infer

  若存在 .venv，会自动改用 .venv/bin/python（避免 base conda 的 numpy/pandas 冲突）。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_VENV_PY = ROOT / ".venv" / "bin" / "python"


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

CONFIG = Path(__file__).resolve().parent / "20260529_object_v1_comment_only_test.yaml"

from human_label_llm.run import (  # noqa: E402
    _resolve_path,
    cmd_compare,
    cmd_dryrun,
    cmd_infer,
    load_config,
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
    parser.add_argument("-n", type=int, default=2, help="dryrun 抽样行数")
    args = parser.parse_args()

    cfg_path = _resolve_path(CONFIG)
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

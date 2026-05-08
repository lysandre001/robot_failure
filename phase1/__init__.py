"""第一阶段探索性分析：模块化包。

避免在 `import phase1` 或 `from phase1.preprocess import ...` 时加载 analysis/pipeline（及 jieba 等）。
`main` / `run_phase1_pipeline` 仅在显式使用时再导入。
"""

from __future__ import annotations

__all__ = ["main", "run_phase1_pipeline"]


def __getattr__(name: str):
    if name == "main":
        from phase1.pipeline import main as m

        return m
    if name == "run_phase1_pipeline":
        from phase1.pipeline import run_phase1_pipeline as run

        return run
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

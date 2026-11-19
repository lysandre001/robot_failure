"""§6 — run STM via R when available."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .paths import ROOT, validity_dir


def run_stm() -> str:
    stm_out = validity_dir() / "stm"
    stm_out.mkdir(parents=True, exist_ok=True)
    rscript = shutil.which("Rscript")
    if not rscript and Path("/opt/homebrew/bin/Rscript").is_file():
        rscript = "/opt/homebrew/bin/Rscript"
    if not rscript:
        msg = (
            "# STM not run\n\n"
            "`Rscript` not found. Install R (`brew install r`) and R packages: "
            "`install.packages(c('stm','quanteda','readr','dplyr'))`.\n"
            "Then re-run: `.venv/bin/python tools/youtube_en_topic_validity_suite.py --only stm`"
        )
        (stm_out / "STM_BLOCKED.md").write_text(msg, encoding="utf-8")
        return "blocked"

    script = Path(__file__).resolve().parent / "stm_fit.R"
    try:
        subprocess.run(
            [rscript, str(script), str(ROOT)],
            check=True,
            capture_output=True,
            text=True,
        )
        return "ok"
    except subprocess.CalledProcessError as e:
        (stm_out / "STM_BLOCKED.md").write_text(
            "# STM failed\n\n```\n"
            + (e.stderr or e.stdout or str(e))
            + "\n```\n",
            encoding="utf-8",
        )
        return "failed"
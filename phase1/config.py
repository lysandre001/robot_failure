"""路径与 Matplotlib 环境（可复现）。项目根目录为仓库根。"""
from __future__ import annotations

import os
from pathlib import Path

# 项目根：phase1/ 的父目录
ROOT = Path(__file__).resolve().parents[1]

OUT = ROOT / "output" / "phase1"
FIG = OUT / "figures"
# Canonical 清洗产物目录（主题建模默认读此处）
CLEAN_DIR = ROOT / "data" / "clean"
CLEAN_COMMENTS_UNIFIED = CLEAN_DIR / "clean_comments_unified.csv"
# 默认数据文件；可用环境变量 ROBOTIC_FAILURE_XLSX 或 load_raw_frames(xlsx=...) 覆盖
XLSX = ROOT / "小红书帖子数据.xlsx"
# 帖子编码：`config/post_category_by_post.csv`（``机器人状态`` + ``人的形象``；合并为 ``post_category``）
POST_CATEGORY_BY_POST_CSV = ROOT / "config" / "post_category_by_post.csv"

# 避免无写权限环境下的 Matplotlib 缓存问题
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".matplotlib_cache"))
(ROOT / ".matplotlib_cache").mkdir(parents=True, exist_ok=True)


def configure_matplotlib() -> None:
    """在导入 pyplot 前调用。"""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = [
        "PingFang SC",
        "Hiragino Sans GB",
        "Arial Unicode MS",
        "Noto Sans CJK SC",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False

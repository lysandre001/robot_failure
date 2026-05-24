"""DEPRECATED：CLI 已迁至 tools/merge_xhs_batches_xlsx.py。库函数见 phase1.xhs_io.build_merged_xlsx。"""
from phase1.xhs_io import build_merged_xlsx as build_merged  # noqa: F401


def main() -> None:
    from tools.merge_xhs_batches_xlsx import main as _main

    _main()


if __name__ == "__main__":
    main()

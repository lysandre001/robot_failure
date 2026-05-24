"""DEPRECATED：CLI 已迁至 tools/ingest_xhs_batch2_csv.py。库函数见 phase1.xhs_io。"""
from phase1.xhs_io import (  # noqa: F401
    EXPECTED_COLS,
    POST_ID_RE,
    build_counts_sheet,
    check_overlap_with_batch1,
    is_valid_post_id,
    sanitize_xhs_wide_csv,
)


def main() -> None:
    from tools.ingest_xhs_batch2_csv import main as _main

    _main()


if __name__ == "__main__":
    main()

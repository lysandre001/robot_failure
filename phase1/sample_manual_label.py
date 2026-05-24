"""DEPRECATED：CLI 已迁至 tools/sample_manual_label.py。库函数见 phase1.manual_label、phase1.post_links。"""
from phase1.manual_label import enrich_for_labeling, sample_l1_per_post  # noqa: F401
from phase1.post_links import DEFAULT_POSTS_CSV, attach_post_links, load_post_links  # noqa: F401


def main() -> None:
    from tools.sample_manual_label import main as _main

    _main()


if __name__ == "__main__":
    main()

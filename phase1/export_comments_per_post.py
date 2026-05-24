"""DEPRECATED：CLI 已迁至 tools/export_comments_per_post.py。"""
from tools.export_comments_per_post import export_counts  # noqa: F401


def main() -> None:
    from tools.export_comments_per_post import main as _main

    _main()


if __name__ == "__main__":
    main()

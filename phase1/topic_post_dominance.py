"""DEPRECATED：CLI 已迁至 tools/topic_post_dominance.py。"""
from tools.topic_post_dominance import compute_post_dominance, resolve_topic_column  # noqa: F401


def main() -> None:
    from tools.topic_post_dominance import main as _main

    _main()


if __name__ == "__main__":
    main()

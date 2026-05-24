"""DEPRECATED：CLI 已迁至 tools/topic_like_concentration.py。"""
from tools.topic_like_concentration import compute_topic_like_concentration  # noqa: F401


def main() -> None:
    from tools.topic_like_concentration import main as _main

    _main()


if __name__ == "__main__":
    main()

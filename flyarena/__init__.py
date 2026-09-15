import sys

if sys.version_info < (3, 11):
    raise SystemExit(
        "FlyArena 需要 Python 3.11 以上，目前是 %d.%d。" % sys.version_info[:2]
        + "Mac 可到 python.org 下載，或用 Homebrew：brew install python@3.12"
    )

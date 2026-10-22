"""配布用 moviealpha-gui.exe の入口。ダブルクリックや動画のドロップで GUI を開く。"""
import sys

from moviealpha.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["--gui", *sys.argv[1:]]))

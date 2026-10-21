"""Entry point for the GitHub Action (action.yml).

Live mode is deliberately not wired in this build: the backtest and a shadow week come first. Until then the
Action only explains what it would do, so a premature install can't touch a repo.
"""
import os
import sys


def main() -> None:
    mode = os.environ.get("MB_MODE", "")
    print(f"maintainer-bot: '{mode}' mode is not enabled yet (backtest and shadow week first).")
    sys.exit(0)


if __name__ == "__main__":
    main()

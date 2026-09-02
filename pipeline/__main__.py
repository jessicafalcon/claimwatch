"""`python -m pipeline …` — the entry Make calls. The logic and its validators
live in `pipeline.cli` (importable by tests)."""

import sys

from pipeline.cli import main

if __name__ == "__main__":
    sys.exit(main())

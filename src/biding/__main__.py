"""Entry point for ``python -m biding``.

Delegates to :func:`biding.main.main` and returns its exit code.
"""

import sys

from biding.main import main


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

# Entry point for `python -m biding ...`.
# Delegates entirely to main.main so all logic stays in main.py.

import sys
from biding.main import main

sys.exit(main(sys.argv[1:]))

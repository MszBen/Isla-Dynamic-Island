"""Double-click to start Isla without a console window."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from isla.__main__ import main  # noqa: E402

sys.exit(main())

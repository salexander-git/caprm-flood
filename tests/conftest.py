from __future__ import annotations

import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PYTHON_SOURCE_DIRECTORY = REPOSITORY_ROOT / "python"

sys.path.insert(0, str(PYTHON_SOURCE_DIRECTORY))
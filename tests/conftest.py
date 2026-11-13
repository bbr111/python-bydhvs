"""Make the helper modules in tests/ importable (e.g. `import frames`)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

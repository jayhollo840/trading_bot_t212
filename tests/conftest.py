import sys
from pathlib import Path

# Ensure project root is on sys.path so tests can import local modules.
SYS_ROOT = Path(__file__).resolve().parents[1]
if str(SYS_ROOT) not in sys.path:
    sys.path.insert(0, str(SYS_ROOT))

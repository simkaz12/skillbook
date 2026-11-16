import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS))
__path__.append(str(SCRIPTS / "test_baseline"))

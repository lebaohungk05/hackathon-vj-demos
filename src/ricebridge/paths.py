"""Single source of truth for every file-system location used by RiceBridge Ops.

The layout assumes a source checkout (``pip install -e .``): the repository root is
two levels above this package. Runtime-written files go to ``.cache/`` (git-ignored).
"""
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
ROOT = PACKAGE_DIR.parents[1]

WEB_DIR = PACKAGE_DIR / "web"

DATA_DIR = ROOT / "data"
FIXTURES_DIR = DATA_DIR / "fixtures"
LLM_CACHE_DIR = DATA_DIR / "llm_cache"
I18N_DIR = DATA_DIR / "i18n"
VISION_DATA_DIR = DATA_DIR / "vision"
TESTSET_DIR = VISION_DATA_DIR / "testset"
VISION_CACHE_DIR = VISION_DATA_DIR / "cache"

OUTPUTS_DIR = ROOT / "outputs"
SIM_OUT_DIR = OUTPUTS_DIR / "sim"
VISION_OUT_DIR = OUTPUTS_DIR / "vision"

RUNTIME_DIR = ROOT / ".cache"
UPLOAD_DIR = RUNTIME_DIR / "uploads"
LOG_PATH = RUNTIME_DIR / "server.log"

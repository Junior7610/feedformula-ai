from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

_temp_db_dir = tempfile.mkdtemp(prefix="feedformula_tests_")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_temp_db_dir}/test.db")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SKIP_DB_INIT", "1")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("AFRI_API_KEY", "")
os.environ.setdefault("FEDAPAY_SECRET_KEY", "")

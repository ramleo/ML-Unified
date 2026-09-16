import os
import sys

# ml-sql has no CI-run suite before this (OPEN_ISSUES E4). The guards it does
# have — the DuckDB file-access lock (E10) and the /sql/connect host check
# (E14) — were proven once by hand and had nothing to catch a regression.
#
# The guard modules import each other as `from .foo import ...` inside the
# `routers` package, so the service root must be on sys.path for
# `from routers._conn_guard import ...` to resolve the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

"""Stop two services silently testing each other's code.

Each service's `tests/conftest.py` puts its own directory on `sys.path`, so in
one interpreter the services' top-level module names all land in the same
namespace. Where two of them use the same name, only one can win, and the suite
collected second imports the other service's code.

That was not hypothetical. ml-api and ml-vision both had an `app.py` holding
their FastAPI application and a `shared/` package with a *different*
`progress.py` inside — 126 lines against 104. `pytest services/` reported seven
ml-vision failures that were nothing of the sort, and the four hundred that
passed alongside them had proved nothing, because some were asserting against
the wrong application. ml-vision's modules are now `vision_app` and
`vision_shared`, so there is no overlap left to hit.

This hook keeps it that way. It compares the real top-level names each
collected service would contribute and refuses only on an actual clash, naming
it — so a future `app.py` added to a third service fails here with a sentence
rather than as a week of strange test results.

`tests` is excluded: every service has one, pytest addresses them by file path,
and nothing imports the name.
"""
import os

import pytest

SERVICES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "services")
NOT_IMPORTED = {"tests", "__pycache__"}


def _service_of(path):
    parts = str(path).replace("\\", "/").split("/")
    if "services" in parts:
        i = parts.index("services")
        if i + 2 < len(parts) and parts[i + 2] == "tests":
            return parts[i + 1]
    return None


def _top_level_names(service):
    """What this service would add to sys.path's top level."""
    root = os.path.join(SERVICES_DIR, service)
    names = set()
    for entry in os.listdir(root):
        if entry in NOT_IMPORTED:
            continue
        full = os.path.join(root, entry)
        if entry.endswith(".py"):
            names.add(entry[:-3])
        elif os.path.isdir(full) and any(f.endswith(".py") for f in os.listdir(full)):
            names.add(entry)
    return names


def pytest_collection_modifyitems(session, config, items):
    services = sorted({s for s in (_service_of(i.fspath) for i in items) if s})
    if len(services) < 2:
        return

    seen, clashes = {}, {}
    for service in services:
        for name in _top_level_names(service):
            if name in seen:
                clashes.setdefault(name, {seen[name]}).add(service)
            else:
                seen[name] = service

    if clashes:
        detail = "; ".join(f"'{n}' in {' and '.join(sorted(s))}" for n, s in sorted(clashes.items()))
        raise pytest.UsageError(
            f"Refusing to collect {', '.join(services)} together: they share top-level "
            f"module names ({detail}), so whichever is imported second would get the "
            f"other's code. Rename one side, or run the suites separately:\n"
            + "\n".join(f"    pytest services/{s}/tests/" for s in services)
        )

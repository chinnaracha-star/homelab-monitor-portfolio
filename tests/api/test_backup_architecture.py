"""Backup domains stay separate.

These checks read imports. They do not run a backup or contact a NAS.
"""

import ast
from pathlib import Path

ROOT = Path("api/src/homelab_monitor")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_sqlite_backup_does_not_import_the_nas_connector() -> None:
    modules = _imports(ROOT / "sqlite_backup.py")
    assert "homelab_monitor.connectors.backup" not in modules
    assert "homelab_monitor.notifications.service" in modules


def test_nas_connector_does_not_import_sqlite_backup() -> None:
    modules = _imports(ROOT / "connectors" / "backup.py")
    assert "homelab_monitor.sqlite_backup" not in modules


def test_sqlite_backup_job_metadata_matches_the_factory() -> None:
    from homelab_monitor.jobs.engine import default_engine
    from homelab_monitor.jobs.validation import EXPECTED

    job = default_engine().describe("sqlite_backup")
    expected = EXPECTED["sqlite_backup"]
    assert job.name == "sqlite_backup"
    assert job.implementation == expected["implementation"]
    assert job.enabled == expected["enabled"]
    assert job.schedule == expected["schedule"]

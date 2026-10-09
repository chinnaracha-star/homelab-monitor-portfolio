"""Architecture checks for the frozen notification facade.

These tests read the service module. They do not send Telegram messages.
"""

import ast
from pathlib import Path

SERVICE = Path("api/src/homelab_monitor/notifications/service.py")


def _tree() -> ast.AST:
    return ast.parse(SERVICE.read_text(encoding="utf-8"))


def _imported_modules(tree: ast.AST) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_notification_service_imports_stay_on_the_facade() -> None:
    modules = _imported_modules(_tree())
    forbidden = {
        "homelab_monitor.photo_watcher",
        "homelab_monitor.notification_queue",
        "homelab_monitor.notification_worker",
        "homelab_monitor.notification_history",
        "homelab_monitor.notifications.dispatcher",
        "homelab_monitor.telegram_reports",
        "homelab_monitor.sqlite_backup",
    }
    assert modules.isdisjoint(forbidden)
    assert "homelab_monitor.telegram" in modules


def _is_loop_or_try(node: ast.AST) -> bool:
    return isinstance(node, ast.For | ast.While | ast.Try)


def test_notification_service_does_not_retry_or_catch_delivery() -> None:
    tree = _tree()
    methods = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name in {"send_text", "send_photo"}
    }
    assert set(methods) == {"send_text", "send_photo"}
    for method in methods.values():
        assert not any(_is_loop_or_try(child) for child in ast.walk(method))

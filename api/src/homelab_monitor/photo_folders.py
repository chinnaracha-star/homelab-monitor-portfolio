from pathlib import Path

DEFAULT_WATCH_FOLDERS = [
    "/data/photos",
    "/data/photos/library-a",
    "/data/photos/library-b",
    "/data/photos/library-c",
    "/data/photos/library-d",
    "/data/photos/library-e",
]

FOLDER_LABELS = {
    "/data/photos": "Photos",
    "/data/photos/library-a": "Library A",
    "/data/photos/library-b": "Library B",
    "/data/photos/library-c": "Library C",
    "/data/photos/library-d": "Library D",
    "/data/photos/library-e": "Library E",
}

_BASENAME_LABELS = {Path(path).name.lower(): label for path, label in FOLDER_LABELS.items()}


def display_folder_name(path: str) -> str:
    normalized = path.rstrip("/") or path
    if normalized in FOLDER_LABELS:
        return FOLDER_LABELS[normalized]
    base = Path(normalized).name
    if not base:
        return normalized
    return _BASENAME_LABELS.get(base.lower(), base)


def display_folder_names(paths: list[str]) -> list[str]:
    return [display_folder_name(path) for path in paths]


def matching_watch_root(folder: str, watch_roots: list[str]) -> str:
    normalized = folder.rstrip("/")
    for root in sorted(watch_roots, key=len, reverse=True):
        prefix = root.rstrip("/")
        if normalized == prefix or normalized.startswith(prefix + "/"):
            return root
    return folder


def inspect_watch_folder(path: str) -> str | None:
    root = Path(path)
    try:
        if not root.exists():
            return "Not found"
        if not root.is_dir():
            return "Not a directory"
        next(root.iterdir(), None)
    except PermissionError:
        return "Permission denied"
    except OSError as exc:
        return exc.strerror or str(exc)
    return None

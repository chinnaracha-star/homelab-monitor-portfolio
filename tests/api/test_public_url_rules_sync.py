import json
from pathlib import Path

from homelab_monitor.public_url_rules import load_public_url_rules, shared_public_url_rules_path
from homelab_monitor.telegram_url_validator import public_url_rejection_reason, validate_public_url

_CASES = Path(__file__).resolve().parents[2] / "shared" / "public-url-cases.json"


def test_shared_rules_file_is_the_source_of_truth() -> None:
    path = shared_public_url_rules_path()
    assert path.name == "public-url-rules.json"
    assert path.is_file()
    rules = load_public_url_rules()
    assert "http" in rules["schemes"]["allow"]
    assert "https" in rules["schemes"]["allow"]
    assert "dashboard" in rules["hosts"]["reject_exact"]
    assert ".internal" in rules["hosts"]["reject_suffixes"]
    assert rules["hosts"]["allow_exact"] == []
    assert rules["hosts"]["allow_wildcards"] == []
    assert "development" in rules["overrides"]
    assert "production" in rules["overrides"]


def test_backend_matches_shared_golden_cases() -> None:
    cases = json.loads(_CASES.read_text(encoding="utf-8"))
    for case in cases:
        url = case["url"]
        reason = public_url_rejection_reason(url)
        accepted = validate_public_url(url) is not None
        assert accepted is case["accept"], url
        assert reason == case["reason"], url

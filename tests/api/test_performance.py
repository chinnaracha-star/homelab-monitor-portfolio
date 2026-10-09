from homelab_monitor.performance import _performance_score, _reliability_score


def test_performance_and_reliability_scores() -> None:
    fast = {"api_ms": 20, "query_ms": 4, "backup_seconds": 1.2, "photo_scan_ms": 40}
    slow = {"api_ms": 400, "query_ms": 80}
    assert _performance_score(fast) == 100
    assert _performance_score(slow) < 80
    assert _reliability_score(fast) == 100
    assert _reliability_score({}) < 100

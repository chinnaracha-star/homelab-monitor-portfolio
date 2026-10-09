from homelab_monitor.schemas import RemoteAccessResponse
from homelab_monitor.settings import get_settings
from homelab_monitor.telegram_links import resolve_dashboard_url


def test_dashboard_url_prefers_public_then_tailnet(monkeypatch) -> None:
    settings = get_settings().model_copy(
        update={
            "dashboard_health_url": "http://dashboard:8080/",
            "dashboard_public_url": "https://dash.example/",
            "dashboard_port": 18081,
        }
    )
    assert resolve_dashboard_url(settings) == "https://dash.example"

    settings = get_settings().model_copy(
        update={"dashboard_health_url": "http://dashboard:8080/", "dashboard_public_url": ""}
    )
    monkeypatch.setattr(
        "homelab_monitor.telegram_links.RemoteAccessService.snapshot",
        lambda self: RemoteAccessResponse(
            hostname="monitor.example.com",
            https=True,
        ),
    )
    assert resolve_dashboard_url(settings) == "https://monitor.example.com"

    monkeypatch.setattr(
        "homelab_monitor.telegram_links.RemoteAccessService.snapshot",
        lambda self: RemoteAccessResponse(),
    )
    assert resolve_dashboard_url(settings) is None

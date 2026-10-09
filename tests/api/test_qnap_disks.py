import base64
from datetime import UTC, datetime, timedelta, timezone
from urllib.parse import parse_qs

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from homelab_monitor.alert_engine import AlertEngine, AlertEvent
from homelab_monitor.connectors.qnap import QnapConnector
from homelab_monitor.database import get_engine
from homelab_monitor.infrastructure import build_infrastructure_service
from homelab_monitor.models import Agent, Alert
from homelab_monitor.qnap_disks import (
    QNAP_DISK_ALERT_KIND,
    disks_from_payload,
    format_qnap_report_section,
    optional_celsius,
    qnap_disk_thresholds,
    sync_qnap_disk_alerts,
    temperature_status,
)
from homelab_monitor.security import hash_agent_token
from homelab_monitor.settings import Settings
from homelab_monitor.telegram import format_alert_message
from homelab_monitor.telegram_reports import format_hourly_report


def test_qnap_timeout_does_not_change_other_connectors() -> None:
    settings = Settings(
        registration_key="test-registration-key-at-least-24-chars",
        infrastructure_timeout_seconds=2,
        qnap_timeout_seconds=10,
        qnap_tls_verify=False,
    )
    service = build_infrastructure_service(settings)
    qnap = service._connectors["qnap"]
    docker = service._connectors["docker"]
    assert qnap.timeout == 10
    assert qnap.tls_verify is False
    assert docker.timeout == 2
    qnap._client.close()


def test_qnap_tls_verify_defaults_on_and_can_be_disabled(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    seen: list[bool] = []
    real_client = httpx.Client

    def factory(*args: object, **kwargs: object) -> httpx.Client:
        seen.append(bool(kwargs.get("verify", True)))
        return real_client(*args, **kwargs)  # type: ignore[arg-type]

    injected = httpx.Client()
    monkeypatch.setattr("homelab_monitor.connectors.qnap.httpx.Client", factory)
    secure = QnapConnector(mock=True)
    insecure = QnapConnector(mock=True, tls_verify=False)
    explicit = QnapConnector(mock=True, tls_verify=False, client=injected)
    assert seen == [True, False]
    assert explicit._client is injected
    assert secure.tls_verify is True
    assert insecure.tls_verify is False
    secure._client.close()
    insecure._client.close()
    injected.close()


def test_missing_storage_fields_are_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "manaRequest.cgi" in request.url.path:
            return httpx.Response(
                200,
                json={"hostname": "Chin-HomeNas", "online": True, "sys_tempc": 35, "cpu_tempc": 43},
            )
        return httpx.Response(200, json={"datas": []})

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=2)
    snapshot = QnapConnector(
        mock=False, base_url="https://qnap.example", api_key="sid", client=client
    ).collect()
    assert snapshot.summary["storage_percent"] is None
    assert snapshot.summary["model"] == ""
    assert snapshot.summary["storage_health"] == "unknown"


def test_optional_celsius_does_not_use_zero_for_missing() -> None:
    assert optional_celsius(None) is None
    assert optional_celsius("") is None
    assert optional_celsius("hot") is None
    assert optional_celsius(0) == 0
    assert optional_celsius("47") == 47


def test_qnap_live_temperature_missing_is_null() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "manaRequest.cgi" in str(request.url):
            return httpx.Response(
                200, json={"hostname": "qnap-lab-01", "model": "TS-453Be", "online": True}
            )
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=2)
    snapshot = QnapConnector(
        mock=False, base_url="https://qnap.example", api_key="sid", client=client
    ).collect()
    assert snapshot.summary["temperature_celsius"] is None
    assert "disks" not in snapshot.summary
    assert snapshot.summary["model"] == "TS-453Be"
    assert "sid" not in str(snapshot.summary)


def test_qnap_login_uses_base64_password_and_reads_cdata_sid() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        if "authLogin.cgi" in request.url.path:
            params = parse_qs(request.url.query.decode())
            seen["user"] = params["user"][0]
            seen["pwd"] = params["pwd"][0]
            seen["serviceKey"] = params["serviceKey"][0]
            seen["client_app"] = params["client_app"][0]
            assert request.url.query.decode().find("plain-secret") == -1
            return httpx.Response(
                200,
                text="<QDocRoot><authPassed><![CDATA[1]]></authPassed>"
                "<authSid><![CDATA[live-sid]]></authSid></QDocRoot>",
            )
        if "manaRequest.cgi" in request.url.path:
            assert "live-sid" in request.url.query.decode()
            return httpx.Response(
                200, json={"hostname": "nas", "model": "TS-453Be", "online": True}
            )
        return httpx.Response(200, json={"datas": []})

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=2)
    snapshot = QnapConnector(
        mock=False,
        base_url="https://qnap.example",
        username="chinnarach",
        password="plain-secret",
        client=client,
    ).collect()
    assert seen["pwd"] == base64.b64encode(b"plain-secret").decode("ascii")
    assert seen["serviceKey"] == "1"
    assert seen["client_app"] == "Web Desktop"
    assert snapshot.summary["hostname"] == "nas"
    rendered = str(snapshot.summary)
    assert "plain-secret" not in rendered
    assert "live-sid" not in rendered


def test_qnap_auth_failure_hides_secrets() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "authLogin.cgi" in request.url.path:
            return httpx.Response(
                200,
                text="<QDocRoot><authPassed>0</authPassed><authSid><![CDATA[should-not-use]]></authSid></QDocRoot>",
            )
        raise AssertionError("sysinfo must not run after auth failure")

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=2)
    snapshot = QnapConnector(
        mock=False,
        base_url="https://qnap.example",
        username="chinnarach",
        password="plain-secret",
        client=client,
    ).collect()
    assert snapshot.status == "unhealthy"
    assert snapshot.summary["error"] == "qnap_auth_failed"
    assert "plain-secret" not in str(snapshot.summary)
    assert "should-not-use" not in str(snapshot.summary)


def test_qnap_sysinfo_http_failure_is_safe() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "authLogin.cgi" in request.url.path:
            return httpx.Response(
                200,
                text="<QDocRoot><authPassed>1</authPassed><authSid><![CDATA[live-sid]]></authSid></QDocRoot>",
            )
        if "manaRequest.cgi" in request.url.path:
            return httpx.Response(500, text="sid=live-sid")
        raise AssertionError(request.url.path)

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=2)
    snapshot = QnapConnector(
        mock=False,
        base_url="https://qnap.example",
        username="chinnarach",
        password="plain-secret",
        client=client,
    ).collect()
    assert snapshot.summary["error"] == "qnap_sysinfo_failed"
    rendered = str(snapshot.summary)
    assert "plain-secret" not in rendered
    assert "live-sid" not in rendered


def test_configured_sid_skips_login() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "authLogin.cgi" not in request.url.path
        if "manaRequest.cgi" in request.url.path:
            return httpx.Response(
                200, json={"hostname": "nas", "online": True, "model": "TS-453Be"}
            )
        return httpx.Response(200, json={"datas": []})

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=2)
    snapshot = QnapConnector(
        mock=False,
        base_url="https://qnap.example",
        username="chinnarach",
        password="plain-secret",
        api_key="configured-sid",
        client=client,
    ).collect()
    assert snapshot.summary["hostname"] == "nas"
    assert "configured-sid" not in str(snapshot.summary)
    assert "plain-secret" not in str(snapshot.summary)


def _verified_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "disk_num": "4",
        "hdd_disk_num": "4",
        "HDTempWarnT": "55",
        "HDTempErrT": "60",
        "disk_installed1": "1",
        "tempc1": "42",
        "temp_alert1": "0",
        "hd_is_ssd1": "0",
        "hd_pd_alias1": '3.5" SATA HDD 1',
        "disk_installed2": "1",
        "tempc2": "42",
        "temp_alert2": "0",
        "hd_is_ssd2": "0",
        "hd_pd_alias2": '3.5" SATA HDD 2',
        "disk_installed3": "1",
        "tempc3": "35",
        "disk_installed4": "1",
        "tempc4": "36",
    }
    payload.update(overrides)
    return payload


def test_indexed_sysinfo_discovers_installed_disks_only() -> None:
    disks = disks_from_payload(
        _verified_payload(
            disk_installed5="0", tempc5="70", disk_installed6="1", tempc6="nope", hd_is_ssd6="1"
        )
    )
    assert disks is not None
    assert [disk["bay"] for disk in disks] == [1, 2, 3, 4, 6]
    assert disks[0]["temperature_celsius"] == 42
    assert disks[0]["temperature_status"] == "normal"
    assert disks[0]["alias"] == '3.5" SATA HDD 1'
    assert disks[0]["is_ssd"] is False
    assert disks[0]["manufacturer"] is None
    assert disks[0]["model"] is None
    assert disks[0]["smart_status"] is None
    assert disks[0]["capacity_bytes"] is None
    assert disks[-1]["temperature_celsius"] is None
    assert disks[-1]["temperature_status"] == "unknown"
    assert disks[-1]["is_ssd"] is True
    assert disks_from_payload({"hostname": "nas"}) is None


def test_temperature_bands_use_qnap_thresholds() -> None:
    assert qnap_disk_thresholds({"HDTempWarnT": "55", "HDTempErrT": "60"}) == (55, 60)
    assert qnap_disk_thresholds({}) == (55, 60)
    assert qnap_disk_thresholds({"HDTempWarnT": "70", "HDTempErrT": "60"}) == (55, 60)
    assert temperature_status(42, 55, 60) == "normal"
    assert temperature_status(54, 55, 60) == "normal"
    assert temperature_status(55, 55, 60) == "warning"
    assert temperature_status(59, 55, 60) == "warning"
    assert temperature_status(60, 55, 60) == "critical"
    assert temperature_status(None, 55, 60) == "unknown"
    assert "0°C" not in format_qnap_report_section(
        {"online": True, "disks": disks_from_payload(_verified_payload(tempc2=""))}
    )


def test_qnap_offline_and_missing_disks_do_not_break_hourly_report() -> None:
    offline = format_qnap_report_section({"online": False, "hostname": "qnap-lab-01"})
    assert "Offline" in offline
    assert "unavailable" in offline
    missing = format_qnap_report_section(
        {"online": True, "hostname": "qnap-lab-01", "temperature_celsius": None}
    )
    assert "Online" in missing
    assert "Disk Temperature: unavailable" in missing
    assert "0°C" not in missing
    body = format_hourly_report(
        local=datetime(2026, 9, 10, 14, 0, tzinfo=timezone(timedelta(hours=7))),
        cpu=57.0,
        memory=32.0,
        temperature=51.0,
        storage_percent=1.0,
        photos_new_today="9",
        immich_indexed="18,421",
        backup_status="Success",
        last_backup="",
        active_alerts=0,
        recovered_today=2,
        health_score=84.0,
        recommendation="Everything looks healthy.",
        dashboard_url="http://127.0.0.1:18081",
    )
    assert "🖥 CPU" in body
    assert "💾 QNAP Storage" in body
    assert "Hourly Executive Report" in body


def test_hourly_section_lists_disks_and_truncates() -> None:
    disks = [
        {
            "bay": index,
            "alias": f"HDD {index}",
            "is_ssd": False,
            "temperature_celsius": 39,
            "temperature_status": "normal",
            "smart_status": None,
        }
        for index in range(1, 90)
    ]
    section = format_qnap_report_section(
        {
            "online": True,
            "hostname": "qnap-lab-01",
            "storage_percent": 41.5,
            "temperature_celsius": 42,
            "disks": disks,
        }
    )
    assert "HDD 1" in section
    assert "more disks" in section
    assert len(section) < 2000
    report = format_hourly_report(
        local=datetime(2026, 9, 27, 16, 0, tzinfo=timezone(timedelta(hours=7))),
        cpu=1,
        memory=1,
        temperature=40,
        storage_percent=10,
        photos_new_today="0",
        immich_indexed="1",
        backup_status="Success",
        last_backup="",
        active_alerts=0,
        recovered_today=0,
        health_score=90,
        recommendation="ok",
        dashboard_url="http://127.0.0.1",
        qnap_section=section,
    )
    assert "💾 QNAP Storage" in report
    assert "📷 Photos Today" in report


def test_hdd_alerts_are_per_bay_and_do_not_use_agent_temperature(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        "homelab_monitor.alert_engine.AlertEngine._enqueue_notifications",
        staticmethod(lambda events: None),
    )
    observed = datetime.now(UTC)
    summary = {
        "hostname": "qnap-disk-host",
        "online": True,
        "disk_temp_warning_c": 55,
        "disk_temp_critical_c": 60,
        "disks": [
            {
                "bay": 1,
                "alias": '3.5" SATA HDD 1',
                "temperature_celsius": 55,
                "temperature_status": "warning",
                "warning_c": 55,
                "critical_c": 60,
                "smart_status": None,
            },
            {
                "bay": 2,
                "temperature_celsius": 60,
                "temperature_status": "critical",
                "warning_c": 55,
                "critical_c": 60,
                "smart_status": None,
            },
            {
                "bay": 3,
                "temperature_celsius": None,
                "temperature_status": "unknown",
                "smart_status": None,
            },
        ],
    }
    with Session(get_engine()) as db:
        agent = Agent(
            name="qnap-disk-host",
            hostname="qnap-disk-host.local",
            version="0.1.0",
            token_hash=hash_agent_token("qnap-disk-host-token"),
            status="online",
            capabilities=["ubuntu"],
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        engine = AlertEngine(
            Settings(
                registration_key="test-registration-key-at-least-24-chars",
                alert_temperature_threshold_celsius=80,
            )
        )
        engine.evaluate_report(
            db,
            agent,
            {
                "modules": [
                    {
                        "module": "system",
                        "status": "ok",
                        "summary": "ok",
                        "metrics": {
                            "cpu": {"usage_percent": 10},
                            "memory": {"usage_percent": 10},
                            "disks": [{"mount_point": "/", "usage_percent": 10}],
                            "temperatures": [
                                {
                                    "source": "coretemp",
                                    "label": "Package",
                                    "current_celsius": 47,
                                }
                            ],
                        },
                        "diagnostics": {},
                    }
                ]
            },
            observed,
        )
        db.commit()
        agent_alerts = db.scalars(select(Alert).where(Alert.agent_id == agent.id)).all()
        assert all(item.kind != QNAP_DISK_ALERT_KIND for item in agent_alerts)
        assert any(item.kind == "temperature_high" for item in agent_alerts) is False

    sync_qnap_disk_alerts(summary)
    sync_qnap_disk_alerts(summary)
    with Session(get_engine()) as db:
        rows = db.scalars(select(Alert).where(Alert.kind == QNAP_DISK_ALERT_KIND)).all()
        resources = sorted(item.resource for item in rows)
        assert resources == ["qnap:qnap-disk-host:bay:1", "qnap:qnap-disk-host:bay:2"]
        assert len(rows) == 2
        warning = next(item for item in rows if item.resource.endswith("bay:1"))
        assert warning.message
        assert "secret" not in warning.message
        assert "55°C" in warning.message
        assert "SMART" not in warning.message
        formatted = format_alert_message(
            AlertEvent(
                agent_id="x",
                agent_name="qnap-disk-host",
                kind=QNAP_DISK_ALERT_KIND,
                resource=warning.resource,
                value=47,
                threshold=45,
                message=warning.message,
                observed_at=observed,
            )
        )
        assert formatted == warning.message

    summary["disks"][0]["temperature_celsius"] = 42
    summary["disks"][0]["temperature_status"] = "normal"
    sync_qnap_disk_alerts(summary)
    with Session(get_engine()) as db:
        recovered = db.scalar(
            select(Alert).where(
                Alert.kind == QNAP_DISK_ALERT_KIND, Alert.resource == "qnap:qnap-disk-host:bay:1"
            )
        )
        assert recovered is not None
        assert recovered.status == "resolved"

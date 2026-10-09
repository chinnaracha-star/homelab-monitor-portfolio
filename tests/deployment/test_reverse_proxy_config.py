from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NGINX_CONFIGS = (
    ROOT / "deploy" / "nginx" / "nginx.conf",
    ROOT / "deploy" / "nginx" / "homelab-monitor.conf",
)


@pytest.mark.parametrize("config_path", NGINX_CONFIGS)
def test_nginx_configs_keep_api_and_websocket_routes(config_path: Path) -> None:
    config = config_path.read_text(encoding="utf-8")
    rest_location = config.split("location /api/ {", maxsplit=1)[1].split("}", maxsplit=1)[0]
    websocket_location = config.split("location ^~ /api/v1/ws/ {", maxsplit=1)[1].split(
        "}", maxsplit=1
    )[0]

    assert "location = /health {" in config
    assert "location = /openapi.json {" in config
    assert "location /docs {" in config
    assert 'proxy_set_header Connection "";' in rest_location
    assert "proxy_set_header Upgrade" not in rest_location
    assert "proxy_set_header Upgrade $http_upgrade;" in websocket_location
    assert "proxy_set_header Connection $connection_upgrade;" in websocket_location
    assert "proxy_socket_keepalive on;" in websocket_location
    assert "proxy_set_header X-Forwarded-Proto $proxy_x_forwarded_proto;" in config


@pytest.mark.parametrize("config_path", NGINX_CONFIGS)
def test_nginx_configs_set_security_and_pwa_cache_headers(config_path: Path) -> None:
    config = config_path.read_text(encoding="utf-8")

    assert "add_header Content-Security-Policy" in config
    assert 'add_header X-Content-Type-Options "nosniff" always;' in config
    assert 'add_header X-Frame-Options "DENY" always;' in config
    assert 'add_header Referrer-Policy "strict-origin-when-cross-origin" always;' in config
    assert "application/manifest+json" in config
    assert "service-worker\\.js" in config
    assert 'Cache-Control "public, max-age=31536000, immutable"' in config
    assert 'Cache-Control "no-cache, no-store, must-revalidate"' in config


def test_compose_keeps_dashboard_loopback_only_and_api_internal() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    production = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")

    assert '"127.0.0.1:${HOMELAB_DASHBOARD_PORT:-8080}:8080"' in compose
    assert '"127.0.0.1:80:8080"' in production
    assert "networks:\n  backend:\n  egress:\n" in compose
    assert "internal: true" not in compose
    assert "api:\n" in compose
    assert "      - backend\n      - egress" in compose
    assert "dashboard:\n" in compose
    assert compose.count("      - backend") == 2


def test_full_nginx_configs_preserve_tailnet_https_scheme() -> None:
    for config_name in ("nginx.conf", "nginx.host.conf"):
        config = (ROOT / "deploy" / "nginx" / config_name).read_text(encoding="utf-8")
        assert "map $http_x_forwarded_proto $proxy_x_forwarded_proto" in config
        assert "https https;" in config

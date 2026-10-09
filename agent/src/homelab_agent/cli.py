import argparse
import json
import signal
import sys
from pathlib import Path
from types import FrameType

from homelab_agent.buffer import ReportBuffer
from homelab_agent.collectors.system import SystemCollector
from homelab_agent.config import AgentSettings
from homelab_agent.logging import configure_logging
from homelab_agent.service import AgentService
from homelab_agent.transport import AgentTransport


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="homelab-agent",
        description="Collect Ubuntu health metrics for HomeLab Monitor",
    )
    parser.add_argument(
        "--env-file",
        default=None,
        help="Optional environment file (systemd normally supplies EnvironmentFile)",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("run", help="Run the scheduled collection agent")
    subcommands.add_parser("collect", help="Collect and print one system snapshot")
    return parser


def load_settings(env_file: str | None) -> AgentSettings:
    if env_file:
        return AgentSettings(_env_file=Path(env_file))  # type: ignore[call-arg]
    return AgentSettings()


def main() -> int:
    args = build_parser().parse_args()
    settings = load_settings(args.env_file)
    configure_logging(settings.log_level)

    if args.command == "collect":
        result = SystemCollector(settings).collect()
        print(json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True))
        return 0

    try:
        transport = AgentTransport(settings)
    except ValueError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2

    buffer = ReportBuffer(settings.buffer_path, settings.buffer_max_reports)
    service = AgentService(settings, transport, buffer, SystemCollector(settings))

    def stop_service(_signum: int, _frame: FrameType | None) -> None:
        service.stop()

    signal.signal(signal.SIGINT, stop_service)
    signal.signal(signal.SIGTERM, stop_service)
    service.run()
    return 0

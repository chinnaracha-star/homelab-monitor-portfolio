# Security policy

## Supported versions

HomeLab Monitor Toolkit is in early development and has not reached a supported
production release. Security fixes currently target the latest development
version.

## Reporting a vulnerability

Do not open a public issue containing credentials, private hostnames, API tokens,
or exploit details. Use GitHub private vulnerability reporting when available,
or contact the maintainer privately through the repository profile.

Include the affected version, reproduction steps, impact, and any suggested
mitigation. Sanitise logs and configuration before attaching them.

## Version 1 security boundary

Version 1 targets trusted HomeLab LAN deployments behind HTTPS termination. It
uses separate credentials for agents and the dashboard. It is not designed for
direct exposure to the public internet, multi-tenant use, or untrusted agents.

# Multi-agent platform

The agent protocol is unchanged. Agents still register and report as before.
HomeLab Monitor already identified hosts such as `monitor`. Additional
Ubuntu, Windows, Raspberry Pi, and NAS agents can use the same Agent API.

## Groups, labels, and tags

- **Groups** remain the existing many-to-many `agent_groups` model
  (`docs/groups.md`).
- **Labels** on the Agents page are the agent's existing group names.
- **Tags** are derived in the dashboard from hostname, name, and OS
  (`ubuntu`, `windows`, `raspberry-pi`, `nas`). They are not a new agent
  payload and are not added to `GET /api/v1/agents` (that response stays
  the original six fields).

## Dashboard

The existing Agents page adds Overall Fleet Health (online / total × 100),
Online Summary, Offline Summary, and table columns for groups, labels, and
tags. Search already filters by name and hostname and now also matches labels
and tags. Status filters (All / Online / Offline / Warning) and the group
dropdown are unchanged.

## Fleet health

Fleet score is operational only: it does not replace Production Health score.
Offline counts use the existing presence timeout (`HOMELAB_AGENT_OFFLINE_AFTER_SECONDS`).

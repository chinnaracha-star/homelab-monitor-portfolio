# Agent groups

Groups organize registered agents without changing agent identity, tokens, or
reporting. Membership is many-to-many: one agent can belong to several groups,
and deleting a group does not delete agents.

## Model

Alembic revision `0005_add_agent_groups` adds:

- `agent_groups`: `id`, unique `name`, `description`, timestamps
- `agent_group_members`: `group_id`, `agent_id`, `assigned_at`, unique pair

Group names must match `^[a-zA-Z0-9][a-zA-Z0-9 ._-]*$`.

## APIs

All group routes require a dashboard JWT. Existing agent and dashboard routes
are unchanged.

| Method | Path | Roles |
| --- | --- | --- |
| `GET` | `/api/v1/groups` | admin, operator, viewer |
| `GET` | `/api/v1/groups/summary` | admin, operator, viewer |
| `GET` | `/api/v1/groups/{group_id}` | admin, operator, viewer |
| `POST` | `/api/v1/groups` | admin, operator |
| `PUT` | `/api/v1/groups/{group_id}` | admin, operator |
| `DELETE` | `/api/v1/groups/{group_id}` | admin, operator |
| `POST` | `/api/v1/groups/{group_id}/agents` | admin, operator |
| `DELETE` | `/api/v1/groups/{group_id}/agents/{agent_id}` | admin, operator |

Assign body:

```json
{ "agent_ids": ["agent-uuid"] }
```

Unknown agent IDs return `agent_not_found` with `details.agent_ids`. Duplicate
IDs in one request are ignored. Assigning an agent that is already a member is
idempotent.

Error codes:

- `group_not_found`
- `group_name_exists`
- `agent_not_found`
- `group_member_not_found`
- `permission_denied`

`GET /api/v1/dashboard/overview` remains the same object plus:

- `groups.total`
- `group_stats[]` with `id`, `name`, `agents`, `online`

Existing `agents` and `reports` fields are unchanged.

## Realtime

Group create, update, delete, assign, and remove publish the existing WebSocket
events `overview_updated` and `agent_updated` with `reason=group_updated`. No
new event type is introduced. History APIs are untouched.

## Dashboard

- Groups lists group cards and, for admins and operators, create plus bulk
  assign.
- Group detail shows members, edit, delete, assign, and remove.
- Agents can be filtered by group.
- Overview shows Total Groups and per-group agent/online cards.

Viewers can open Groups and filter; they cannot mutate membership.

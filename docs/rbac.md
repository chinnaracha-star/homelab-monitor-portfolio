# Role-based access control

HomeLab Monitor authorizes dashboard users by role after JWT authentication.
Agents are unchanged: they still use registration keys and hashed agent tokens.

Authorization lives in one FastAPI dependency, `require_roles(...)`. Endpoints do
not contain inline role checks.

## Roles

| Role | Access |
| --- | --- |
| `admin` | Full dashboard, alerts, alert rules, groups, notifications, user management, and system settings. |
| `operator` | Dashboard, agents, reports, alerts, alert acknowledgement, groups, notification tests/retries, and read-only alert rules. Cannot manage users, settings, or alert rules. |
| `viewer` | Read-only dashboard, agents, reports, alerts, alert rules, groups, infrastructure, photo services, and notification history. No POST, PUT, PATCH, or DELETE. |

## Backend

Protect a router or endpoint with the shared dependency:

```python
dependencies = [Depends(require_roles("admin", "operator", "viewer"))]
dependencies = [Depends(require_roles("admin", "operator"))]
dependencies = [Depends(require_roles("admin"))]
```

A caller whose role is not listed receives HTTP 403:

```json
{
  "error": {
    "code": "permission_denied",
    "message": "You do not have permission to access this resource"
  }
}
```

The standard error envelope also includes `details` and `request_id`.

Current assignments:

- `GET /api/v1/dashboard/*`, `GET /api/v1/agents/*`, `GET /api/v1/alerts/*`,
  `GET /api/v1/groups`, `GET /api/v1/groups/summary`, `GET /api/v1/groups/{group_id}`:
  admin, operator, viewer
- `POST /api/v1/alerts/{alert_id}/acknowledge`: admin, operator
- `POST /api/v1/groups`, `PUT /api/v1/groups/{group_id}`,
  `DELETE /api/v1/groups/{group_id}`, `POST /api/v1/groups/{group_id}/agents`,
  `DELETE /api/v1/groups/{group_id}/agents/{agent_id}`: admin, operator
- `GET /api/v1/notifications`, `GET /api/v1/notifications/{notification_id}`,
  `GET /api/v1/settings/notifications`: admin, operator, viewer
- `POST /api/v1/notifications/test`, `POST /api/v1/notifications/{notification_id}/retry`:
  admin, operator
- `PUT /api/v1/settings/notifications`: admin
- `GET /api/v1/alert-rules`, `GET /api/v1/alert-rules/{rule_id}`: admin, operator, viewer
- `POST /api/v1/alert-rules`, `PUT /api/v1/alert-rules/{rule_id}`,
  `PATCH /api/v1/alert-rules/{rule_id}/enable`,
  `DELETE /api/v1/alert-rules/{rule_id}`: admin
- `GET /api/v1/infrastructure`, `GET /api/v1/infrastructure/{service}`,
  `GET /api/v1/photo-services`, `GET /api/v1/photos`, `GET /api/v1/photos/latest`,
  `GET /api/v1/photos/stats`, `GET /api/v1/photos/settings`, `GET /api/v1/backup`:
  admin, operator, viewer
- `PUT /api/v1/photos/settings`: admin
- `GET /api/v1/users`: admin
- `POST /api/v1/users`, `PUT /api/v1/users/{user_id}`,
  `PATCH /api/v1/users/{user_id}/password`,
  `PATCH /api/v1/users/{user_id}/status`, `DELETE /api/v1/users/{user_id}`: admin
- `GET /api/v1/auth/me`: any authenticated dashboard user

JWT claims remain `sub`, `uid`, and `role`. Role checks still load the user from
the database so a disabled account cannot keep access from an old token.

## Frontend

The dashboard reads the current user from `GET /api/v1/auth/me` and stores it in
auth context. Navigation and route gates call one helper:

```ts
can(role, "users")
can(role, "settings")
can(role, "groups")
can(role, "manage_groups")
can(role, "alerts")
can(role, "alert_rules")
can(role, "manage_alert_rules")
can(role, "infrastructure")
can(role, "photo_services")
can(role, "backup")
```

Components use `useCan()` instead of comparing role strings. Viewers do not see
Users or Settings. Operators do not see Users or Settings. Admins see every
item. Opening a hidden route shows a 403 Permission denied page.

## Security notes

- Treat RBAC as server-enforced. Hiding a menu item is not authorization.
- Replace the seeded default passwords before exposing the dashboard.
- Future settings mutation endpoints should reuse `require_roles`
  rather than adding per-handler conditionals.

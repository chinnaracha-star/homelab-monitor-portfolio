# Authentication

HomeLab Monitor uses separate credentials for agents and dashboard users.

Agents continue to authenticate with a one-time hashed bearer token issued at
registration. Dashboard users authenticate with a username, password, and a
short-lived JWT access token.

## Roles

| Role | Purpose |
| --- | --- |
| `admin` | Full dashboard operator. Seeded by default in development. |
| `operator` | Day-to-day monitoring access, including alert acknowledgement. |
| `viewer` | Read-only dashboard access. |

Role checks are enforced by `require_roles(...)`. See [rbac.md](rbac.md) and
[user-management.md](user-management.md).

## Login flow

1. Submit `POST /api/v1/auth/login` with a JSON username and password.
2. The API verifies the bcrypt password hash and returns a JWT.
3. The dashboard stores the token in `localStorage`.
4. Subsequent dashboard API calls send `Authorization: Bearer <token>`.
5. `GET /api/v1/auth/me` returns the current user for the navbar.
6. Logout deletes the stored token and returns to `/login`.

Accounts are created from environment variables at API start, not from hardcoded
passwords. Production requires `HOMELAB_BOOTSTRAP_ADMIN_PASSWORD` (minimum 8
characters, and not `admin123`). Optional `HOMELAB_BOOTSTRAP_OPERATOR_PASSWORD`
and `HOMELAB_BOOTSTRAP_VIEWER_PASSWORD` create those roles when set. Existing
usernames are never overwritten unless they still use a known insecure default
and a bootstrap password is provided.

## JWT

Tokens are signed with HS256 using `HOMELAB_JWT_SECRET`. Expiry is controlled by
`HOMELAB_JWT_EXPIRE_MINUTES`. Expired or malformed tokens return HTTP 401.
Inactive users return HTTP 403.

## Protected APIs

These routes require a dashboard JWT:

- `GET /api/v1/dashboard/*`
- `GET /api/v1/agents`
- `GET /api/v1/agents/{agent_id}`
- `GET /api/v1/agents/{agent_id}/latest-report`
- `GET /api/v1/agents/{agent_id}/reports`
- `GET /api/v1/history/agents/{agent_id}`
- `GET /api/v1/history/agents/{agent_id}/export`
- `GET /api/v1/alerts/*`
- `POST /api/v1/alerts/{alert_id}/acknowledge` (admin, operator)
- `GET /api/v1/groups`, `GET /api/v1/groups/summary`, `GET /api/v1/groups/{group_id}`
- `POST /api/v1/groups`, `PUT /api/v1/groups/{group_id}`,
  `DELETE /api/v1/groups/{group_id}`, `POST /api/v1/groups/{group_id}/agents`,
  `DELETE /api/v1/groups/{group_id}/agents/{agent_id}` (admin, operator)
- `GET /api/v1/users` (admin)
- `POST /api/v1/users` (admin)
- `PUT /api/v1/users/{user_id}` (admin)
- `PATCH /api/v1/users/{user_id}/password` (admin)
- `PATCH /api/v1/users/{user_id}/status` (admin)
- `DELETE /api/v1/users/{user_id}` (admin)
- `GET /api/v1/auth/me`

- `GET /api/v1/notifications`
- `GET /api/v1/notifications/{notification_id}`
- `POST /api/v1/notifications/test` (admin, operator)
- `POST /api/v1/notifications/{notification_id}/retry` (admin, operator)
- `GET /api/v1/settings/notifications`
- `PUT /api/v1/settings/notifications` (admin)

These routes remain available without a dashboard JWT:

- `GET /health`
- `POST /api/v1/auth/login`
- `POST /api/v1/agents/register` (registration key)
- `POST /api/v1/agent/check-ins` (agent token)
- `POST /api/v1/agent/reports` (agent token)

## Security notes

- Passwords are hashed with bcrypt through passlib. Plain passwords are never stored.
- Do not commit `HOMELAB_JWT_SECRET` or production passwords.
- Replace the seeded default passwords before exposing the dashboard beyond a
  trusted HomeLab network.
- The dashboard JWT is stored in `localStorage` in v1. Treat the browser as a
  trusted operator workstation.

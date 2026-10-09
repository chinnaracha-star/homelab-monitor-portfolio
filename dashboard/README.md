# HomeLab Monitor Dashboard

Read-only React dashboard for the HomeLab Monitor API. Navigation and
administration pages follow role-based access control. Administrators can
manage dashboard users from `/users`. See
[user management](../docs/user-management.md).

## Local development

```bash
cp .env.example .env.local
npm install
npm run dev
```

The API server must be running and accessible from the browser. Agent Detail
includes history charts for CPU, memory, disk, and temperature.

## Configuration

Set the API v1 base URL in `.env.local`. The optional proxy target lets the Vite
development server reach the local API without requiring backend CORS changes:

```env
VITE_API_BASE_URL=/api/v1
VITE_API_PROXY_TARGET=http://127.0.0.1:8000
```

For production, keep the relative base URL and route `/api` to the backend with
the deployment reverse proxy. The Vite `/api` proxy enables WebSocket upgrades
for `GET /api/v1/ws/dashboard`.

## Quality checks

```bash
npm run lint
npm run test
npm run build
```

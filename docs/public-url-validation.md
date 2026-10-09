# Public URL validation

Telegram buttons, Settings live checks, and preview badges all use **one** rule
file. Backend Python and Frontend TypeScript never keep their own host lists.

## Where rules live

`shared/public-url-rules.json` is the source of truth.

Golden cases that both runtimes must agree on live in
`shared/public-url-cases.json`.

| Consumer | Loader |
| --- | --- |
| API | `homelab_monitor.public_url_rules.load_public_url_rules()` then `validate_public_url()` |
| Dashboard | `dashboard/src/settings/publicUrl.ts` imports the same JSON |

Docker copies `shared/` into the API image (`/app/shared`) and the dashboard
build (`/shared`). The Python wheel also force-includes the JSON next to the
package for installs that do not keep the repo tree.

## How a URL is decided

1. Empty → omit (reason `empty`).
2. Scheme must be in `schemes.allow` (`http`, `https`). Other schemes (`ftp`,
   `file`, `ws`, `wss`) fail as `missing_http_scheme`.
3. If the host matches `allow_exact`, `allow_suffixes`, or `allow_wildcards`, it
   is accepted even if a reject rule would otherwise match.
4. Otherwise apply `reject_exact`, `reject_prefixes`, `reject_suffixes`, then
   `reject_single_label` (Docker-style names without a dot).

Loopback names (`localhost`, `127.0.0.1`, `0.0.0.0`) map to reason `loopback`.
Compose service names map to `internal_docker_host`. Suffixes such as `.local`
and `.internal` map to `private_only_tld`.

## How to add a rule

Edit **only** `shared/public-url-rules.json`.

- Block another Compose hostname: add it to `hosts.reject_exact`.
- Block a TLD: add a suffix like `.lan` to `hosts.reject_suffixes`.
- Allow an org domain later: put `example.com` in `hosts.allow_suffixes` (leading
  dot) or a pattern in `hosts.allow_wildcards` (`*.corp.example`).
- Environment-specific extras: put host list merges under
  `overrides.development` or `overrides.production`. The API merges those lists
  using `HOMELAB_ENVIRONMENT`. Empty override objects change nothing.

Add a row to `shared/public-url-cases.json` for every new behavior, then run
backend and frontend tests. Do not copy the host list into Python or TypeScript.

## How Backend and Frontend stay synchronized

Both sides load the JSON and apply the same match order. Regression tests walk
`public-url-cases.json`:

- `tests/api/test_public_url_rules_sync.py`
- `dashboard/src/settings/publicUrl.shared.test.ts`

If those suites pass, Backend == Frontend for every golden URL.

## Future extension (no matcher rewrite)

The file already has empty `allow_exact`, `allow_suffixes`, `allow_wildcards`,
and `overrides`. Filling those arrays is enough for a host whitelist,
organization domains, wildcard allow rules, and environment-specific overrides.

## What this does not change

Telegram delivery, NotificationService, retry, scheduler, REST payloads, and
SQLite schema are unchanged. Validation ownership moved; message sending did not.

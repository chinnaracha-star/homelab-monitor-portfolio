# Contributing

HomeLab Monitor Toolkit is currently building its version 1 foundation.
Contributions should remain within the published version scope and preserve the
agent-server trust boundary.

## Development workflow

1. Create a focused branch.
2. Install the project with `python -m pip install -e ".[dev]"`.
3. Add or update tests for every behaviour change.
4. Run `alembic check`, `pytest`, `ruff check .`,
   `ruff format --check .`, and in `dashboard/` `npm run lint`,
   `npm run test`, and `npm run build`.
5. Remove private hostnames, addresses, tokens, and logs from examples.
6. Open a pull request explaining the problem, approach, and test evidence.

Database model changes must include an Alembic migration. Public API changes
must update OpenAPI descriptions and `docs/api.md`.

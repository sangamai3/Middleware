# SangamMW Backend

Open-source middleware / iPaaS platform.

## Database (dev)

From the repo root:

- `make dev-db` or `sangam db ensure` — connect to Postgres, auto-start Docker Compose `postgres` when `SANGAM_POSTGRES=auto`, run migrations.
- `make dev` — same, then API on port **8100** (matches Vite proxy).
- `make dev-all` — API + frontend via `scripts/dev.sh`.

Copy `.env.example` → `.env`. Use `SANGAM_POSTGRES=local` and your own `DATABASE_URL` if you do not use Docker Postgres.

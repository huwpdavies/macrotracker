# Learning notes

## Phase 0: Repository and tooling
- Built: project folder, virtual environment (`.venv`), `requirements.txt`, `.gitignore`, `.env.example`, README, MIT licence.
- Concepts: a virtual environment keeps this project's packages separate from the rest of your Mac; `requirements.txt` pins exact versions so Vercel installs the same thing; `.gitignore` keeps secrets and clutter out of git; `.env` (secret, local) vs `.env.example` (safe template, committed).
- Files to read: `.gitignore`, `requirements.txt`, `.env.example`.

## Phase 1: Flask skeleton
- Built: `create_app()` factory, config from environment variables, a `dashboard` blueprint, `base.html` + a hello page, `robots.txt`, first tests.
- Concepts: app factory (build the app in a function so tests/config can vary); blueprints (route groups registered on the app); Jinja `extends`/`block`; Vercel runs the whole app as one serverless function that finds `app` in `app.py`; static files live in `public/` (Flask serves it locally at the root to match).
- Files to read: `app.py`, `macrotracker/__init__.py`, `macrotracker/blueprints/dashboard.py`, `macrotracker/templates/base.html`.
- Deploy gotchas: Vercel needed `pyproject.toml` with `[tool.vercel] entrypoint = "app:app"`, and that file must also have a `[project]` table with dependencies (Vercel builds with `uv`). Dependencies are therefore listed in both `pyproject.toml` and `requirements.txt`; update both.

## Phase 2: Database and models
- Built: SQLAlchemy models (Food, Meal, MealItem, Goal, LogEntry), Flask-Migrate set up, `flask seed`, tests on in-memory SQLite.
- Concepts: a model is a Python class that maps to a table; a migration is a versioned script that changes the schema (`flask db migrate` writes it, `flask db upgrade` applies it); `DATABASE_URL` lives in `.env` locally and Vercel settings in production; `NullPool` = one connection per use, because serverless instances would otherwise hoard connections and Supabase's pooler does the pooling; a partial unique index makes the database itself allow only one active goal.
- Files to read: `macrotracker/models.py`, `macrotracker/config.py`, `macrotracker/seed.py`, `tests/test_models.py`.

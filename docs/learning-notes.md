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
- Gotcha: Supabase's *direct* connection (port 5432) is IPv6-only and Vercel can't reach it. Use the *transaction pooler* string (port 6543, user `postgres.<ref>`, host `...pooler.supabase.com`).

## Phase 3: Foods
- Built: foods list (HTMX search), detail, create/edit/delete with Flask-WTF forms + CSRF, live per-serving preview, `services/nutrition.py` with tests.
- Concepts: GET shows a page, POST changes data, then redirect so refresh can't resubmit; `form.validate_on_submit()` runs the rules in `forms.py`; CSRF tokens stop other sites posting to us; HTMX attributes (`hx-get`, `hx-post`, `hx-target`) fetch small HTML fragments from routes and swap them in; a route checks the `HX-Request` header to return a fragment instead of a full page; display rounding happens in a Jinja filter, never in the stored numbers.
- Files to read: `macrotracker/blueprints/foods.py`, `macrotracker/forms.py`, `macrotracker/services/nutrition.py`, `macrotracker/templates/foods/form.html`.

## Phase 3b: Food form redesign (from the HTML prototype)
- Changed: calories are typed from the label and stored (`calories_kcal` on foods, goals, log entries); brand removed; favourite stars on foods (and a column on meals for Phase 4); paste-a-label autofill; compact form layout.
- Concepts: a migration can change existing data too (we backfilled calories with `op.execute`); `server_default` lets a NOT NULL column be added to a table that already has rows; pure-Python parsing in `services/label_parser.py` is easy to test, while a small JS file just copies the result into the inputs; `hx-headers` on `<body>` sends the CSRF token with every HTMX POST.
- Files to read: `macrotracker/services/label_parser.py`, `public/js/food-form.js`, `macrotracker/templates/foods/form.html`, `migrations/versions/03d1e472b24e_*.py`.

## Phase 4: Meals
- Built: meal list/detail/create/edit/delete, ingredient rows you add and remove without a page reload, live totals and per-serving totals, favourite stars, `servings` column on meals.
- Concepts: one-to-many (`meal.items`, `item.food`; `cascade="all, delete-orphan"` removes items with their meal); a variable number of form rows is read with `request.form.getlist()` instead of a WTForms FieldList (plainer); HTMX partials (`/meals/row` returns one row, `/meals/preview` returns totals); `{% include %}` reuses the row and nutrient-chip fragments; htmx won't send a `<form>` that fails browser validation, so the `hx-` attributes sit on a wrapper div; an app-level check (food in a meal?) gives a friendly message and the foreign key is the safety net.
- Files to read: `macrotracker/blueprints/meals.py`, `macrotracker/templates/meals/form.html`, `macrotracker/templates/partials/_meal_item_row.html`, `macrotracker/services/nutrition.py`.

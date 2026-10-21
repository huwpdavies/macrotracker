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

## Food page redesign (view and edit share one layout)
- Changed: the food detail page and the edit form now render the same `foods/_sheet.html` (a flag, `editing`, switches text for inputs), so they look identical; the food list is a table with one column per nutrient (per typical serving).
- Concepts: one template included from two pages with a different variable set in each (`{% set editing = True %}`); Jinja macros for repeated cells; responsive tables (`overflow-x: auto`, short headers and a hidden column on narrow screens, with `aria-hidden` on the short labels); tidying `Decimal`s for display (`256.00` -> `256`) in the route before the form renders.
- Files to read: `macrotracker/templates/foods/_sheet.html`, `macrotracker/templates/partials/_food_rows.html`, the "Food sheet" and "Food list table" sections of `public/css/main.css`.

## Full visual redesign (modern, grey and blue)
- Changed: replaced the sandy/playful look with a clean system: light grey page, white cards, one blue accent, Inter font, one type scale and spacing scale. Top bar on desktop, bottom tab bar on phones. No per-nutrient colours (labels carry the meaning).
- Concepts: design tokens as CSS variables in `:root`; the same `<nav>` is a top bar or a fixed bottom bar purely through a media query; component classes (`.btn`, `.card`, `.rows`, `.field`) reused across pages instead of one-off styles; a Jinja macro in `base.html` builds the nav links and marks the current page with `aria-current`; `request.blueprint` tells the template which section is active; tap targets are at least 44px and focus rings are visible.
- Files to read: `public/css/main.css` (sections 1 to 13), `macrotracker/templates/base.html`.

## Redesign 2: ivory and navy, one set of components
- Changed: ivory paper background with a fine grain (an SVG noise filter in a CSS variable, no image file), navy for text, top bar, bottom tab bar and buttons; Fraunces serif for headings, Inter for everything else. Every page now uses the same parts: page header (eyebrow + title), sections with one heading style, nutrient tiles (calories in navy), and one table style for both foods and meals. Meal pages now share a view/edit sheet like foods.
- Concepts: shared Jinja macros imported with `{% from "partials/_table_macros.html" import ... %}` so two tables can't drift apart; one `_nutrients.html` partial replaces three different nutrient displays; CSS specificity (`input[type=text]` beat `.title-input` until the selector became `input.title-input`); `:has()` to adjust a grid based on the tile that follows.
- Files to read: `public/css/main.css`, `macrotracker/templates/partials/_nutrients.html`, `macrotracker/templates/partials/_table_macros.html`, `macrotracker/templates/meals/_sheet.html`.

## Phase 5: Goals
- Built: goal list (active goal first, one-click "Make active"), goal page and edit form sharing one layout, delete flow that asks which goal takes over when you delete the active one, Goals tab in the nav.
- Concepts: a database constraint (the partial unique index) is a guarantee no bug can break; an application check (`services/goals.py`) gives friendly behaviour on top. A transaction groups changes so they all happen or none do: switching goals turns the old one off, `flush()`es, then turns the new one on, and `rollback()` undoes everything if anything fails (there is a test that forces a failure). Business rules live in a service module so routes stay short and the rules can be tested directly. Redirects only follow paths on this site (`next` must start with a single `/`).
- Files to read: `macrotracker/services/goals.py`, `macrotracker/blueprints/goals.py`, `tests/test_goals.py`, `macrotracker/templates/partials/_tile_macros.html`.
- Update: the goals list is now one card per goal with Make active, Edit and Delete right on it (goals are a short list you act on, so cards suit them better than a table).

## Phase 6: Daily log
- Built: a page per day (`/log/2026-10-21`) with previous/next/today, quick-add search that logs foods (servings or raw amount) and meals, day totals, edit amount, remove entry, and a Log tab.
- Concepts: snapshotting (each entry copies name, unit and nutrition when logged; editing the amount rescales the entry's own numbers, never the food's); "today" always comes from `services/dates.today_london()` because servers run on UTC (`tzdata` is installed so Vercel has the London rules); URL parameter = which thing (the day in the path), query string = options (`?q=tuna` for search); meals expand into one entry per food, scaled by servings eaten / servings the recipe makes; a bad date in the URL returns 404.
- Files to read: `macrotracker/services/log.py`, `macrotracker/services/dates.py`, `macrotracker/blueprints/log.py`, `macrotracker/templates/log/day.html`, `tests/test_log.py`.

## Phase 7: Dashboard
- Built: the home page is now the dashboard for a day (`/?day=2026-10-20`, default today): a large navy calories card, a bar per nutrient with eaten / goal, percentage and "to go"/"over" text, the day's entries, previous/next day, and the active goal with a link to change it. Under / on target (90–110%) / over; protein and fibre over = celebration (tick pops in), salt is a ceiling (over 100% warns), other overs warn.
- Concepts: aggregate queries (`func.sum` with `func.coalesce(..., 0)` adds up a day in one SQL query); the route passes ready-made rows so the template only displays; Jinja filters (`|num`, new `|pct`) and the built-in `min` to cap bar widths at 100%; query string for an optional value (the day on the home page) versus URL parameter for a required one (the day in `/log/<day>`); `prefers-reduced-motion` turns the bar animation off.
- Files to read: `macrotracker/services/dashboard.py`, `macrotracker/blueprints/dashboard.py`, `macrotracker/templates/dashboard/index.html`, `tests/test_dashboard.py`.

## Phase 8: Design pass
- Done: reorganised `main.css` into 13 numbered sections with each component's phone rules next to it and reduced motion last; removed unused rules (found with a script that checks every class against the templates); measured WCAG contrast for every colour pair (all text passes AA; input borders failed at 1.7:1, so a new `--control` colour gives 3:1 or more); placeholders readable but italic; favicon; a friendly line at the top of the dashboard (problems first, then wins).
- Concepts: CSS variables (tokens in `:root`, used with `var()`), so a colour or spacing change is one edit; flexbox for one direction that wraps (button rows, list rows), grid for rows and columns (tiles: 3 across, 2 on phones); without a build step, order and grouping are the organisation: tokens first, shared components next, page-specific last, `prefers-reduced-motion` at the end so it wins.
- Files to read: the top of `public/css/main.css` (contents and tokens), `macrotracker/services/dashboard.py` (`cheer`).

## Phase 9: Polish and hand-over
- Built: friendly error pages (404 not found, 500 something went wrong, 503 database unreachable) in the app's style with "Try again" and "Go to dashboard"; checked every save/delete/switch shows a flash message; README with screenshots, setup, env vars, deploy steps and a folder tour; the app now refuses to start on Vercel without a real `SECRET_KEY`.
- Concepts: `@app.errorhandler(...)` runs for an error anywhere in the app; catching `OperationalError` (the database didn't answer) in one place and rolling back the broken transaction; flash messages live in the signed session cookie for one request; `SECRET_KEY` signs that cookie and the CSRF tokens, so a public default would let anyone forge them, so fail loudly instead of falling back; hidden browser tabs pause CSS animations, which is why screenshots of a background page can show half-drawn bars.
- Files to read: `macrotracker/errors.py`, `macrotracker/templates/errors/error.html`, `macrotracker/config.py`, `README.md`.

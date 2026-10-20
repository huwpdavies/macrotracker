# Macro Tracker

A playful, game-like web app for tracking daily macronutrient intake (protein, carbs, fat, salt, fibre) against a chosen goal. Single user, no login.

> **Warning: there is no login.** Anyone who has the URL can view and edit the data. Do not share the URL. The site asks search engines not to index it, but that is not security.

## Stack

Flask (Python), Jinja templates + HTMX, plain CSS, Supabase Postgres, hosted on Vercel.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit .env with real values
```

`.env` holds secrets and is never committed; `.env.example` is the committed template.

## Deployment

Added in Phase 1 (Vercel) and Phase 2 (Supabase).

## Future ideas

Barcode scanning, food database imports, login/accounts, charts over weeks, a mobile app, streaks/badges/levels.

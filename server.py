from flask import Flask, jsonify, request, send_from_directory
import sqlite3
import os
import time
import random
import string

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'macro-tracker.db')


def uid():
    ts = format(int(time.time() * 1000), 'x')
    rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return ts + rand


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS ingredients (
                id      TEXT PRIMARY KEY,
                name    TEXT NOT NULL,
                per     REAL NOT NULL DEFAULT 100,
                calories REAL NOT NULL DEFAULT 0,
                protein REAL NOT NULL DEFAULT 0,
                carbs   REAL NOT NULL DEFAULT 0,
                fat     REAL NOT NULL DEFAULT 0,
                fibre   REAL NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS meals (
                id       TEXT PRIMARY KEY,
                name     TEXT NOT NULL,
                servings REAL NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS meal_ingredients (
                id            TEXT PRIMARY KEY,
                meal_id       TEXT NOT NULL,
                ingredient_id TEXT NOT NULL,
                amount        REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS goals (
                id       TEXT PRIMARY KEY,
                name     TEXT NOT NULL,
                calories REAL NOT NULL DEFAULT 0,
                protein  REAL NOT NULL DEFAULT 0,
                carbs    REAL NOT NULL DEFAULT 0,
                fat      REAL NOT NULL DEFAULT 0,
                fibre    REAL NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS log_entries (
                id       TEXT PRIMARY KEY,
                date     TEXT NOT NULL,
                name     TEXT NOT NULL,
                detail   TEXT NOT NULL DEFAULT '',
                calories REAL NOT NULL DEFAULT 0,
                protein  REAL NOT NULL DEFAULT 0,
                carbs    REAL NOT NULL DEFAULT 0,
                fat      REAL NOT NULL DEFAULT 0,
                fibre    REAL NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_log_date ON log_entries (date);
        ''')


init_db()


def migrate_db():
    with get_db() as conn:
        for col, default in [
            ('servings', '1'),
            ('calories', '0'), ('protein', '0'),
            ('carbs',    '0'), ('fat',     '0'), ('fibre', '0'),
        ]:
            try:
                conn.execute(f'ALTER TABLE meals ADD COLUMN {col} REAL DEFAULT {default}')
            except Exception:
                pass  # column already exists


migrate_db()


# ── Static ────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'macro-tracker.html')


# ── Ingredients ───────────────────────────────────────────────────────────────
@app.route('/api/ingredients', methods=['GET'])
def get_ingredients():
    with get_db() as conn:
        rows = conn.execute('SELECT * FROM ingredients ORDER BY name COLLATE NOCASE').fetchall()
        return jsonify([dict(r) for r in rows])


@app.route('/api/ingredients', methods=['POST'])
def create_ingredient():
    d = request.json
    with get_db() as conn:
        conn.execute(
            'INSERT INTO ingredients (id,name,per,calories,protein,carbs,fat,fibre) VALUES (?,?,?,?,?,?,?,?)',
            (d['id'], d['name'], d['per'], d['calories'], d['protein'], d['carbs'], d['fat'], d['fibre'])
        )
    return jsonify({'ok': True})


@app.route('/api/ingredients/<ing_id>', methods=['PUT'])
def update_ingredient(ing_id):
    d = request.json
    with get_db() as conn:
        conn.execute(
            'UPDATE ingredients SET name=?,per=?,calories=?,protein=?,carbs=?,fat=?,fibre=? WHERE id=?',
            (d['name'], d['per'], d['calories'], d['protein'], d['carbs'], d['fat'], d['fibre'], ing_id)
        )
    return jsonify({'ok': True})


@app.route('/api/ingredients/<ing_id>', methods=['DELETE'])
def delete_ingredient(ing_id):
    with get_db() as conn:
        conn.execute('DELETE FROM ingredients WHERE id=?', (ing_id,))
    return jsonify({'ok': True})


# ── Meals ─────────────────────────────────────────────────────────────────────
def fetch_meals(conn):
    meals = [dict(r) for r in conn.execute('SELECT * FROM meals ORDER BY name COLLATE NOCASE').fetchall()]
    for m in meals:
        rows = conn.execute(
            'SELECT ingredient_id AS ingredientId, amount FROM meal_ingredients WHERE meal_id=? ORDER BY rowid',
            (m['id'],)
        ).fetchall()
        m['ingredients'] = [dict(r) for r in rows]
    return meals


@app.route('/api/meals', methods=['GET'])
def get_meals():
    with get_db() as conn:
        return jsonify(fetch_meals(conn))


@app.route('/api/meals', methods=['POST'])
def create_meal():
    d = request.json
    with get_db() as conn:
        conn.execute(
            'INSERT INTO meals (id,name,servings,calories,protein,carbs,fat,fibre) VALUES (?,?,?,?,?,?,?,?)',
            (d['id'], d['name'], d.get('servings', 1),
             d.get('calories', 0), d.get('protein', 0), d.get('carbs', 0), d.get('fat', 0), d.get('fibre', 0))
        )
        for mi in d.get('ingredients', []):
            conn.execute(
                'INSERT INTO meal_ingredients (id,meal_id,ingredient_id,amount) VALUES (?,?,?,?)',
                (uid(), d['id'], mi['ingredientId'], mi['amount'])
            )
    return jsonify({'ok': True})


@app.route('/api/meals/<meal_id>', methods=['PUT'])
def update_meal(meal_id):
    d = request.json
    with get_db() as conn:
        conn.execute(
            'UPDATE meals SET name=?, servings=?, calories=?, protein=?, carbs=?, fat=?, fibre=? WHERE id=?',
            (d['name'], d.get('servings', 1),
             d.get('calories', 0), d.get('protein', 0), d.get('carbs', 0), d.get('fat', 0), d.get('fibre', 0),
             meal_id)
        )
        conn.execute('DELETE FROM meal_ingredients WHERE meal_id=?', (meal_id,))
        for mi in d.get('ingredients', []):
            conn.execute(
                'INSERT INTO meal_ingredients (id,meal_id,ingredient_id,amount) VALUES (?,?,?,?)',
                (uid(), meal_id, mi['ingredientId'], mi['amount'])
            )
    return jsonify({'ok': True})


@app.route('/api/meals/<meal_id>', methods=['DELETE'])
def delete_meal(meal_id):
    with get_db() as conn:
        conn.execute('DELETE FROM meal_ingredients WHERE meal_id=?', (meal_id,))
        conn.execute('DELETE FROM meals WHERE id=?', (meal_id,))
    return jsonify({'ok': True})


# ── Goals ─────────────────────────────────────────────────────────────────────
@app.route('/api/goals', methods=['GET'])
def get_goals():
    with get_db() as conn:
        rows = conn.execute('SELECT * FROM goals').fetchall()
        return jsonify([dict(r) for r in rows])


@app.route('/api/goals', methods=['POST'])
def create_goal():
    d = request.json
    with get_db() as conn:
        conn.execute(
            'INSERT INTO goals (id,name,calories,protein,carbs,fat,fibre) VALUES (?,?,?,?,?,?,?)',
            (d['id'], d['name'], d['calories'], d['protein'], d['carbs'], d['fat'], d['fibre'])
        )
    return jsonify({'ok': True})


@app.route('/api/goals/<goal_id>', methods=['PUT'])
def update_goal(goal_id):
    d = request.json
    with get_db() as conn:
        conn.execute(
            'UPDATE goals SET name=?,calories=?,protein=?,carbs=?,fat=?,fibre=? WHERE id=?',
            (d['name'], d['calories'], d['protein'], d['carbs'], d['fat'], d['fibre'], goal_id)
        )
    return jsonify({'ok': True})


@app.route('/api/goals/<goal_id>', methods=['DELETE'])
def delete_goal(goal_id):
    with get_db() as conn:
        conn.execute('DELETE FROM goals WHERE id=?', (goal_id,))
    return jsonify({'ok': True})


# ── Settings ──────────────────────────────────────────────────────────────────
@app.route('/api/settings', methods=['GET'])
def get_settings():
    with get_db() as conn:
        rows = conn.execute('SELECT key, value FROM settings').fetchall()
        return jsonify({r['key']: r['value'] for r in rows})


@app.route('/api/settings', methods=['PUT'])
def update_settings():
    with get_db() as conn:
        for k, v in request.json.items():
            conn.execute('INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)', (k, str(v or '')))
    return jsonify({'ok': True})


# ── Log Entries ───────────────────────────────────────────────────────────────
@app.route('/api/log/<date>', methods=['GET'])
def get_log(date):
    with get_db() as conn:
        rows = conn.execute(
            'SELECT * FROM log_entries WHERE date=? ORDER BY rowid', (date,)
        ).fetchall()
        return jsonify([dict(r) for r in rows])


@app.route('/api/log/<date>', methods=['POST'])
def add_log_entry(date):
    d = request.json
    with get_db() as conn:
        conn.execute(
            'INSERT INTO log_entries (id,date,name,detail,calories,protein,carbs,fat,fibre) VALUES (?,?,?,?,?,?,?,?,?)',
            (d['id'], date, d['name'], d.get('detail', ''), d['calories'], d['protein'], d['carbs'], d['fat'], d['fibre'])
        )
    return jsonify({'ok': True})


@app.route('/api/log/entry/<entry_id>', methods=['DELETE'])
def delete_log_entry(entry_id):
    with get_db() as conn:
        conn.execute('DELETE FROM log_entries WHERE id=?', (entry_id,))
    return jsonify({'ok': True})


if __name__ == '__main__':
    print('\n  Macro Tracker is running!')
    print('  Open: http://localhost:5000\n')
    app.run(debug=False, port=5000)

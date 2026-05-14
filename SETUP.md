# Lunsjavtale – Local setup (macOS/zsh, Postgres.app, no Docker)

Run these commands from the **repo root** (same folder as `manage.py`). Use a single shell and run in order.

---

## 1) Virtual environment

```bash
cd "." # Go to the project root directory

python3 -m venv .venv
source .venv/bin/activate
```

You should see `(.venv)` in your prompt.

---

## 2) Python dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Check imports (run from repo root; graphene_django needs Django configured):**

```bash
DJANGO_SETTINGS_MODULE=backend.settings python -c "import django; django.setup(); import decouple; from corsheaders.defaults import default_headers; import graphene_django; print('OK')"
```

- **If `ModuleNotFoundError: No module named 'psycopg2'`:**  
  `pip install psycopg2-binary`  
  (Already in `requirements.txt`; only needed if you had a separate/older env.)

- **If any other import fails:**  
  Ensure the venv is activated and re-run `pip install -r requirements.txt`.

---

## 3) Environment file

A `.env` file is already in the repo root (same folder as `manage.py`) with:

- `DEBUG=True`, `SECRET_KEY=dev-secret-key-change-me`, `ALLOWED_HOSTS=localhost,127.0.0.1`
- DB: `ENGINE=django.db.backends.postgresql`, `NAME=lunsjavtale`, `DB_USER=postgres`, `PASSWORD=postgres`, `HOST=localhost`, `PORT=5432`
- Placeholders for Vipps, email, Firebase (app runs without them).

If you change DB user/password or database name, update `.env` to match.

---

## 4) PostgreSQL (Postgres.app on localhost:5432)

**Verify connection:**

```bash
psql -h localhost -p 5432 -U postgres -d postgres -c "SELECT 1;"
```

- **If `psql: command not found`:**  
  Add Postgres.app’s bin to `PATH`, e.g. in `~/.zshrc`:  
  `export PATH="/Applications/Postgres.app/Contents/Versions/latest/bin:$PATH"`  
  then `source ~/.zshrc`.

- **If connection refused:**  
  Start Postgres.app (open the app and ensure the elephant icon shows it’s running).

**Create role and database (only if they don’t exist):**

```bash
# Create user 'postgres' with password (if your setup uses a different default user, run as that user)
psql -h localhost -p 5432 -d postgres -c "CREATE USER postgres WITH PASSWORD 'postgres' SUPERUSER CREATEDB CREATEROLE LOGIN;" 2>/dev/null || true

# Create database
psql -h localhost -p 5432 -U postgres -d postgres -c "CREATE DATABASE lunsjavtale OWNER postgres;" 2>/dev/null || true

# Grant privileges (optional, postgres owner usually has them)
psql -h localhost -p 5432 -U postgres -d lunsjavtale -c "GRANT ALL PRIVILEGES ON DATABASE lunsjavtale TO postgres;"
```

**Note:** Postgres.app often creates a user with your macOS username. If `postgres` doesn’t exist and you prefer not to create it, set in `.env`:

- `DB_USER=` your macOS username  
- `PASSWORD=` empty or your Postgres.app password  

and create the DB as that user, then point `NAME=lunsjavtale` to it.

---

## 5) Django setup

Ensure venv is activated and you’re in the repo root.

```bash
source .venv/bin/activate
cd "." # Go to the project root directory
```

**Migrations:**

```bash
python manage.py makemigrations
python manage.py migrate
```

**Superuser (optional):**

```bash
python manage.py createsuperuser
```

**Run server:**

```bash
python manage.py runserver
```

- Server: http://127.0.0.1:8000/  
- **If `ImproperlyConfigured` or `decouple` error:**  
  Check that `.env` is in the same directory as `manage.py` and that you’re running commands from that directory.  
- **If DB connection error:**  
  Check `DB_USER`, `PASSWORD`, `HOST`, `PORT`, `NAME` in `.env` and that the database and role exist (step 4).  
- **If `No module named 'psycopg2'`:**  
  `pip install psycopg2-binary`.

---

## 6) Celery / Redis

Settings use `CELERY_BROKER_URL = 'redis://localhost:6379'`. For Celery you need Redis.

**macOS (Homebrew):**

```bash
brew install redis
brew services start redis
```

**Check Redis:**

```bash
redis-cli ping
# Expected: PONG
```

To run Celery worker (optional, only if the app uses async tasks):

```bash
celery -A backend worker -l info
```

(Replace `backend` if your project package name is different; `backend` matches this repo.)

---

## Quick reference – order of commands

```bash
cd "." # Go to the project root directory
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python -c "import django, decouple; from corsheaders.defaults import default_headers; import graphene_django; print('OK')"

# Postgres: verify then create DB/user if needed (see above)
psql -h localhost -p 5432 -U postgres -d postgres -c "CREATE DATABASE lunsjavtale OWNER postgres;" 2>/dev/null || true

python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser   # optional
python manage.py runserver
```

---

## Common fixes

| Problem | Fix |
|--------|-----|
| **decouple / config error** | `.env` in repo root; run `manage.py` from repo root. |
| **DB connection refused** | Start Postgres.app; check `HOST=localhost`, `PORT=5432`. |
| **role "postgres" does not exist** | Create user (step 4) or set `DB_USER`/`PASSWORD` in `.env` to your Postgres.app user. |
| **database "lunsjavtale" does not exist** | Run the `CREATE DATABASE` command in step 4. |
| **No module named 'psycopg2'** | `pip install psycopg2-binary` (and ensure venv is active). |
| **Celery/Redis connection error** | Install and start Redis: `brew install redis && brew services start redis`. |

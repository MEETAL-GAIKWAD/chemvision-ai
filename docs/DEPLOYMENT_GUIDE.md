# ChemVision AI deployment guide

Status: deployment preparation only. No hosting account, target platform, or deployed URL was provided or verified. Do not describe the application as deployed.

## Architecture and requirements

- Static HTML/CSS/JavaScript frontend, hosted as static files.
- FastAPI backend, Python 3.12 recommended by the supplied local virtual environment.
- SQLite for a single-instance demonstration; PostgreSQL is supported through `DATABASE_URL` for a hosted backend.
- Persistent writable storage is required for uploaded images when using the current local upload implementation.
- CPU inference is supported. The current chemistry classifier is experimental and must not establish reaction identity. EasyOCR may download model data on first use. PubChem search requires outbound network access.
- ML training dependencies are separate in `ml/requirements.txt`; they are not required to serve the ordinary API. Use a compatible PyTorch/torchvision pair and a GPU only for a future training run.

## Local setup

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env`. For local development, keep the default SQLite path and set a unique secret, for example by generating one with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Start the API from `backend`:

```powershell
..venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal from the project root:

```powershell
python -m http.server 8080
```

Open `http://127.0.0.1:8080/home.html`. Verify `http://127.0.0.1:8000/health` returns database availability and that signup/login, upload, learning content, and profile routes behave as expected.

## Production configuration

Set these variables through the hosting provider's secret/configuration manager. Never commit real values.

| Variable | Required production setting |
|---|---|
| `ENVIRONMENT` | Set to `production`; this disables local file-origin and localhost CORS allowances and requires explicit origins and a non-placeholder secret. |
| `DATABASE_URL` | Persistent PostgreSQL URL, e.g. `postgresql+psycopg://...`; do not rely on an ephemeral container filesystem for SQLite. |
| `JWT_SECRET_KEY` | Unique high-entropy secret; replace the development fallback. |
| `JWT_ALGORITHM` | `HS256` unless the deployment has a reviewed key-management reason to change it. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Choose an appropriate session lifetime; default is 24 hours. |
| `FRONTEND_ORIGINS` | Comma-separated exact HTTPS origins only. Do not include `null` or localhost. |
| `UPLOAD_DIR` | Persistent volume path with restricted filesystem permissions and backups. |
| `MAX_UPLOAD_MB` | Keep bounded; current default is 8 MB. |

The backend adds tables with `Base.metadata.create_all()` at startup. This is not a migration system and does not alter existing columns safely. Before production schema changes, introduce Alembic and test migrations against a database backup. Back up the database and upload volume together. Static hosting must route API requests to the backend URL; set `window.CHEMVISION_API_BASE` before `js/api.js` loads (or use the existing local-storage override) when frontend and API do not share the default `http://127.0.0.1:8000` origin.

## Deployment checks and current blockers

- Use HTTPS for frontend and API; configure exact CORS origins and persistent database/upload storage.
- Uploaded reaction images are delivered through an owner-checked authenticated API route; the public `/uploads` static mount has been removed. Keep the upload volume restricted and persistent.
- Run `GET /health` after startup. It checks a DB connection; it does not verify OCR weights, PubChem connectivity, or model inference.
- Confirm database initialization, signup/login, one authenticated upload, user-scoped history, quiz submission, and flashcard review in a staging deployment.
- Confirm upload volume persistence across restart and recovery from a database/upload backup.
- Do not load `best_model.pth` as a trusted reaction identifier; its saved result is poor and its original evaluation omitted 33 of 54 test samples.
- Browser-based QA across all pages, mobile layouts, and dark/light themes has not been executed as part of this source/runtime verification.

## Database initialization and migration

For a new database, starting the FastAPI process creates current tables and seeds learning content. Existing SQLite data is kept in `backend/app.db`; preserve and back it up before moving or changing database settings. There is no migration command today. `create_all()` only creates missing tables and will not migrate changed columns. Do not delete or replace the existing database to resolve a schema issue.

## Production dependencies

Install `backend/requirements.txt` in the API environment. Install `ml/requirements.txt` only in a separate training/benchmark environment. The current ML requirements use open-ended PyTorch version constraints; pin and verify a matching `torch`/`torchvision` wheel pair for the target OS/Python before training. No GPU is needed for the current static frontend and ordinary backend serving. The bundled model is optional and CPU inference is possible, but reaction identity remains unverified.

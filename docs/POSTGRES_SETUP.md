# PostgreSQL Setup

The backend reads `RAG_DATABASE_URL` from `.env` or the process environment. SQLite remains the local default; PostgreSQL is supported through SQLAlchemy and Alembic.

Proxy evaluation only. These results do not demonstrate clinical safety, clinical effectiveness, or real-world healthcare performance. Real EHR evaluation requires credentialed datasets such as MIMIC-IV-Note or MIMIC-IV-BHC under approved governance processes.

## Start PostgreSQL

```powershell
docker run --name clin-summ-postgres -e POSTGRES_USER=clin_summ -e POSTGRES_PASSWORD=clin_summ_dev -e POSTGRES_DB=clin_summ -p 5433:5432 -v clin_summ_pgdata:/var/lib/postgresql/data -d postgres:16
```

## Configure Environment

```powershell
Copy-Item .env.example .env
$env:DATABASE_URL="postgresql+psycopg://clin_summ:clin_summ_dev@127.0.0.1:5433/clin_summ"
$env:HF_HOME="D:\hf_cache"
$env:HF_HUB_CACHE="D:\hf_cache\hub"
$env:HF_DATASETS_CACHE="D:\hf_cache\datasets"
$env:TRANSFORMERS_CACHE="D:\hf_cache\hub"
```

## Install and Migrate

```powershell
python -m pip install -r requirements.txt
python -m alembic -c alembic.ini upgrade head
python -m backend.app.db.seed
```

## Run Backend

```powershell
python -m uvicorn backend.app.main:app --reload --port 8080
```

The API docs are available at `http://127.0.0.1:8080/docs`.

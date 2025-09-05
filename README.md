# tree_life_backend

Small FastAPI app that connects to a local Postgres database and exposes a `/users` endpoint.

Setup

1. Create a virtualenv and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Ensure Postgres is running locally and the `tree_life` DB exists. The app reads DATABASE_URL from the environment; default is `postgres://hari@localhost:5432/tree_life`.

Run

```bash
uvicorn main:app --reload
```

GET /users will return all rows from the `persons` table.

# Expense Tracker — Render Ready

This version keeps the original Flask/HTML dashboard and adds:

- public Render deployment configuration
- PostgreSQL support through `DATABASE_URL`
- user registration/login/logout
- password hashing
- user-specific expenses
- persistent cloud database support
- production Gunicorn server
- `/health` endpoint
- local SQLite fallback for development

## Recommended Render setup

Render currently supports free Python web services and free PostgreSQL databases. The free PostgreSQL database has a 1 GB limit and expires 30 days after creation, so it is suitable for a short hackathon/demo but not permanent production storage.

### Easiest deployment

1. Put the contents of this folder into a GitHub repository.
2. In Render, choose **New → Blueprint** and select that repository.
3. Render reads `render.yaml` and creates the web service and PostgreSQL database.
4. Wait for deployment to finish.
5. Open the generated `https://...onrender.com` URL.
6. Register a test account and add expenses.

If you create the services manually instead, use:

- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app`
- Add a PostgreSQL database.
- Set `DATABASE_URL` to the database connection string.
- Set `SECRET_KEY` to a long random value.

## Important

Do not use the local `database.db` as the production database on Render. Free Render web services do not have persistent local filesystem storage. This project therefore uses PostgreSQL whenever `DATABASE_URL` is present.

## Local testing

Without `DATABASE_URL`, the app falls back to SQLite. Run:

```bash
pip install -r requirements.txt
python app.py
```

Then open `http://127.0.0.1:5000` on the same computer.

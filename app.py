import os
from datetime import datetime, date
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, g, session
from werkzeug.security import generate_password_hash, check_password_hash

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
CATEGORIES = ["Food", "Transport", "Shopping", "Education", "Entertainment", "Bills", "Other"]


def using_postgres():
    return bool(DATABASE_URL)


def get_db_connection():
    if "db" not in g:
        if using_postgres():
            if psycopg is None:
                raise RuntimeError("psycopg is required when DATABASE_URL is set")
            g.db = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        else:
            # Local fallback only. Render should use DATABASE_URL with Postgres.
            import sqlite3
            db_path = os.environ.get("SQLITE_PATH", "database.db")
            g.db = sqlite3.connect(db_path)
            g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db_connection(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db_connection()
    if using_postgres():
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                amount DOUBLE PRECISION NOT NULL,
                description VARCHAR(200) NOT NULL,
                category VARCHAR(50) NOT NULL,
                date DATE NOT NULL,
                created_at TIMESTAMP NOT NULL
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_expenses_user_date ON expenses(user_id, date DESC)")
    else:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                date TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_expenses_user_date ON expenses(user_id, date DESC)")
    db.commit()


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    db = get_db_connection()
    row = db.execute("SELECT id, name, email FROM users WHERE id = %s" % ("%s" if using_postgres() else "?"), (user_id,)).fetchone()
    return row


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_user():
    return {"current_user": current_user()}


def validate_expense_form(form):
    errors = {}
    amount_raw = form.get("amount", "").strip()
    description = form.get("description", "").strip()
    category = form.get("category", "").strip()
    date_raw = form.get("date", "").strip()
    amount = None

    if not amount_raw:
        errors["amount"] = "Amount is required."
    else:
        try:
            amount = float(amount_raw)
            if amount <= 0:
                errors["amount"] = "Amount must be greater than 0."
        except ValueError:
            errors["amount"] = "Amount must be a valid number."

    if not description:
        errors["description"] = "Description is required."
    elif len(description) > 200:
        errors["description"] = "Description must be under 200 characters."

    if category not in CATEGORIES:
        errors["category"] = "Please choose a valid category."

    if not date_raw:
        errors["date"] = "Date is required."
    else:
        try:
            datetime.strptime(date_raw, "%Y-%m-%d")
        except ValueError:
            errors["date"] = "Date must be in YYYY-MM-DD format."

    return len(errors) == 0, errors, {"amount": amount, "description": description, "category": category, "date": date_raw}


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        errors = []
        if not name:
            errors.append("Name is required.")
        if not email or "@" not in email:
            errors.append("Enter a valid email address.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")

        db = get_db_connection()
        placeholder = "%s" if using_postgres() else "?"
        existing = db.execute(f"SELECT id FROM users WHERE email = {placeholder}", (email,)).fetchone()
        if existing:
            errors.append("An account with this email already exists.")

        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("register.html", form_data=request.form)

        if using_postgres():
            row = db.execute(
                "INSERT INTO users (name, email, password_hash, created_at) VALUES (%s, %s, %s, %s) RETURNING id",
                (name, email, generate_password_hash(password), datetime.now()),
            ).fetchone()
            user_id = row["id"]
        else:
            cur = db.execute(
                "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (name, email, generate_password_hash(password), datetime.now().isoformat(timespec="seconds")),
            )
            user_id = cur.lastrowid
        db.commit()
        session.clear()
        session["user_id"] = user_id
        flash("Account created successfully!", "success")
        return redirect(url_for("dashboard"))
    return render_template("register.html", form_data={})


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        placeholder = "%s" if using_postgres() else "?"
        user = get_db_connection().execute(f"SELECT * FROM users WHERE email = {placeholder}", (email,)).fetchone()
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "danger")
            return render_template("login.html", form_data=request.form)
        session.clear()
        session["user_id"] = user["id"]
        flash("Welcome back!", "success")
        return redirect(url_for("dashboard"))
    return render_template("login.html", form_data={})


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    db = get_db_connection()
    uid = session["user_id"]
    p = "%s" if using_postgres() else "?"
    today = date.today()
    month_start = today.replace(day=1)
    total = db.execute(f"SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE user_id = {p}", (uid,)).fetchone()["total"]
    today_total = db.execute(f"SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE user_id = {p} AND date = {p}", (uid, today if using_postgres() else today.isoformat())).fetchone()["total"]
    if using_postgres():
        month_total = db.execute("SELECT COALESCE(SUM(amount),0) AS total FROM expenses WHERE user_id=%s AND date >= %s", (uid, month_start)).fetchone()["total"]
        recent = db.execute("SELECT * FROM expenses WHERE user_id=%s ORDER BY date DESC, id DESC LIMIT 5", (uid,)).fetchall()
    else:
        month_total = db.execute("SELECT COALESCE(SUM(amount),0) AS total FROM expenses WHERE user_id=? AND date >= ?", (uid, month_start.isoformat())).fetchone()["total"]
        recent = db.execute("SELECT * FROM expenses WHERE user_id=? ORDER BY date DESC, id DESC LIMIT 5", (uid,)).fetchall()
    count = db.execute(f"SELECT COUNT(*) AS count FROM expenses WHERE user_id = {p}", (uid,)).fetchone()["count"]
    return render_template("dashboard.html", total_expenses=total, today_expenses=today_total, month_expenses=month_total, transaction_count=count, recent_transactions=recent)


@app.route("/add", methods=["GET", "POST"])
@login_required
def add_expense():
    if request.method == "POST":
        valid, errors, cleaned = validate_expense_form(request.form)
        if not valid:
            for message in errors.values():
                flash(message, "danger")
            return render_template("add_expense.html", categories=CATEGORIES, form_data=request.form)
        db = get_db_connection()
        if using_postgres():
            db.execute("INSERT INTO expenses (user_id, amount, description, category, date, created_at) VALUES (%s,%s,%s,%s,%s,%s)", (session["user_id"], cleaned["amount"], cleaned["description"], cleaned["category"], datetime.strptime(cleaned["date"], "%Y-%m-%d").date(), datetime.now()))
        else:
            db.execute("INSERT INTO expenses (user_id, amount, description, category, date, created_at) VALUES (?,?,?,?,?,?)", (session["user_id"], cleaned["amount"], cleaned["description"], cleaned["category"], cleaned["date"], datetime.now().isoformat(timespec="seconds")))
        db.commit()
        flash("Expense added successfully!", "success")
        return redirect(url_for("dashboard"))
    return render_template("add_expense.html", categories=CATEGORIES, form_data={"date": date.today().isoformat()})


@app.route("/transactions")
@login_required
def transactions():
    category_filter = request.args.get("category", "").strip()
    sort_order = request.args.get("sort", "desc")
    search_query = request.args.get("q", "").strip()
    db = get_db_connection()
    conditions = ["user_id = %s" if using_postgres() else "user_id = ?"]
    params = [session["user_id"]]
    if category_filter in CATEGORIES:
        conditions.append("category = %s" if using_postgres() else "category = ?")
        params.append(category_filter)
    if search_query:
        conditions.append("description ILIKE %s" if using_postgres() else "description LIKE ?")
        params.append(f"%{search_query}%")
    order = "ASC" if sort_order == "asc" else "DESC"
    query = "SELECT * FROM expenses WHERE " + " AND ".join(conditions) + f" ORDER BY date {order}, id DESC"
    expenses = db.execute(query, params).fetchall()
    return render_template("transactions.html", expenses=expenses, categories=CATEGORIES, selected_category=category_filter, sort_order=sort_order, search_query=search_query)


@app.route("/edit/<int:expense_id>", methods=["GET", "POST"])
@login_required
def edit_expense(expense_id):
    db = get_db_connection()
    p = "%s" if using_postgres() else "?"
    expense = db.execute(f"SELECT * FROM expenses WHERE id = {p} AND user_id = {p}", (expense_id, session["user_id"])).fetchone()
    if expense is None:
        flash("Expense not found.", "danger")
        return redirect(url_for("transactions"))
    if request.method == "POST":
        valid, errors, cleaned = validate_expense_form(request.form)
        if not valid:
            for message in errors.values():
                flash(message, "danger")
            return render_template("edit_expense.html", expense=expense, categories=CATEGORIES, form_data=request.form)
        if using_postgres():
            db.execute("UPDATE expenses SET amount=%s, description=%s, category=%s, date=%s WHERE id=%s AND user_id=%s", (cleaned["amount"], cleaned["description"], cleaned["category"], datetime.strptime(cleaned["date"], "%Y-%m-%d").date(), expense_id, session["user_id"]))
        else:
            db.execute("UPDATE expenses SET amount=?, description=?, category=?, date=? WHERE id=? AND user_id=?", (cleaned["amount"], cleaned["description"], cleaned["category"], cleaned["date"], expense_id, session["user_id"]))
        db.commit()
        flash("Expense updated successfully!", "success")
        return redirect(url_for("transactions"))
    return render_template("edit_expense.html", expense=expense, categories=CATEGORIES, form_data=expense)


@app.route("/delete/<int:expense_id>", methods=["POST"])
@login_required
def delete_expense(expense_id):
    db = get_db_connection()
    p = "%s" if using_postgres() else "?"
    result = db.execute(f"DELETE FROM expenses WHERE id = {p} AND user_id = {p}", (expense_id, session["user_id"]))
    db.commit()
    if getattr(result, "rowcount", 0) == 0:
        flash("Expense not found.", "danger")
    else:
        flash("Expense deleted successfully!", "success")
    return redirect(url_for("transactions"))


@app.route("/api/category-data")
@login_required
def api_category_data():
    db = get_db_connection()
    p = "%s" if using_postgres() else "?"
    rows = db.execute(f"SELECT category, SUM(amount) AS total FROM expenses WHERE user_id={p} GROUP BY category ORDER BY total DESC", (session["user_id"],)).fetchall()
    return jsonify({"labels": [r["category"] for r in rows], "values": [round(float(r["total"]), 2) for r in rows]})


@app.route("/api/monthly-data")
@login_required
def api_monthly_data():
    db = get_db_connection()
    if using_postgres():
        rows = db.execute("SELECT TO_CHAR(date, 'YYYY-MM') AS month, SUM(amount) AS total FROM expenses WHERE user_id=%s GROUP BY month ORDER BY month ASC", (session["user_id"],)).fetchall()
    else:
        rows = db.execute("SELECT strftime('%Y-%m', date) AS month, SUM(amount) AS total FROM expenses WHERE user_id=? GROUP BY month ORDER BY month ASC", (session["user_id"],)).fetchall()
    return jsonify({"labels": [r["month"] for r in rows], "values": [round(float(r["total"]), 2) for r in rows]})


@app.route("/health")
def health():
    try:
        get_db_connection().execute("SELECT 1").fetchone()
        return "OK", 200
    except Exception as exc:
        return f"Database error: {exc}", 500


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)

from datetime import datetime
from pathlib import Path
import sqlite3

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "campuscare.db"
app = Flask(__name__)
app.secret_key = "campuscare-demo-local-key"

CATEGORIES = ["Safety Hazard", "Medical Assistance Request", "Security Concern", "Infrastructure Damage", "Fire/Electrical Risk", "Other"]
SEVERITIES = ["Low", "Medium", "High", "Critical"]
STATUSES = ["Submitted", "Acknowledged", "Assigned", "In progress", "Resolved"]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reference TEXT UNIQUE,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        category TEXT NOT NULL,
        severity TEXT NOT NULL,
        location TEXT NOT NULL,
        location_details TEXT,
        contact TEXT,
        status TEXT NOT NULL DEFAULT 'Submitted',
        assignee TEXT,
        resolution TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS updates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
        status TEXT NOT NULL,
        note TEXT NOT NULL,
        author TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """)
    db.commit()
    db.close()


init_db()


def stamp():
    return datetime.now().astimezone().isoformat(timespec="minutes")


def report_by_ref(reference):
    report = get_db().execute("SELECT * FROM reports WHERE reference = ?", (reference.upper(),)).fetchone()
    if report is None:
        abort(404)
    return report


@app.context_processor
def shared_context():
    return {"categories": CATEGORIES, "severities": SEVERITIES, "statuses": STATUSES}


@app.before_request
def require_demo_role():
    if request.endpoint in {"login", "logout", "static"}:
        return None
    role = session.get("role")
    if role not in {"reporter", "responder"}:
        return redirect(url_for("login"))
    if request.path.startswith("/responders") and role != "responder":
        flash("Switch to the responder portal to open response tools.", "error")
        return redirect(url_for("index"))
    if not request.path.startswith("/responders") and role != "reporter":
        flash("Switch to the reporter portal to open student tools.", "error")
        return redirect(url_for("index"))


@app.route("/login", methods=["GET", "POST"])
def login():
    selected_role = request.args.get("role", "reporter")
    if request.method == "POST":
        selected_role = request.form.get("role", "reporter")
        if selected_role not in {"reporter", "responder"}:
            selected_role = "reporter"
        session.clear()
        session["role"] = selected_role
        session["display_name"] = request.form.get("display_name", "").strip()[:80]
        return redirect(url_for("index"))
    if session.get("role") in {"reporter", "responder"} and "switch" not in request.args:
        return redirect(url_for("index"))
    if selected_role not in {"reporter", "responder"}:
        selected_role = "reporter"
    return render_template("login.html", selected_role=selected_role, standalone=True)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def index():
    if session.get("role") == "responder":
        return redirect(url_for("responders"))
    db = get_db()
    recent = db.execute("SELECT * FROM reports ORDER BY id DESC LIMIT 5").fetchall()
    total = db.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    active = db.execute("SELECT COUNT(*) FROM reports WHERE status != 'Resolved'").fetchone()[0]
    resolved = db.execute("SELECT COUNT(*) FROM reports WHERE status = 'Resolved'").fetchone()[0]
    return render_template("index.html", recent=recent, total=total, active=active, resolved=resolved, page="overview")


@app.route("/report", methods=["GET", "POST"])
def new_report():
    values = request.form if request.method == "POST" else {}
    errors = []
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "")
        severity = request.form.get("severity", "")
        location = request.form.get("location", "").strip()
        details = request.form.get("location_details", "").strip()
        contact = request.form.get("contact", "").strip()
        if not title: errors.append("Add a short title for the report.")
        if not description: errors.append("Describe what happened or what needs attention.")
        if category not in CATEGORIES: errors.append("Choose a valid report category.")
        if severity not in SEVERITIES: errors.append("Choose a severity level.")
        if not location: errors.append("Add a campus location or building.")
        if errors:
            for error in errors: flash(error, "error")
        else:
            db = get_db()
            now = stamp()
            cur = db.execute("INSERT INTO reports (title, description, category, severity, location, location_details, contact, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (title, description, category, severity, location, details, contact, now, now))
            report_id = cur.lastrowid
            reference = f"CC-{datetime.now().year}-{report_id:04d}"
            db.execute("UPDATE reports SET reference = ? WHERE id = ?", (reference, report_id))
            db.execute("INSERT INTO updates (report_id, status, note, author, created_at) VALUES (?, 'Submitted', ?, 'CampusCare system', ?)", (report_id, "Report received and added to the responder queue.", now))
            db.commit()
            return redirect(url_for("report_detail", reference=reference, submitted=1))
    return render_template("report.html", page="report", values=values)


@app.route("/my-reports", methods=["GET", "POST"])
def my_reports():
    found = None
    if request.method == "POST":
        reference = request.form.get("reference", "").strip()
        if reference:
            found = get_db().execute("SELECT * FROM reports WHERE reference = ?", (reference.upper(),)).fetchone()
            if found:
                return redirect(url_for("report_detail", reference=found["reference"]))
            flash("We couldn't find that reference. Check it and try again.", "error")
    return render_template("my_reports.html", page="my-reports", recent=get_db().execute("SELECT reference, title, status, severity, location, created_at FROM reports ORDER BY id DESC LIMIT 20").fetchall())


@app.route("/reports/<reference>")
def report_detail(reference):
    report = report_by_ref(reference)
    updates = get_db().execute("SELECT * FROM updates WHERE report_id = ? ORDER BY id DESC", (report["id"],)).fetchall()
    return render_template("detail.html", report=report, updates=updates, submitted=request.args.get("submitted") == "1", page="my-reports")


@app.route("/responders")
def responders():
    reports = get_db().execute("SELECT * FROM reports ORDER BY CASE status WHEN 'Submitted' THEN 0 WHEN 'Acknowledged' THEN 1 WHEN 'Assigned' THEN 2 WHEN 'In progress' THEN 3 ELSE 4 END, id DESC").fetchall()
    counts = {status: get_db().execute("SELECT COUNT(*) FROM reports WHERE status = ?", (status,)).fetchone()[0] for status in STATUSES}
    return render_template("responders.html", reports=reports, counts=counts, page="responders")


@app.route("/responders/<reference>/update", methods=["POST"])
def update_report(reference):
    report = report_by_ref(reference)
    status = request.form.get("status", "")
    assignee = request.form.get("assignee", "").strip()
    note = request.form.get("note", "").strip()
    resolution = request.form.get("resolution", "").strip()
    errors = []
    if status not in STATUSES: errors.append("Choose a valid status.")
    if status in ("Assigned", "In progress") and not assignee: errors.append("Add the responder or team responsible.")
    if status == "Resolved" and not resolution and not note: errors.append("Add a resolution summary or update note before resolving.")
    if errors:
        for error in errors: flash(error, "error")
        return redirect(url_for("responders") + "#" + reference)
    if not note:
        note = {"Acknowledged": "A responder acknowledged this report.", "Assigned": f"Assigned to {assignee}.", "In progress": f"Response in progress with {assignee}.", "Resolved": resolution, "Submitted": "Report status returned to submitted."}.get(status, f"Status updated to {status}.")
    if status == "Resolved" and not resolution:
        resolution = note
    now = stamp()
    get_db().execute("UPDATE reports SET status = ?, assignee = ?, resolution = ?, updated_at = ? WHERE id = ?", (status, assignee or report["assignee"], resolution if status == "Resolved" else report["resolution"], now, report["id"]))
    get_db().execute("INSERT INTO updates (report_id, status, note, author, created_at) VALUES (?, ?, ?, 'Campus responder', ?)", (report["id"], status, note, now))
    get_db().commit()
    flash(f"{report['reference']} updated to {status}.", "success")
    return redirect(url_for("responders") + "#" + reference)


@app.route("/how-it-works")
def how_it_works():
    return render_template("how.html", page="how")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False)

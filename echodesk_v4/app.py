import os
import secrets
import smtplib
from email.message import EmailMessage
from datetime import datetime, timezone
from functools import wraps

from bson import ObjectId
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_pymongo import PyMongo
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from flask_socketio import SocketIO, join_room
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/echodesk")

if not app.config["SECRET_KEY"]:
    raise RuntimeError("Missing SECRET_KEY. Add it to your .env file.")

mongo = PyMongo(app)
socketio = SocketIO(app)  # Same-origin connections by default.
login_manager = LoginManager(app)
login_manager.login_view = "login"

users = mongo.db.users
complaints = mongo.db.complaints

STATUSES = ["Submitted", "Under Review", "In Progress", "Resolved", "Closed"]
CATEGORIES = [
    "Academics", "Faculty", "Hostel", "Library", "Wi-Fi / Internet",
    "Infrastructure", "Fees", "Transport", "Other"
]
DEPARTMENTS = [
    "Administration", "Academic Department", "IT Department",
    "Hostel Department", "Library", "Transport Department",
    "Accounts Department"
]



def send_student_email(recipient, student_name, complaint, status, remarks):
    """Send a complaint status update using SMTP settings from .env. Return (ok, message)."""
    host = os.getenv("SMTP_HOST", "").strip()
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    sender = os.getenv("SMTP_FROM", username).strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() in {"1", "true", "yes"}

    if not host or not username or not password or not sender:
        return False, "Email not sent: configure SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD and SMTP_FROM in .env."
    if not recipient:
        return False, "Email not sent: this student's account has no email address."

    subject = f"Echo Desk update: {complaint.get('complaint_id', 'your complaint')} — {status}"
    if status == "Resolved":
        intro = "Good news! Your complaint has been marked as resolved by the administration."
    elif status == "Closed":
        intro = "Your complaint has been marked as closed by the administration."
    else:
        intro = f"Your complaint status has been updated to: {status}."

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        f"Hello {student_name},\n\n{intro}\n\n"
        f"Complaint ID: {complaint.get('complaint_id', 'N/A')}\n"
        f"Title: {complaint.get('title', 'N/A')}\n"
        f"Department: {complaint.get('department', 'N/A')}\n"
        f"Current status: {status}\n\n"
        f"Admin message: {remarks or 'No additional remarks.'}\n\n"
        "You can log in to Echo Desk to view the latest progress.\n\n"
        "Regards,\nEcho Desk College Administration"
    )
    try:
        if use_ssl:
            with smtplib.SMTP_SSL(host, port, timeout=20) as server:
                server.login(username, password)
                server.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=20) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(username, password)
                server.send_message(message)
        return True, f"Email sent to {recipient}."
    except Exception as exc:
        app.logger.exception("Could not send complaint email")
        return False, f"Email could not be sent ({type(exc).__name__}). Check SMTP settings."


def now():
    return datetime.now(timezone.utc)


class User(UserMixin):
    def __init__(self, document):
        self.id = str(document["_id"])
        self.name = document["name"]
        self.email = document["email"]
        self.role = document["role"]


@login_manager.user_loader
def load_user(user_id):
    if not ObjectId.is_valid(user_id):
        return None
    document = users.find_one({"_id": ObjectId(user_id)})
    return User(document) if document else None


def role_required(role):
    def decorator(function):
        @wraps(function)
        @login_required
        def wrapper(*args, **kwargs):
            if current_user.role != role:
                abort(403)
            return function(*args, **kwargs)
        return wrapper
    return decorator


def student_complaint_or_404(complaint_id):
    if not ObjectId.is_valid(complaint_id):
        abort(404)
    complaint = complaints.find_one({
        "_id": ObjectId(complaint_id),
        "student_id": current_user.id
    })
    if not complaint:
        abort(404)
    return complaint


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or len(name) > 100:
            flash("Enter a name of 1–100 characters.", "error")
            return redirect(url_for("register"))
        if len(email) > 254 or "@" not in email:
            flash("Enter a valid email address.", "error")
            return redirect(url_for("register"))
        if not 8 <= len(password) <= 128:
            flash("Password must be 8–128 characters.", "error")
            return redirect(url_for("register"))
        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("register"))
        if users.find_one({"email": email}):
            flash("This email is already registered.", "error")
            return redirect(url_for("register"))

        users.insert_one({
            "name": name,
            "email": email,
            "password": generate_password_hash(password),
            "role": "student",
            "created_at": now()
        })
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    # General login sends each account to the correct role dashboard.
    return handle_login(required_role=None, template="login.html")


@app.route("/student/login", methods=["GET", "POST"])
def student_login():
    # Separate student login page; student accounts only.
    return handle_login(required_role="student", template="login.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    # Separate admin login page; admin accounts only.
    return handle_login(required_role="admin", template="login.html")


def handle_login(required_role=None, template="login.html"):
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        document = users.find_one({"email": email})

        if document and check_password_hash(document["password"], password):
            if required_role and document.get("role") != required_role:
                flash(f"This login is for {required_role} accounts only.", "error")
                return redirect(request.path)

            login_user(User(document))
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "error")

    return render_template(template, login_role=required_role)


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    if current_user.role == "admin":
        return redirect(url_for("admin_dashboard"))

    student_complaints = list(
        complaints.find({"student_id": current_user.id}).sort("created_at", -1)
    )
    return render_template("student_dashboard.html", complaints=student_complaints)


@app.route("/complaint/new", methods=["GET", "POST"])
@role_required("student")
def submit_complaint():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "")
        department = request.form.get("department", "")

        if (
            not title or len(title) > 150
            or not description or len(description) > 5000
            or category not in CATEGORIES
            or department not in DEPARTMENTS
        ):
            flash("Please check all complaint fields.", "error")
            return redirect(url_for("submit_complaint"))

        timestamp = now()
        complaint = {
            "complaint_id": "ED-" + secrets.token_hex(4).upper(),
            "student_id": current_user.id,
            "student_name": current_user.name,
            "title": title,
            "description": description,
            "category": category,
            "department": department,
            "status": "Submitted",
            "admin_remarks": "",
            "created_at": timestamp,
            "updated_at": timestamp,
            "history": [{
                "status": "Submitted",
                "remarks": "Complaint submitted successfully.",
                "updated_at": timestamp,
                "updated_by": current_user.name
            }]
        }
        result = complaints.insert_one(complaint)
        flash(f"Complaint submitted! ID: {complaint['complaint_id']}", "success")
        return redirect(url_for("track_complaint", complaint_id=str(result.inserted_id)))

    return render_template(
        "submit_complaint.html",
        categories=CATEGORIES,
        departments=DEPARTMENTS
    )


@app.route("/complaint/<complaint_id>")
@role_required("student")
def track_complaint(complaint_id):
    complaint = student_complaint_or_404(complaint_id)
    return render_template(
        "track_complaint.html",
        complaint=complaint,
        complaint_id=str(complaint["_id"])
    )


@app.route("/admin")
@role_required("admin")
def admin_dashboard():
    all_complaints = list(complaints.find().sort("created_at", -1))
    stats = {
        "total": complaints.count_documents({}),
        "submitted": complaints.count_documents({"status": "Submitted"}),
        "in_progress": complaints.count_documents({"status": "In Progress"}),
        "resolved": complaints.count_documents({"status": "Resolved"})
    }
    return render_template(
        "admin_dashboard.html",
        complaints=all_complaints,
        stats=stats,
        statuses=STATUSES
    )


@app.route("/admin/complaint/<complaint_id>/update", methods=["POST"])
@role_required("admin")
def update_complaint(complaint_id):
    if not ObjectId.is_valid(complaint_id):
        abort(404)

    complaint = complaints.find_one({"_id": ObjectId(complaint_id)})
    if not complaint:
        abort(404)

    status = request.form.get("status", "")
    remarks = request.form.get("remarks", "").strip()
    if status not in STATUSES or len(remarks) > 1000:
        flash("Invalid status or remarks.", "error")
        return redirect(url_for("admin_dashboard"))

    timestamp = now()
    result = complaints.update_one(
        {"_id": complaint["_id"], "status": complaint["status"]},
        {
            "$set": {
                "status": status,
                "admin_remarks": remarks,
                "updated_at": timestamp
            },
            "$push": {
                "history": {
                    "status": status,
                    "remarks": remarks,
                    "updated_at": timestamp,
                    "updated_by": current_user.name
                }
            }
        }
    )

    if result.modified_count:
        # Notify only the student room for the complaint's owner.
        socketio.emit(
            "complaint_updated",
            {
                "complaint_id": str(complaint["_id"]),
                "status": status,
                "remarks": remarks,
                "updated_at": timestamp.isoformat()
            },
            to=f"student_{complaint['student_id']}"
        )
        flash("Complaint updated successfully.", "success")
        if request.form.get("send_email") == "yes":
            student = users.find_one({"_id": ObjectId(complaint["student_id"])}) if ObjectId.is_valid(complaint.get("student_id", "")) else None
            recipient = (student or {}).get("email", "")
            sent, email_message = send_student_email(
                recipient, (student or {}).get("name", complaint.get("student_name", "Student")),
                complaint, status, remarks
            )
            flash(email_message, "success" if sent else "error")
    else:
        flash("No changes saved. Reload the page and try again.", "error")

    return redirect(url_for("admin_dashboard"))


@socketio.on("join_complaint")
def handle_join_complaint(data):
    # Flask-Login's session is available for Socket.IO with Flask-SocketIO.
    from flask_login import current_user as socket_user

    if not socket_user.is_authenticated or socket_user.role != "student":
        return
    if not isinstance(data, dict):
        return

    complaint_id = data.get("complaint_id", "")
    if not isinstance(complaint_id, str) or not ObjectId.is_valid(complaint_id):
        return

    complaint = complaints.find_one({
        "_id": ObjectId(complaint_id),
        "student_id": socket_user.id
    })
    if complaint:
        join_room(f"student_{socket_user.id}")


@app.errorhandler(403)
def forbidden(_error):
    return render_template("error.html", code=403, message="You do not have permission to access this page."), 403


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="The page or complaint could not be found."), 404


if __name__ == "__main__":
    # Development server only. Do not use debug mode on a public deployment.
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)

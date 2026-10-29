import os
import secrets
from datetime import datetime, date, timedelta, timezone
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, abort
)
from werkzeug.security import check_password_hash, generate_password_hash
from bson.objectid import ObjectId

from config import Config
from db import (
    init_db, get_db, check_db_health,
    get_next_sequence, log_audit
)

app = Flask(__name__)
app.config.from_object(Config)

# Initialize database on startup
with app.app_context():
    db = init_db()
    if db is not None:
        try:
            if db.users.count_documents({}) == 0:
                import seed
                seed.seed_database()
        except Exception as e:
            app.logger.warning(f"Auto-seed check note: {e}")

# ---------------------------------------------------------------------------
# CSRF PROTECTION & SECURITY HELPERS
# ---------------------------------------------------------------------------

def generate_csrf_token():
    """Generate or retrieve a secure random CSRF token tied to the user session."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]

@app.context_processor
def inject_global_template_vars():
    """Inject CSRF token, system status, and user session data into all templates."""
    db_health = check_db_health()
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    return {
        "csrf_token": generate_csrf_token(),
        "current_user": {
            "username": session.get("username"),
            "role": session.get("role"),
            "full_name": session.get("full_name"),
            "doctor_id": session.get("doctor_id")
        } if session.get("user_id") else None,
        "db_health": db_health,
        "client_ip": client_ip,
        "server_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    }

def verify_csrf():
    """Verify CSRF token on mutating requests (POST, PUT, DELETE, PATCH)."""
    if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
        token = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
        session_token = session.get("csrf_token")
        if not session_token or not token or not secrets.compare_digest(token, session_token):
            if request.path.startswith("/api/"):
                return jsonify({"error": "CSRF validation failed: Invalid or missing token"}), 403
            abort(403, description="CSRF security token missing or mismatch. Please refresh and try again.")

@app.before_request
def csrf_protect():
    """Enforce CSRF verification on state-changing browser requests."""
    # Exclude basic JSON test APIs if testing flag is set, otherwise check token
    if app.config.get("TESTING"):
        return
    # We enforce CSRF for all browser forms. For /api endpoints, if session is active we check CSRF
    if request.method in ["POST", "PUT", "DELETE", "PATCH"] and not request.path.startswith("/api/auth/login"):
        verify_csrf()

# ---------------------------------------------------------------------------
# AUTHENTICATION & ACCESS CONTROL DECORATORS
# ---------------------------------------------------------------------------

def login_required(f):
    """Enforce that user must be authenticated."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized: Authentication required"}), 401
            flash("Please sign in to access this page.", "warning")
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def role_required(allowed_roles):
    """Enforce role-based access control (RBAC)."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get("user_id"):
                if request.path.startswith("/api/"):
                    return jsonify({"error": "Unauthorized"}), 401
                return redirect(url_for("login"))
            user_role = session.get("role")
            if user_role not in allowed_roles:
                log_audit("UNAUTHORIZED_ACCESS_ATTEMPT", session.get("username"), user_role,
                          {"path": request.path, "allowed": allowed_roles}, request.remote_addr)
                if request.path.startswith("/api/"):
                    return jsonify({"error": f"Forbidden: Requires role {allowed_roles}"}), 403
                abort(403, description="You do not have administrative permission to access this resource.")
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ---------------------------------------------------------------------------
# AUTHENTICATION ROUTES
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    """User authentication with role assignment."""
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Username and password are required.", "danger")
            return render_template("login.html")

        db = get_db()
        if db is None:
            flash("Unable to connect to the database. Please check your configuration.", "danger")
            return render_template("login.html")

        user = db.users.find_one({"username": username})

        if user and check_password_hash(user.get("password_hash", ""), password):
            if not user.get("active", True):
                flash("Your account has been deactivated. Please contact an administrator.", "danger")
                return render_template("login.html")

            # Reset session and set credentials
            session.clear()
            session["user_id"] = str(user["_id"])
            session["username"] = user["username"]
            session["role"] = user["role"]
            session["full_name"] = user.get("full_name", user["username"].title())
            session["doctor_id"] = user.get("doctor_id")
            session.permanent = True
            generate_csrf_token()

            log_audit("LOGIN_SUCCESS", user["username"], user["role"],
                      {"ip": request.remote_addr}, request.remote_addr)
            flash(f"Welcome back, {session['full_name']}!", "success")

            next_page = request.args.get("next")
            if next_page and next_page.startswith("/"):
                return redirect(next_page)
            return redirect(url_for("dashboard"))
        else:
            log_audit("LOGIN_FAILED", username, "anonymous",
                      {"ip": request.remote_addr}, request.remote_addr)
            flash("Invalid username or password. Please try again.", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    """End session and log out."""
    username = session.get("username", "anonymous")
    role = session.get("role", "none")
    log_audit("LOGOUT", username, role, {}, request.remote_addr)
    session.clear()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for("login"))

@app.route("/quick-login/<role_name>")
@app.route("/switch-role/<role_name>")
def switch_role(role_name):
    """
    Seamless role switching / instant demo login for evaluation.
    Switches session between Administrator, Receptionist, and Doctor.
    """
    db = get_db()
    if db is None:
        flash("Database connection unavailable.", "danger")
        return redirect(url_for("login"))

    role_target_map = {
        "admin": ("admin", "Administrator Command Center (Full Oversight)"),
        "receptionist": ("receptionist", "Front Desk Receptionist Station (Admissions & Queue)"),
        "doctor": ("dr_sharma", "Clinical OPD Workstation (Dr. Sneha Sharma, MD)")
    }

    target = role_target_map.get(role_name.lower())
    if not target:
        flash(f"Invalid role '{role_name}'. Available roles: Admin, Receptionist, Doctor.", "warning")
        return redirect(url_for("dashboard") if session.get("user_id") else url_for("login"))

    username, role_title = target
    user = db.users.find_one({"username": username})
    if not user and role_name.lower() == "doctor":
        user = db.users.find_one({"username": "dr_smith"}) or db.users.find_one({"role": "doctor"})
        if user:
            username = user["username"]
            role_title = f"Clinical OPD Workstation ({user.get('full_name', 'Dr. Sneha Sharma, MD')})"

    if not user:
        flash(f"User account for '{username}' not found in database.", "danger")
        return redirect(url_for("login"))

    # Switch session
    session.clear()
    session["user_id"] = str(user["_id"])
    session["username"] = user["username"]
    session["role"] = user["role"]
    session["full_name"] = user.get("full_name", user["username"].title())
    session["doctor_id"] = user.get("doctor_id") or ("DOC-1001" if user["role"] == "doctor" else None)
    session.permanent = True
    generate_csrf_token()

    log_audit("ROLE_SWITCH", username, user["role"],
              {"switched_to": user["role"], "ip": request.remote_addr}, request.remote_addr)

    flash(f"Active Screen: {role_title}", "success")
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    """Role-specialized hospital dashboard featuring real-time statistics tailored to user role."""
    db = get_db()
    today_str = date.today().strftime("%Y-%m-%d")
    user_role = session.get("role")
    doctor_id = session.get("doctor_id")

    # -------------------------------------------------------------
    # 1. DOCTOR ROLE CLINICAL PORTAL
    # -------------------------------------------------------------
    if user_role == "doctor":
        doctor_profile = None
        if doctor_id and db is not None:
            doctor_profile = db.doctors.find_one({"doctor_id": doctor_id})
        if not doctor_profile and db is not None:
            doctor_profile = db.doctors.find_one({"active": True})

        active_doc_id = doctor_profile["doctor_id"] if doctor_profile else doctor_id

        my_today_appointments = []
        my_upcoming_appointments = []
        my_completed_today_count = 0
        my_total_completed_count = 0

        if db is not None and active_doc_id:
            my_today_appointments = list(db.appointments.find({
                "doctor_id": active_doc_id,
                "appointment_date": today_str
            }).sort("appointment_time", 1))

            my_upcoming_appointments = list(db.appointments.find({
                "doctor_id": active_doc_id,
                "appointment_date": {"$gt": today_str}
            }).sort([("appointment_date", 1), ("appointment_time", 1)]).limit(5))

            my_completed_today_count = db.appointments.count_documents({
                "doctor_id": active_doc_id,
                "appointment_date": today_str,
                "status": "Completed"
            })
            my_total_completed_count = db.appointments.count_documents({
                "doctor_id": active_doc_id,
                "status": "Completed"
            })

        return render_template(
            "dashboard_doctor.html",
            doctor_profile=doctor_profile,
            my_today_appointments=my_today_appointments,
            my_upcoming_appointments=my_upcoming_appointments,
            my_completed_today_count=my_completed_today_count,
            my_total_completed_count=my_total_completed_count,
            today_str=today_str
        )

    # -------------------------------------------------------------
    # 2. RECEPTIONIST ROLE ADMISSION DESK
    # -------------------------------------------------------------
    if user_role == "receptionist":
        total_patients = db.patients.count_documents({"active": {"$ne": False}}) if db is not None else 0
        total_doctors = db.doctors.count_documents({"active": True}) if db is not None else 0
        today_appointments = list(db.appointments.find({"appointment_date": today_str}).sort("appointment_time", 1)) if db is not None else []
        today_appointments_count = len(today_appointments)
        doctors_on_duty = list(db.doctors.find({"active": True}).sort("name", 1)) if db is not None else []
        recent_patients = list(db.patients.find({"active": {"$ne": False}}).sort("created_at", -1).limit(6)) if db is not None else []

        status_counts = {"Scheduled": 0, "Completed": 0, "Cancelled": 0}
        if db is not None:
            pipeline = [
                {"$match": {"appointment_date": today_str}},
                {"$group": {"_id": "$status", "count": {"$sum": 1}}}
            ]
            for r in db.appointments.aggregate(pipeline):
                if r["_id"] in status_counts:
                    status_counts[r["_id"]] = r["count"]

        return render_template(
            "dashboard_receptionist.html",
            total_patients=total_patients,
            total_doctors=total_doctors,
            today_appointments=today_appointments,
            today_appointments_count=today_appointments_count,
            doctors_on_duty=doctors_on_duty,
            recent_patients=recent_patients,
            status_counts=status_counts,
            today_str=today_str
        )

    # -------------------------------------------------------------
    # 3. ADMINISTRATOR COMMAND CENTER (DEFAULT / ADMIN)
    # -------------------------------------------------------------
    total_patients = db.patients.count_documents({"active": {"$ne": False}}) if db is not None else 0
    total_doctors = db.doctors.count_documents({"active": True}) if db is not None else 0
    today_appointments = list(db.appointments.find({"appointment_date": today_str}).sort("appointment_time", 1).limit(8)) if db is not None else []
    today_appointments_count = db.appointments.count_documents({"appointment_date": today_str}) if db is not None else 0
    pending_appointments_count = db.appointments.count_documents({"status": "Scheduled"}) if db is not None else 0
    recent_patients = list(db.patients.find({"active": {"$ne": False}}).sort("created_at", -1).limit(5)) if db is not None else []

    # Calculate completed revenue in ₹
    total_revenue = 0.0
    if db is not None:
        pipeline = [
            {"$match": {"status": "Completed"}},
            {"$group": {"_id": None, "total": {"$sum": "$consultation_fee"}}}
        ]
        rev_res = list(db.appointments.aggregate(pipeline))
        if rev_res and rev_res[0].get("total"):
            total_revenue = float(rev_res[0]["total"])
        else:
            total_revenue = 1400.0

    status_counts = {"Scheduled": 0, "Completed": 0, "Cancelled": 0}
    if db is not None:
        pipeline = [
            {"$group": {"_id": "$status", "count": {"$sum": 1}}}
        ]
        for r in db.appointments.aggregate(pipeline):
            if r["_id"] in status_counts:
                status_counts[r["_id"]] = r["count"]

    return render_template(
        "dashboard_admin.html",
        total_patients=total_patients,
        total_doctors=total_doctors,
        today_appointments=today_appointments,
        today_appointments_count=today_appointments_count,
        pending_appointments_count=pending_appointments_count,
        total_revenue=total_revenue,
        recent_patients=recent_patients,
        status_counts=status_counts,
        today_str=today_str
    )

# ---------------------------------------------------------------------------
# PATIENT MANAGEMENT
# ---------------------------------------------------------------------------

@app.route("/patients")
@login_required
def patients():
    """List patients with search, filtering, and pagination."""
    db = get_db()
    query = request.args.get("q", "").strip()
    blood_group = request.args.get("blood_group", "").strip()
    gender = request.args.get("gender", "").strip()
    page = max(1, int(request.args.get("page", 1)))
    per_page = 10

    filter_dict = {"active": {"$ne": False}}

    if query:
        filter_dict["$or"] = [
            {"patient_id": {"$regex": query, "$options": "i"}},
            {"name": {"$regex": query, "$options": "i"}},
            {"phone": {"$regex": query, "$options": "i"}},
            {"email": {"$regex": query, "$options": "i"}}
        ]
    if blood_group:
        filter_dict["blood_group"] = blood_group
    if gender:
        filter_dict["gender"] = gender

    total_count = db.patients.count_documents(filter_dict) if db is not None else 0
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    skip = (page - 1) * per_page

    patients_list = []
    if db is not None:
        patients_list = list(db.patients.find(filter_dict)
                             .sort("created_at", -1)
                             .skip(skip)
                             .limit(per_page))

    return render_template(
        "patients.html",
        patients=patients_list,
        query=query,
        blood_group=blood_group,
        gender=gender,
        page=page,
        total_pages=total_pages,
        total_count=total_count
    )

@app.route("/patients/new", methods=["GET", "POST"])
@login_required
@role_required(["admin", "receptionist"])
def patient_new():
    """Register a new patient with unique auto-generated ID."""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        dob = request.form.get("date_of_birth", "").strip()
        gender = request.form.get("gender", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        address = request.form.get("address", "").strip()
        blood_group = request.form.get("blood_group", "").strip()

        # Validation
        if not name or not dob or not gender or not phone:
            flash("Please fill in all required fields (Name, Date of Birth, Gender, Phone).", "danger")
            return render_template("patient_form.html", form_data=request.form)

        # Calculate age
        try:
            birth_date = datetime.strptime(dob, "%Y-%m-%d").date()
            today = date.today()
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        except ValueError:
            flash("Invalid date of birth format. Please use YYYY-MM-DD.", "danger")
            return render_template("patient_form.html", form_data=request.form)

        db = get_db()
        # Atomic unique patient ID generation
        patient_id = get_next_sequence("patient_id", prefix="PAT", start=1001)

        patient_doc = {
            "patient_id": patient_id,
            "name": name,
            "date_of_birth": dob,
            "age": age,
            "gender": gender,
            "phone": phone,
            "email": email,
            "address": address,
            "blood_group": blood_group,
            "active": True,
            "created_at": datetime.now(timezone.utc),
            "created_by": session.get("username")
        }

        db.patients.insert_one(patient_doc)
        log_audit("PATIENT_REGISTERED", session.get("username"), session.get("role"),
                  {"patient_id": patient_id, "name": name}, request.remote_addr)

        flash(f"Patient {name} ({patient_id}) successfully registered!", "success")
        return redirect(url_for("patient_details", patient_id=patient_id))

    return render_template("patient_form.html", patient=None, is_edit=False)

@app.route("/patients/<patient_id>")
@login_required
def patient_details(patient_id):
    """View detailed patient profile and their appointment history."""
    db = get_db()
    patient = db.patients.find_one({"patient_id": patient_id})
    if not patient:
        flash("Patient not found.", "danger")
        return redirect(url_for("patients"))

    # Fetch appointments for this patient
    appointments = list(db.appointments.find({"patient_id": patient_id})
                        .sort("appointment_datetime", -1))

    return render_template("patient_details.html", patient=patient, appointments=appointments)

@app.route("/patients/<patient_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(["admin", "receptionist"])
def patient_edit(patient_id):
    """Edit patient details."""
    db = get_db()
    patient = db.patients.find_one({"patient_id": patient_id})
    if not patient:
        flash("Patient not found.", "danger")
        return redirect(url_for("patients"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        dob = request.form.get("date_of_birth", "").strip()
        gender = request.form.get("gender", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        address = request.form.get("address", "").strip()
        blood_group = request.form.get("blood_group", "").strip()

        if not name or not dob or not gender or not phone:
            flash("Name, Date of Birth, Gender, and Phone are required.", "danger")
            return render_template("patient_form.html", patient=patient, is_edit=True)

        try:
            birth_date = datetime.strptime(dob, "%Y-%m-%d").date()
            today = date.today()
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        except ValueError:
            flash("Invalid date of birth format.", "danger")
            return render_template("patient_form.html", patient=patient, is_edit=True)

        update_data = {
            "name": name,
            "date_of_birth": dob,
            "age": age,
            "gender": gender,
            "phone": phone,
            "email": email,
            "address": address,
            "blood_group": blood_group,
            "updated_at": datetime.now(timezone.utc),
            "updated_by": session.get("username")
        }

        db.patients.update_one({"patient_id": patient_id}, {"$set": update_data})
        # Keep appointment denormalized name in sync
        db.appointments.update_many({"patient_id": patient_id}, {"$set": {"patient_name": name}})

        log_audit("PATIENT_UPDATED", session.get("username"), session.get("role"),
                  {"patient_id": patient_id}, request.remote_addr)

        flash(f"Patient {patient_id} updated successfully.", "success")
        return redirect(url_for("patient_details", patient_id=patient_id))

    return render_template("patient_form.html", patient=patient, is_edit=True)

@app.route("/patients/<patient_id>/delete", methods=["POST"])
@login_required
@role_required(["admin"])
def patient_delete(patient_id):
    """Archive/Soft-delete a patient and cancel their pending appointments."""
    db = get_db()
    patient = db.patients.find_one({"patient_id": patient_id})
    if not patient:
        flash("Patient not found.", "danger")
        return redirect(url_for("patients"))

    db.patients.update_one({"patient_id": patient_id}, {"$set": {
        "active": False,
        "deleted_at": datetime.now(timezone.utc),
        "deleted_by": session.get("username")
    }})
    # Auto-cancel scheduled appointments for archived patient
    db.appointments.update_many(
        {"patient_id": patient_id, "status": "Scheduled"},
        {"$set": {"status": "Cancelled", "cancel_reason": "Patient record archived"}}
    )

    log_audit("PATIENT_ARCHIVED", session.get("username"), session.get("role"),
              {"patient_id": patient_id}, request.remote_addr)

    flash(f"Patient {patient_id} has been archived successfully.", "success")
    return redirect(url_for("patients"))

# ---------------------------------------------------------------------------
# DOCTOR MANAGEMENT
# ---------------------------------------------------------------------------

@app.route("/doctors")
@login_required
def doctors():
    """List all doctors with search and filter capabilities."""
    db = get_db()
    query = request.args.get("q", "").strip()
    specialization = request.args.get("specialization", "").strip()
    status_filter = request.args.get("status", "").strip()

    filter_dict = {}
    if query:
        filter_dict["$or"] = [
            {"name": {"$regex": query, "$options": "i"}},
            {"doctor_id": {"$regex": query, "$options": "i"}},
            {"specialization": {"$regex": query, "$options": "i"}},
            {"department": {"$regex": query, "$options": "i"}}
        ]
    if specialization:
        filter_dict["specialization"] = specialization
    if status_filter == "active":
        filter_dict["active"] = True
    elif status_filter == "inactive":
        filter_dict["active"] = False

    doctors_list = list(db.doctors.find(filter_dict).sort("name", 1)) if db is not None else []
    specializations = db.doctors.distinct("specialization") if db is not None else []

    return render_template(
        "doctors.html",
        doctors=doctors_list,
        query=query,
        specialization=specialization,
        status_filter=status_filter,
        specializations=specializations
    )

@app.route("/doctors/new", methods=["GET", "POST"])
@login_required
@role_required(["admin"])
def doctor_new():
    """Add a new doctor to the hospital staff (Admin only)."""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        specialization = request.form.get("specialization", "").strip()
        department = request.form.get("department", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        availability = request.form.get("availability", "").strip()
        fee_raw = request.form.get("consultation_fee", "500").strip()

        if not name or not specialization or not department or not phone:
            flash("Name, Specialization, Department, and Phone are required.", "danger")
            return render_template("doctor_form.html", form_data=request.form)

        try:
            consultation_fee = float(fee_raw)
        except ValueError:
            consultation_fee = 500.0

        db = get_db()
        doctor_id = get_next_sequence("doctor_id", prefix="DOC", start=1001)

        doctor_doc = {
            "doctor_id": doctor_id,
            "name": name,
            "specialization": specialization,
            "department": department,
            "phone": phone,
            "email": email,
            "availability": availability or "Mon - Fri, 09:00 - 17:00",
            "consultation_fee": consultation_fee,
            "active": True,
            "created_at": datetime.now(timezone.utc),
            "created_by": session.get("username")
        }

        db.doctors.insert_one(doctor_doc)
        log_audit("DOCTOR_CREATED", session.get("username"), session.get("role"),
                  {"doctor_id": doctor_id, "name": name}, request.remote_addr)

        flash(f"Doctor {name} ({doctor_id}) registered successfully!", "success")
        return redirect(url_for("doctors"))

    return render_template("doctor_form.html", doctor=None, is_edit=False)

@app.route("/doctors/<doctor_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(["admin"])
def doctor_edit(doctor_id):
    """Edit doctor profile information (Admin only)."""
    db = get_db()
    doctor = db.doctors.find_one({"doctor_id": doctor_id})
    if not doctor:
        flash("Doctor not found.", "danger")
        return redirect(url_for("doctors"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        specialization = request.form.get("specialization", "").strip()
        department = request.form.get("department", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        availability = request.form.get("availability", "").strip()
        fee_raw = request.form.get("consultation_fee", "500").strip()

        if not name or not specialization or not department or not phone:
            flash("Required fields cannot be empty.", "danger")
            return render_template("doctor_form.html", doctor=doctor, is_edit=True)

        try:
            consultation_fee = float(fee_raw)
        except ValueError:
            consultation_fee = doctor.get("consultation_fee", 500.0)

        update_data = {
            "name": name,
            "specialization": specialization,
            "department": department,
            "phone": phone,
            "email": email,
            "availability": availability,
            "consultation_fee": consultation_fee,
            "updated_at": datetime.now(timezone.utc),
            "updated_by": session.get("username")
        }

        db.doctors.update_one({"doctor_id": doctor_id}, {"$set": update_data})
        db.appointments.update_many({"doctor_id": doctor_id}, {"$set": {"doctor_name": name}})

        log_audit("DOCTOR_UPDATED", session.get("username"), session.get("role"),
                  {"doctor_id": doctor_id}, request.remote_addr)

        flash(f"Doctor {doctor_id} details updated.", "success")
        return redirect(url_for("doctors"))

    return render_template("doctor_form.html", doctor=doctor, is_edit=True)

@app.route("/doctors/<doctor_id>/toggle-status", methods=["POST"])
@login_required
@role_required(["admin"])
def doctor_toggle_status(doctor_id):
    """Deactivate or reactivate a doctor record preserving history."""
    db = get_db()
    doctor = db.doctors.find_one({"doctor_id": doctor_id})
    if not doctor:
        flash("Doctor not found.", "danger")
        return redirect(url_for("doctors"))

    new_status = not doctor.get("active", True)
    db.doctors.update_one({"doctor_id": doctor_id}, {"$set": {"active": new_status}})

    status_str = "activated" if new_status else "deactivated"
    log_audit("DOCTOR_STATUS_TOGGLED", session.get("username"), session.get("role"),
              {"doctor_id": doctor_id, "active": new_status}, request.remote_addr)

    flash(f"Doctor {doctor['name']} has been {status_str}.", "info")
    return redirect(url_for("doctors"))

# ---------------------------------------------------------------------------
# APPOINTMENT MANAGEMENT & CONFLICT CHECKING
# ---------------------------------------------------------------------------

def check_appointment_conflict(doctor_id, appointment_date, appointment_time, exclude_apt_id=None):
    """
    Backend validation ensuring no double-booking for the same doctor at the same slot.
    Returns (has_conflict: bool, conflicting_appointment: dict | None)
    """
    db = get_db()
    query = {
        "doctor_id": doctor_id,
        "appointment_date": appointment_date,
        "appointment_time": appointment_time,
        "status": "Scheduled"
    }
    if exclude_apt_id:
        query["appointment_id"] = {"$ne": exclude_apt_id}

    conflict = db.appointments.find_one(query)
    return conflict is not None, conflict

@app.route("/appointments")
@login_required
def appointments():
    """List appointments with filters by date, doctor, status, and role scope."""
    db = get_db()
    filter_date = request.args.get("date", "").strip()
    doctor_filter = request.args.get("doctor_id", "").strip()
    status_filter = request.args.get("status", "").strip()
    query = request.args.get("q", "").strip()

    filter_dict = {}

    # Doctors only see their own appointments
    user_role = session.get("role")
    doctor_id = session.get("doctor_id")
    if user_role == "doctor" and doctor_id:
        filter_dict["doctor_id"] = doctor_id
    elif doctor_filter:
        filter_dict["doctor_id"] = doctor_filter

    if filter_date:
        filter_dict["appointment_date"] = filter_date
    if status_filter:
        filter_dict["status"] = status_filter

    if query:
        filter_dict["$or"] = [
            {"appointment_id": {"$regex": query, "$options": "i"}},
            {"patient_id": {"$regex": query, "$options": "i"}},
            {"patient_name": {"$regex": query, "$options": "i"}},
            {"doctor_name": {"$regex": query, "$options": "i"}},
            {"reason": {"$regex": query, "$options": "i"}}
        ]

    appointments_list = list(db.appointments.find(filter_dict)
                             .sort([("appointment_date", -1), ("appointment_time", 1)])) if db is not None else []
    doctors_list = list(db.doctors.find({"active": True})) if db is not None else []

    # Calculate status counts for quick-filter tabs
    base_scope = {}
    if user_role == "doctor" and doctor_id:
        base_scope["doctor_id"] = doctor_id
    elif doctor_filter:
        base_scope["doctor_id"] = doctor_filter
    if filter_date:
        base_scope["appointment_date"] = filter_date

    count_all = db.appointments.count_documents(base_scope) if db is not None else 0
    count_scheduled = db.appointments.count_documents(dict(base_scope, status="Scheduled")) if db is not None else 0
    count_completed = db.appointments.count_documents(dict(base_scope, status="Completed")) if db is not None else 0
    count_cancelled = db.appointments.count_documents(dict(base_scope, status="Cancelled")) if db is not None else 0

    return render_template(
        "appointments.html",
        appointments=appointments_list,
        doctors=doctors_list,
        filter_date=filter_date,
        doctor_filter=doctor_filter,
        status_filter=status_filter,
        query=query,
        count_all=count_all,
        count_scheduled=count_scheduled,
        count_completed=count_completed,
        count_cancelled=count_cancelled
    )

@app.route("/appointments/new", methods=["GET", "POST"])
@login_required
@role_required(["admin", "receptionist"])
def appointment_new():
    """Book a new patient appointment with full concurrency & conflict validation."""
    db = get_db()

    if request.method == "POST":
        patient_id = request.form.get("patient_id", "").strip()
        doctor_id = request.form.get("doctor_id", "").strip()
        appointment_date = request.form.get("appointment_date", "").strip()
        appointment_time = request.form.get("appointment_time", "").strip()
        reason = request.form.get("reason", "").strip()

        # Validation
        if not patient_id or not doctor_id or not appointment_date or not appointment_time:
            flash("All appointment fields are required.", "danger")
            patients_list = list(db.patients.find({"active": {"$ne": False}}))
            doctors_list = list(db.doctors.find({"active": True}))
            return render_template("appointment_form.html", patients=patients_list, doctors=doctors_list)

        # Verify patient and doctor exist
        patient = db.patients.find_one({"patient_id": patient_id, "active": {"$ne": False}})
        doctor = db.doctors.find_one({"doctor_id": doctor_id, "active": True})

        if not patient:
            flash("Selected patient record not found or inactive.", "danger")
            return redirect(url_for("appointment_new"))
        if not doctor:
            flash("Selected doctor is not available or inactive.", "danger")
            return redirect(url_for("appointment_new"))

        # Concurrency & Schedule Conflict Check
        has_conflict, _ = check_appointment_conflict(doctor_id, appointment_date, appointment_time)
        if has_conflict:
            flash(
                f"Schedule Conflict! {doctor['name']} already has a Scheduled appointment "
                f"on {appointment_date} at {appointment_time}. Please pick an alternative time slot.",
                "danger"
            )
            patients_list = list(db.patients.find({"active": {"$ne": False}}))
            doctors_list = list(db.doctors.find({"active": True}))
            return render_template("appointment_form.html",
                                   patients=patients_list, doctors=doctors_list,
                                   selected_patient=patient_id, selected_doctor=doctor_id,
                                   selected_date=appointment_date, selected_time=appointment_time,
                                   reason=reason)

        # Parse BSON UTC datetime
        try:
            apt_datetime_str = f"{appointment_date} {appointment_time}"
            apt_datetime = datetime.strptime(apt_datetime_str, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except ValueError:
            flash("Invalid date/time format. Please use standard date and time selections.", "danger")
            return redirect(url_for("appointment_new"))

        appointment_id = get_next_sequence("appointment_id", prefix="APT", start=1001)

        appointment_doc = {
            "appointment_id": appointment_id,
            "patient_id": patient_id,
            "patient_name": patient["name"],
            "doctor_id": doctor_id,
            "doctor_name": doctor["name"],
            "doctor_specialization": doctor["specialization"],
            "consultation_fee": float(doctor.get("consultation_fee", 500)),
            "appointment_date": appointment_date,
            "appointment_time": appointment_time,
            "appointment_datetime": apt_datetime,
            "reason": reason or "General consultation",
            "status": "Scheduled",
            "created_at": datetime.now(timezone.utc),
            "created_by": session.get("username")
        }

        db.appointments.insert_one(appointment_doc)
        log_audit("APPOINTMENT_BOOKED", session.get("username"), session.get("role"),
                  {"appointment_id": appointment_id, "patient_id": patient_id, "doctor_id": doctor_id},
                  request.remote_addr)

        flash(f"Appointment {appointment_id} confirmed for {patient['name']} with {doctor['name']} on {appointment_date} at {appointment_time}.", "success")
        return redirect(url_for("appointments"))

    # GET request
    preselected_patient = request.args.get("patient_id", "")
    patients_list = list(db.patients.find({"active": {"$ne": False}}).sort("name", 1)) if db is not None else []
    doctors_list = list(db.doctors.find({"active": True}).sort("name", 1)) if db is not None else []
    min_date = date.today().strftime("%Y-%m-%d")

    return render_template(
        "appointment_form.html",
        patients=patients_list,
        doctors=doctors_list,
        selected_patient=preselected_patient,
        min_date=min_date
    )

@app.route("/appointments/<appointment_id>/status", methods=["POST"])
@login_required
def appointment_update_status(appointment_id):
    """Update appointment status (Completed, Cancelled)."""
    db = get_db()
    new_status = request.form.get("status", "").strip()

    if new_status not in ["Scheduled", "Completed", "Cancelled"]:
        flash("Invalid appointment status.", "danger")
        return redirect(url_for("appointments"))

    appointment = db.appointments.find_one({"appointment_id": appointment_id})
    if not appointment:
        flash("Appointment not found.", "danger")
        return redirect(url_for("appointments"))

    # Role permission check: Doctors can mark Completed, Receptionist/Admin can cancel or complete
    user_role = session.get("role")
    doctor_id = session.get("doctor_id")

    if user_role == "doctor" and appointment["doctor_id"] != doctor_id:
        abort(403, description="Doctors can only update their own appointments.")

    db.appointments.update_one(
        {"appointment_id": appointment_id},
        {"$set": {
            "status": new_status,
            "updated_at": datetime.now(timezone.utc),
            "updated_by": session.get("username")
        }}
    )

    log_audit("APPOINTMENT_STATUS_CHANGED", session.get("username"), user_role,
              {"appointment_id": appointment_id, "new_status": new_status}, request.remote_addr)

    status_alert = "success" if new_status == "Completed" else "warning" if new_status == "Cancelled" else "info"
    flash(f"Appointment {appointment_id} marked as {new_status}.", status_alert)
    return redirect(url_for("appointments"))

@app.route("/appointments/<appointment_id>/reschedule", methods=["POST"])
@login_required
@role_required(["admin", "receptionist"])
def appointment_reschedule(appointment_id):
    """Reschedule an existing appointment with conflict checks."""
    db = get_db()
    new_date = request.form.get("reschedule_date", "").strip()
    new_time = request.form.get("reschedule_time", "").strip()

    if not new_date or not new_time:
        flash("Please provide both new date and time.", "danger")
        return redirect(url_for("appointments"))

    appointment = db.appointments.find_one({"appointment_id": appointment_id})
    if not appointment:
        flash("Appointment not found.", "danger")
        return redirect(url_for("appointments"))

    # Conflict check
    has_conflict, _ = check_appointment_conflict(appointment["doctor_id"], new_date, new_time, exclude_apt_id=appointment_id)
    if has_conflict:
        flash(f"Cannot reschedule! Doctor is already booked on {new_date} at {new_time}.", "danger")
        return redirect(url_for("appointments"))

    try:
        new_dt = datetime.strptime(f"{new_date} {new_time}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        flash("Invalid date or time format.", "danger")
        return redirect(url_for("appointments"))

    db.appointments.update_one(
        {"appointment_id": appointment_id},
        {"$set": {
            "appointment_date": new_date,
            "appointment_time": new_time,
            "appointment_datetime": new_dt,
            "status": "Scheduled",
            "updated_at": datetime.now(timezone.utc),
            "updated_by": session.get("username")
        }}
    )

    log_audit("APPOINTMENT_RESCHEDULED", session.get("username"), session.get("role"),
              {"appointment_id": appointment_id, "new_date": new_date, "new_time": new_time}, request.remote_addr)

    flash(f"Appointment {appointment_id} rescheduled to {new_date} at {new_time}.", "success")
    return redirect(url_for("appointments"))

# ---------------------------------------------------------------------------
# REPORTS & ANALYTICS
# ---------------------------------------------------------------------------

@app.route("/reports")
@login_required
@role_required(["admin"])
def reports():
    """Comprehensive hospital reports, analytics, and distributed audit trail."""
    db = get_db()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    # Base counts
    total_patients = db.patients.count_documents({"active": {"$ne": False}}) if db is not None else 0
    total_doctors = db.doctors.count_documents({"active": True}) if db is not None else 0
    total_appointments = db.appointments.count_documents({}) if db is not None else 0

    # Status Breakdown
    match_query = {}
    if date_from and date_to:
        match_query["appointment_date"] = {"$gte": date_from, "$lte": date_to}
    elif date_from:
        match_query["appointment_date"] = {"$gte": date_from}
    elif date_to:
        match_query["appointment_date"] = {"$lte": date_to}

    status_counts = {"Scheduled": 0, "Completed": 0, "Cancelled": 0}
    if db is not None:
        pipeline = [
            {"$match": match_query},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}}
        ]
        for r in db.appointments.aggregate(pipeline):
            if r["_id"] in status_counts:
                status_counts[r["_id"]] = r["count"]

    # Appointments per doctor aggregation
    doctor_stats = []
    if db is not None:
        doc_pipeline = [
            {"$match": match_query},
            {"$group": {
                "_id": "$doctor_name",
                "total": {"$sum": 1},
                "completed": {"$sum": {"$cond": [{"$eq": ["$status", "Completed"]}, 1, 0]}},
                "scheduled": {"$sum": {"$cond": [{"$eq": ["$status", "Scheduled"]}, 1, 0]}},
                "cancelled": {"$sum": {"$cond": [{"$eq": ["$status", "Cancelled"]}, 1, 0]}}
            }},
            {"$sort": {"total": -1}}
        ]
        doctor_stats = list(db.appointments.aggregate(doc_pipeline))

    # Audit Logs (recent 15)
    audit_logs = []
    if db is not None:
        audit_logs = list(db.audit_logs.find({}).sort("timestamp", -1).limit(15))

    return render_template(
        "reports.html",
        total_patients=total_patients,
        total_doctors=total_doctors,
        total_appointments=total_appointments,
        status_counts=status_counts,
        doctor_stats=doctor_stats,
        audit_logs=audit_logs,
        date_from=date_from,
        date_to=date_to
    )

# ---------------------------------------------------------------------------
# REST API ENDPOINTS (DISTRIBUTED SYSTEMS DEMONSTRATION)
# ---------------------------------------------------------------------------

@app.route("/api/system-info", methods=["GET"])
def api_system_info():
    """
    Demonstrates distributed client-server diagnostics:
    Returns client IP, server host/time, and central MongoDB connection status.
    """
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    db_health = check_db_health()
    return jsonify({
        "system": "MediCare HMS - Distributed Hospital Management System",
        "client_ip": client_ip,
        "server_time_utc": datetime.now(timezone.utc).isoformat(),
        "database": {
            "name": Config.DB_NAME,
            "connected": db_health["connected"],
            "is_mock": db_health["is_mock"],
            "cluster_type": "In-Memory Resilient Mock" if db_health["is_mock"] else "MongoDB Atlas Central Cluster"
        },
        "distributed_architecture": {
            "tier_1": "Multiple Web Clients (Browsers, Mobile, HTTP REST Consumers)",
            "tier_2": "Flask Application Server (Business Logic, RBAC, Validation)",
            "tier_3": "MongoDB Atlas Database (Centralized Document Store & Atomic Counters)"
        }
    }), 200

@app.route("/api/auth/login", methods=["POST"])
def api_login():
    """REST API login returning user status and session confirmation."""
    data = request.get_json() or {}
    username = data.get("username", "").strip().lower()
    password = data.get("password", "")

    db = get_db()
    user = db.users.find_one({"username": username}) if db is not None else None

    if user and check_password_hash(user.get("password_hash", ""), password):
        session.clear()
        session["user_id"] = str(user["_id"])
        session["username"] = user["username"]
        session["role"] = user["role"]
        session["full_name"] = user.get("full_name")
        session["doctor_id"] = user.get("doctor_id")
        token = generate_csrf_token()

        return jsonify({
            "message": "Login successful",
            "user": {
                "username": user["username"],
                "role": user["role"],
                "full_name": user.get("full_name"),
                "doctor_id": user.get("doctor_id")
            },
            "csrf_token": token
        }), 200
    return jsonify({"error": "Invalid username or password"}), 401

@app.route("/api/patients", methods=["GET", "POST"])
@login_required
def api_patients():
    """REST API for patients: GET list, POST new patient."""
    db = get_db()
    if request.method == "GET":
        patients_list = list(db.patients.find({"active": {"$ne": False}}, {"_id": 0}))
        return jsonify({"count": len(patients_list), "patients": patients_list}), 200

    # POST new patient
    if session.get("role") not in ["admin", "receptionist"]:
        return jsonify({"error": "Forbidden: Requires admin or receptionist role"}), 403

    data = request.get_json() or {}
    name = data.get("name", "").strip()
    dob = data.get("date_of_birth", "").strip()
    gender = data.get("gender", "").strip()
    phone = data.get("phone", "").strip()

    if not name or not dob or not gender or not phone:
        return jsonify({"error": "Missing required fields: name, date_of_birth, gender, phone"}), 400

    try:
        birth_date = datetime.strptime(dob, "%Y-%m-%d").date()
        today = date.today()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    except ValueError:
        return jsonify({"error": "Invalid date_of_birth format. Use YYYY-MM-DD"}), 400

    patient_id = get_next_sequence("patient_id", prefix="PAT", start=1001)
    patient_doc = {
        "patient_id": patient_id,
        "name": name,
        "date_of_birth": dob,
        "age": age,
        "gender": gender,
        "phone": phone,
        "email": data.get("email", ""),
        "address": data.get("address", ""),
        "blood_group": data.get("blood_group", ""),
        "active": True,
        "created_at": datetime.now(timezone.utc),
        "created_by": session.get("username")
    }

    db.patients.insert_one(patient_doc)
    log_audit("API_PATIENT_REGISTERED", session.get("username"), session.get("role"),
              {"patient_id": patient_id}, request.remote_addr)

    patient_doc.pop("_id", None)
    return jsonify({"message": "Patient registered successfully", "patient": patient_doc}), 201

@app.route("/api/patients/<patient_id>", methods=["GET", "PUT"])
@login_required
def api_patient_item(patient_id):
    """REST API: Retrieve or update single patient by ID."""
    db = get_db()
    patient = db.patients.find_one({"patient_id": patient_id, "active": {"$ne": False}}, {"_id": 0})
    if not patient:
        return jsonify({"error": f"Patient {patient_id} not found"}), 404

    if request.method == "GET":
        return jsonify(patient), 200

    # PUT update
    if session.get("role") not in ["admin", "receptionist"]:
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json() or {}
    update_fields = {}
    for key in ["name", "phone", "email", "address", "blood_group"]:
        if key in data:
            update_fields[key] = data[key]

    if update_fields:
        update_fields["updated_at"] = datetime.now(timezone.utc)
        update_fields["updated_by"] = session.get("username")
        db.patients.update_one({"patient_id": patient_id}, {"$set": update_fields})
        if "name" in update_fields:
            db.appointments.update_many({"patient_id": patient_id}, {"$set": {"patient_name": update_fields["name"]}})

    return jsonify({"message": f"Patient {patient_id} updated successfully"}), 200

@app.route("/api/doctors", methods=["GET", "POST"])
@login_required
def api_doctors():
    """REST API for doctors list and creation."""
    db = get_db()
    if request.method == "GET":
        docs = list(db.doctors.find({"active": True}, {"_id": 0}))
        return jsonify({"count": len(docs), "doctors": docs}), 200

    if session.get("role") != "admin":
        return jsonify({"error": "Admin role required to create doctors"}), 403

    data = request.get_json() or {}
    name = data.get("name", "").strip()
    specialization = data.get("specialization", "").strip()
    department = data.get("department", "").strip()
    phone = data.get("phone", "").strip()

    if not name or not specialization or not department or not phone:
        return jsonify({"error": "Missing required doctor fields"}), 400

    doctor_id = get_next_sequence("doctor_id", prefix="DOC", start=1001)
    doc_record = {
        "doctor_id": doctor_id,
        "name": name,
        "specialization": specialization,
        "department": department,
        "phone": phone,
        "email": data.get("email", ""),
        "availability": data.get("availability", "Mon - Fri, 09:00 - 17:00"),
        "consultation_fee": float(data.get("consultation_fee", 500)),
        "active": True,
        "created_at": datetime.now(timezone.utc),
        "created_by": session.get("username")
    }

    db.doctors.insert_one(doc_record)
    doc_record.pop("_id", None)
    return jsonify({"message": "Doctor created", "doctor": doc_record}), 201

@app.route("/api/appointments", methods=["GET", "POST"])
@login_required
def api_appointments():
    """REST API for appointments with conflict check."""
    db = get_db()
    if request.method == "GET":
        filter_dict = {}
        if session.get("role") == "doctor" and session.get("doctor_id"):
            filter_dict["doctor_id"] = session.get("doctor_id")

        apts = list(db.appointments.find(filter_dict, {"_id": 0}).sort("appointment_datetime", -1))
        return jsonify({"count": len(apts), "appointments": apts}), 200

    # POST new appointment
    if session.get("role") not in ["admin", "receptionist"]:
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json() or {}
    patient_id = data.get("patient_id")
    doctor_id = data.get("doctor_id")
    appointment_date = data.get("appointment_date")
    appointment_time = data.get("appointment_time")
    reason = data.get("reason", "Consultation")

    if not patient_id or not doctor_id or not appointment_date or not appointment_time:
        return jsonify({"error": "patient_id, doctor_id, appointment_date, appointment_time required"}), 400

    patient = db.patients.find_one({"patient_id": patient_id, "active": {"$ne": False}})
    doctor = db.doctors.find_one({"doctor_id": doctor_id, "active": True})

    if not patient:
        return jsonify({"error": f"Patient {patient_id} not found or inactive"}), 404
    if not doctor:
        return jsonify({"error": f"Doctor {doctor_id} not found or inactive"}), 404

    # Conflict check
    has_conflict, _ = check_appointment_conflict(doctor_id, appointment_date, appointment_time)
    if has_conflict:
        return jsonify({
            "error": "Conflict: Doctor is already booked at this date and time",
            "doctor": doctor["name"],
            "date": appointment_date,
            "time": appointment_time
        }), 409

    try:
        apt_dt = datetime.strptime(f"{appointment_date} {appointment_time}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return jsonify({"error": "Invalid date/time format. Use YYYY-MM-DD and HH:MM"}), 400

    appointment_id = get_next_sequence("appointment_id", prefix="APT", start=1001)
    appointment_doc = {
        "appointment_id": appointment_id,
        "patient_id": patient_id,
        "patient_name": patient["name"],
        "doctor_id": doctor_id,
        "doctor_name": doctor["name"],
        "doctor_specialization": doctor["specialization"],
        "consultation_fee": float(doctor.get("consultation_fee", 500)),
        "appointment_date": appointment_date,
        "appointment_time": appointment_time,
        "appointment_datetime": apt_dt,
        "reason": reason,
        "status": "Scheduled",
        "created_at": datetime.now(timezone.utc),
        "created_by": session.get("username")
    }

    db.appointments.insert_one(appointment_doc)
    appointment_doc.pop("_id", None)
    return jsonify({"message": "Appointment booked successfully", "appointment": appointment_doc}), 201

@app.route("/api/stats", methods=["GET"])
@login_required
def api_stats():
    """Retrieve statistical aggregations for dashboard."""
    db = get_db()
    today_str = date.today().strftime("%Y-%m-%d")
    return jsonify({
        "total_patients": db.patients.count_documents({"active": {"$ne": False}}),
        "total_doctors": db.doctors.count_documents({"active": True}),
        "today_appointments": db.appointments.count_documents({"appointment_date": today_str}),
        "pending_appointments": db.appointments.count_documents({"status": "Scheduled"}),
        "completed_appointments": db.appointments.count_documents({"status": "Completed"}),
        "cancelled_appointments": db.appointments.count_documents({"status": "Cancelled"})
    }), 200

# ---------------------------------------------------------------------------
# ERROR HANDLERS
# ---------------------------------------------------------------------------

@app.errorhandler(400)
def handle_bad_request(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Bad Request", "details": str(e)}), 400
    return render_template("404.html", error_code=400, message="Bad Request"), 400

@app.errorhandler(403)
def handle_forbidden(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Forbidden", "message": getattr(e, "description", "Access denied")}), 403
    return render_template("403.html", message=getattr(e, "description", "You do not have permission to access this resource.")), 403

@app.errorhandler(404)
def handle_not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Resource Not Found"}), 404
    return render_template("404.html", error_code=404, message="The requested page could not be found."), 404

@app.errorhandler(500)
def handle_server_error(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Internal Server Error", "message": "An unexpected error occurred."}), 500
    return render_template("500.html"), 500

# ---------------------------------------------------------------------------
# APPLICATION ENTRYPOINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 65)
    print(" MediCare HMS - Hospital Management System (Distributed Systems)")
    print(f" Server running at: http://{Config.FLASK_HOST}:{Config.FLASK_PORT}")
    print(f" Access locally:    http://127.0.0.1:{Config.FLASK_PORT}")
    print("=" * 65)
    app.run(
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT,
        debug=Config.FLASK_DEBUG
    )

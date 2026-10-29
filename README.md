# MediCare HMS — Hospital Management System using Distributed Systems

> **Academic Project-Based Learning (PBL) Implementation**  
> **Course:** Distributed Systems / Full-Stack Web Architecture  
> **Backend:** Python 3 & Flask | **Database:** MongoDB Atlas & PyMongo | **Frontend:** HTML5, CSS3, JavaScript, Bootstrap 5

---

## 1. Project Overview & Abstract

**MediCare HMS** is a complete, production-grade, web-based Hospital Management System developed to demonstrate fundamental **Distributed Systems** concepts within a healthcare domain. The application connects multiple concurrent client endpoints (Receptionists, Doctors, and Hospital Administrators) to a centralized Flask application tier and a shared MongoDB Atlas cloud database cluster.

In traditional standalone hospital software, localized patient records lead to data silos, appointment schedule collisions, and security risks. MediCare HMS solves this by implementing:
- Centralized, concurrent multi-client access over HTTP/REST.
- Guaranteed ACID-level document consistency and atomic counter generation.
- Real-time backend validation preventing conflicting doctor appointment schedules.
- Immutable centralized audit logging for security and traceability.
- Role-Based Access Control (RBAC) across Admin, Receptionist, and Doctor roles.

---

## 2. Distributed Systems Architecture

```
                       ┌───────────────────────────────┐
                       │  Client A (Reception Desk)    │
                       │  Web Browser / HTTP Client   │
                       └──────────────┬────────────────┘
                                      │ HTTP Request / Response
                                      ▼
                       ┌───────────────────────────────┐
                       │  Flask Application Server     │
                       │  Host: 0.0.0.0 : 5000         │
                       │  - Business Logic & RBAC      │
                       │  - Concurrency Conflict Engine│
                       │  - Session & CSRF Security    │
                       └──────────────┬────────────────┘
                                      │ PyMongo Wire Protocol
                                      ▼
                       ┌───────────────────────────────┐
                       │  Centralized MongoDB Atlas     │
                       │  Cloud Replica Set Database   │
                       │  - Database: medicare_hms     │
                       │  - Atomic ID Sequence Counters│
                       │  - Central Audit Trail        │
                       └──────────────▲────────────────┘
                                      │ PyMongo Wire Protocol
                                      │
                       ┌──────────────┴────────────────┐
                       │  Client B (Doctor Station)    │
                       │  Web Browser / Mobile / REST  │
                       └───────────────────────────────┘
```

### Core Distributed Systems Concepts Demonstrated:

1. **Client-Server Architecture:**
   - Clients (Browsers, mobile devices, or API consumers) communicate with the centralized application server exclusively using standard HTTP/HTTPS protocols.
2. **Centralized Database Access:**
   - All client instances read from and write to a single source of truth in MongoDB Atlas, ensuring consistent state across the hospital network.
3. **Concurrent Multi-User Access & Mutual Exclusion:**
   - Multiple users simultaneously perform operations (e.g., patient registrations and appointment bookings) without race conditions.
4. **Data Consistency & Atomic Operations:**
   - Consecutive, collision-free Patient (`PAT-XXXX`), Doctor (`DOC-XXXX`), and Appointment (`APT-XXXX`) IDs are generated using MongoDB's atomic `find_one_and_update` with `$inc: {"seq": 1}`.
5. **Backend Concurrency Conflict Prevention:**
   - When Client A and Client B attempt to book the same doctor at the exact same hour, the server evaluates schedule locks and rejects the conflicting request with an HTTP `409 Conflict`.
6. **Stateless REST Communication & Session Security:**
   - Provides standardized JSON REST APIs with HTTP status codes (`200 OK`, `201 Created`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`, `409 Conflict`, `500 Server Error`).
7. **Resilient Fallback & Fault Tolerance:**
   - Handles network partitions, transient database connectivity loss, and offline evaluations gracefully via integrated diagnostics and in-memory mock fallback mode.
8. **Centralized Distributed Audit Logging:**
   - Every state mutation (logins, updates, registrations, cancellations) is committed to an immutable `audit_logs` collection along with UTC timestamps, roles, and client IP addresses.

---

## 3. Technology Stack

| Layer | Technologies & Tools |
| :--- | :--- |
| **Frontend** | HTML5, CSS3 (Custom Hospital Design System), JavaScript (ES6+), Bootstrap 5, Bootstrap Icons, Chart.js |
| **Backend** | Python 3.11+, Flask 3.x, Werkzeug (Password Hashing), Python-Dotenv |
| **Database** | MongoDB Atlas (Cloud) / Local MongoDB / PyMongo 4.x with SRV DNS resolution |
| **Testing** | Pytest 8.x, Mongomock (In-memory mock for rapid isolated unit testing), Requests |
| **Environment** | Windows 10/11, PowerShell, Visual Studio Code |

---

## 4. Database Schema (MongoDB Atlas)

Database Name: `medicare_hms`

### 1. `users` Collection
```json
{
  "_id": {"$oid": "..."},
  "username": "admin",
  "password_hash": "scrypt:32768:8:1$...",
  "role": "admin",
  "full_name": "System Administrator",
  "email": "admin@medicare.local",
  "doctor_id": null,
  "active": true,
  "created_at": "2026-10-15T08:30:00Z"
}
```

### 2. `patients` Collection
```json
{
  "_id": {"$oid": "..."},
  "patient_id": "PAT-1001",
  "name": "Alexander Hayes",
  "date_of_birth": "1988-04-14",
  "age": 37,
  "gender": "Male",
  "phone": "+1 (555) 890-1122",
  "email": "alex.hayes@example.com",
  "address": "742 Evergreen Terrace, Springfield",
  "blood_group": "O+",
  "active": true,
  "created_at": "2026-10-15T08:30:00Z",
  "created_by": "receptionist"
}
```

### 3. `doctors` Collection
```json
{
  "_id": {"$oid": "..."},
  "doctor_id": "DOC-1001",
  "name": "Dr. Sarah Smith",
  "specialization": "Cardiology",
  "department": "Cardiology & Vascular",
  "phone": "+1 (555) 234-5678",
  "email": "dr.smith@medicare.local",
  "availability": "Mon - Fri, 09:00 - 15:00",
  "consultation_fee": 750.0,
  "active": true,
  "created_at": "2026-10-15T08:30:00Z"
}
```

### 4. `appointments` Collection
```json
{
  "_id": {"$oid": "..."},
  "appointment_id": "APT-1001",
  "patient_id": "PAT-1001",
  "patient_name": "Alexander Hayes",
  "doctor_id": "DOC-1001",
  "doctor_name": "Dr. Sarah Smith",
  "appointment_date": "2026-10-15",
  "appointment_time": "09:30",
  "appointment_datetime": "2026-10-15T09:30:00Z",
  "reason": "Routine cardiac checkup and BP review",
  "status": "Scheduled",
  "created_at": "2026-10-15T08:30:00Z"
}
```

### 5. `counters` Collection (Atomic Distributed Locks)
```json
{
  "_id": "patient_id",
  "seq": 1005
}
```

### 6. `audit_logs` Collection
```json
{
  "_id": {"$oid": "..."},
  "timestamp": "2026-10-15T08:35:12Z",
  "action": "APPOINTMENT_BOOKED",
  "user": "receptionist",
  "role": "receptionist",
  "client_ip": "192.168.1.45",
  "details": {"appointment_id": "APT-1006", "doctor_id": "DOC-1001"}
}
```

---

## 5. Quick-Start Installation (Windows 10/11)

### Prerequisites:
- Python 3.10+ installed and added to Windows `PATH`.
- Windows PowerShell.

### Step 1: Open PowerShell in Project Directory
```powershell
cd C:\Users\hp\OneDrive\Documents\DS
```

### Step 2: Create and Activate Virtual Environment
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
*(If PowerShell displays an execution policy warning, run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`)*

### Step 3: Install Required Dependencies
```powershell
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```
Open `.env` in VS Code or Notepad and set your variables.

---

## 6. MongoDB Atlas Cloud Database Setup Guide

If you wish to connect to your live MongoDB Atlas cloud database:

1. **Create Free Account:** Go to [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas) and register.
2. **Build a Free Database:** Choose **M0 Free Shared Cluster**, select AWS or Google Cloud, and choose your nearest region.
3. **Database Access User:** Create a database user (e.g. `admin`), generate a strong password, and assign the `Read and write to any database` role.
4. **Network Access (IP Whitelist):** In **Network Access**, add IP `0.0.0.0/0` (Allow Access from Anywhere) to permit connections from your home/college network.
5. **Get Connection String:** Click **Connect** -> **Drivers** -> **Python (3.6 or later)**. Copy the URI format:
   ```
   mongodb+srv://<username>:<password>@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority
   ```
6. Paste your URI into `.env`:
   ```env
   MONGO_URI=mongodb+srv://admin:MySecurePass123@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority
   DB_NAME=medicare_hms
   ```

*(Note: MediCare HMS has an automatic resilient mock database fallback. If no Atlas cluster is provided, it operates seamlessly in local in-memory mode so you can demo immediately).*

---

## 7. Seeding Initial Hospital Data & Admin Account

Run the idempotent database seed script:
```powershell
python seed.py
```

### Pre-Configured Demo Accounts:
| Role | Username | Password | Permissions |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin` | `Admin@123` | Full Access: Dashboard, Patients, Doctors, Appointments, Reports, API, Staff Management |
| **Receptionist** | `receptionist` | `Recep@123` | Patient Registration, Search & Edit, Appointment Booking & Scheduling |
| **Doctor** | `dr_smith` | `Doctor@123` | View Authorized Patients, View Daily Schedule, Complete Consultations |

---

## 8. Running the Application

Start the Flask application server:
```powershell
python app.py
```

You will see:
```text
=================================================================
 MediCare HMS - Hospital Management System (Distributed Systems)
 Server running at: http://0.0.0.0:5000
 Access locally:    http://127.0.0.1:5000
=================================================================
 * Running on http://127.0.0.1:5000
 * Running on http://192.168.1.XX:5000
```

Open your browser and navigate to:
[http://127.0.0.1:5000](http://127.0.0.1:5000)

---

## 9. Multi-Client / Multi-Device Demonstration (LAN)

To demonstrate the **Distributed Systems** client-server network functionality between two different devices on the same Wi-Fi network (e.g., Laptop as Server/Client A and Mobile/Second Laptop as Client B):

1. **Find your Server IP:**
   In PowerShell, run:
   ```powershell
   ipconfig
   ```
   Look for the `IPv4 Address` under your active Wi-Fi adapter (e.g. `192.168.1.15` or `172.21.5.198`).
2. **Windows Firewall Rule (One-Time Command in Admin PowerShell):**
   ```powershell
   New-NetFirewallRule -DisplayName "MediCare HMS Port 5000" -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow
   ```
3. **Open on Client B (Mobile or 2nd Computer):**
   Open Chrome/Safari and visit:
   `http://<YOUR_IPV4_ADDRESS>:5000` (e.g. `http://192.168.1.15:5000`)
4. **Demonstration Steps:**
   - **Client A (Laptop):** Sign in as `receptionist`. Register a new patient.
   - **Client B (Mobile):** Sign in as `dr_smith`. Search for the patient. The record appears immediately.
   - Both clients verify identical real-time data retrieved from the central database.

---

## 10. Automated Testing

MediCare HMS comes with a test suite verifying authentication, patient lifecycle, atomic counters, and appointment conflict prevention.

Run pytest in PowerShell:
```powershell
pytest -v
```

Expected Output:
```text
tests/test_appointments.py::test_book_appointment PASSED                 [  6%]
tests/test_appointments.py::test_appointment_conflict_prevention PASSED  [ 12%]
tests/test_appointments.py::test_appointment_status_update PASSED        [ 18%]
tests/test_appointments.py::test_api_appointment_conflict_returns_409 PASSED [ 25%]
tests/test_auth.py::test_login_page_renders PASSED                       [ 31%]
tests/test_auth.py::test_successful_admin_login PASSED                   [ 37%]
tests/test_auth.py::test_invalid_login PASSED                            [ 43%]
tests/test_auth.py::test_unauthenticated_access_redirect PASSED          [ 50%]
tests/test_auth.py::test_rbac_receptionist_cannot_access_reports PASSED  [ 56%]
tests/test_auth.py::test_logout PASSED                                   [ 62%]
tests/test_auth.py::test_api_system_info PASSED                          [ 68%]
tests/test_patients.py::test_patient_registration_and_atomic_id PASSED   [ 75%]
tests/test_patients.py::test_patient_search PASSED                       [ 81%]
tests/test_patients.py::test_patient_update PASSED                       [ 87%]
tests/test_patients.py::test_patient_archiving PASSED                    [ 93%]
tests/test_patients.py::test_api_patients PASSED                         [100%]
============================= 16 passed in 6.18s ==============================
```

---

## 11. REST API Specification

| Method | Endpoint | Description | Role Required | Status Codes |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/system-info` | Client IP, server time, database status | Public | `200` |
| `POST` | `/api/auth/login` | JSON user authentication | Public | `200`, `401` |
| `GET` | `/api/patients` | List registered patients | Logged In | `200` |
| `POST` | `/api/patients` | Register patient | Admin, Receptionist | `201`, `400`, `403` |
| `GET` | `/api/patients/<id>` | Fetch single patient | Logged In | `200`, `404` |
| `PUT` | `/api/patients/<id>` | Update patient details | Admin, Receptionist | `200`, `403`, `404` |
| `GET` | `/api/doctors` | List active medical staff | Logged In | `200` |
| `POST` | `/api/doctors` | Create new doctor | Admin | `201`, `400`, `403` |
| `GET` | `/api/appointments` | Filtered appointment list | Logged In | `200` |
| `POST` | `/api/appointments` | Book appointment with conflict check | Admin, Receptionist | `201`, `400`, `409` |
| `GET` | `/api/stats` | Aggregated metrics | Logged In | `200` |

---

## 12. College PBL Presentation & Demonstration Script

Follow this script when presenting to teachers and evaluators:

### Step 1: Explain Problem & Architecture (1 Minute)
- Introduce **MediCare HMS** as a 3-tier distributed system:
  1. Presentation Tier (Concurrent Web Clients).
  2. Application Tier (Flask Server managing concurrency and RBAC).
  3. Data Tier (Centralized MongoDB Atlas document store).
- Click **"System Architecture"** in the sidebar to display the live live node diagnostics modal.

### Step 2: Role-Based Access Control Demonstration (1 Minute)
- Log in as **Receptionist** (`receptionist` / `Recep@123`).
- Show that Receptionists can manage Patients and Book Appointments.
- Attempt to navigate to `/reports` or `/doctors/new`. Point out the HTTP `403 Forbidden` security enforcement.

### Step 3: Concurrent Multi-Client Data Flow Demonstration (2 Minutes)
- Open a second browser in **Incognito Mode** (or a smartphone connected to Wi-Fi).
- On **Client A (Receptionist)**: Register a patient named `"Marcus Brody"`. Point out the atomic counter ID (e.g. `PAT-1006`).
- On **Client B (Dr. Smith)**: Refresh the dashboard or search for `"Marcus"`. Show that the patient is immediately retrievable.

### Step 4: Concurrency Conflict Prevention Demonstration (2 Minutes)
- On **Client A**: Book an appointment for `"Marcus Brody"` with `"Dr. Sarah Smith"` on a specific date at `11:00`.
- Immediately attempt to book **another appointment** for a different patient with `"Dr. Sarah Smith"` at the exact same date and time (`11:00`).
- Show the teacher that the backend detects the schedule collision and rejects the request with an explanatory warning (`Schedule Conflict! Doctor is already booked...`).

### Step 5: Reports & Centralized Audit Trail (1 Minute)
- Sign in as **Admin** (`admin` / `Admin@123`).
- Navigate to **Reports & Analytics**.
- Point out the Chart.js status breakdown, doctor workload distributions, and the **Centralized Audit Trail** showing all actions logged with client IPs, timestamps, and usernames.

---

## 13. Security & Best Practices

- **Password Hashing:** Werkzeug PBKDF2/Scrypt cryptographic salt & hashing.
- **CSRF Tokens:** Synchronizer token pattern with `X-CSRFToken` verification on all mutating requests.
- **Session Protection:** `HttpOnly`, `SameSite=Lax`, and 8-hour lifetime cookie tokens.
- **Sanitized DB Access:** MongoDB parameterized queries prevent NoSQL injection.
- **No Credentials in Frontend:** Database connection strings are stored strictly server-side in `.env`.

---

## 14. License & Educational Usage
This project is built for educational and demonstration purposes as part of college Project-Based Learning (PBL). All synthetic patient data is fictional.

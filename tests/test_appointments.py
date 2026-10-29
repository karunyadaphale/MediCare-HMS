import pytest
from datetime import datetime, timezone
from app import app
from db import init_db
from werkzeug.security import generate_password_hash

@pytest.fixture
def client():
    app.config["TESTING"] = True
    db = init_db(force_mock=True)

    # Clean collections
    db.users.delete_many({})
    db.patients.delete_many({})
    db.doctors.delete_many({})
    db.appointments.delete_many({})
    db.counters.delete_many({})

    # Initialize counters
    db.counters.insert_one({"_id": "patient_id", "seq": 1000})
    db.counters.insert_one({"_id": "doctor_id", "seq": 1000})
    db.counters.insert_one({"_id": "appointment_id", "seq": 1000})

    # Setup User, Patient, Doctor
    db.users.insert_one({
        "username": "admin",
        "password_hash": generate_password_hash("Admin@123"),
        "role": "admin",
        "full_name": "Admin Tester",
        "active": True
    })

    db.patients.insert_one({
        "patient_id": "PAT-1001",
        "name": "Bruce Banner",
        "date_of_birth": "1975-12-18",
        "age": 49,
        "gender": "Male",
        "phone": "+1 555-4321",
        "blood_group": "B+",
        "active": True,
        "created_at": datetime.now(timezone.utc)
    })

    db.doctors.insert_one({
        "doctor_id": "DOC-1001",
        "name": "Dr. Strange",
        "specialization": "Neuroscience",
        "department": "Surgery",
        "phone": "+1 555-8888",
        "consultation_fee": 1000.0,
        "active": True,
        "created_at": datetime.now(timezone.utc)
    })

    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "Admin@123"})
        yield client

def test_book_appointment(client):
    """Test successful appointment booking."""
    response = client.post("/appointments/new", data={
        "patient_id": "PAT-1001",
        "doctor_id": "DOC-1001",
        "appointment_date": "2026-11-20",
        "appointment_time": "10:00",
        "reason": "Neurological checkup"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"APT-1001 confirmed" in response.data

def test_appointment_conflict_prevention(client):
    """
    CRITICAL DISTRIBUTED SYSTEMS TEST:
    Verify that concurrent bookings for the same doctor at the same slot are rejected.
    """
    # First booking
    res1 = client.post("/appointments/new", data={
        "patient_id": "PAT-1001",
        "doctor_id": "DOC-1001",
        "appointment_date": "2026-11-25",
        "appointment_time": "14:00",
        "reason": "First consultation"
    }, follow_redirects=True)
    assert res1.status_code == 200

    # Second booking at exact same slot for same doctor
    res2 = client.post("/appointments/new", data={
        "patient_id": "PAT-1001",
        "doctor_id": "DOC-1001",
        "appointment_date": "2026-11-25",
        "appointment_time": "14:00",
        "reason": "Conflicting consultation"
    }, follow_redirects=True)

    assert res2.status_code == 200
    assert b"Schedule Conflict!" in res2.data

def test_appointment_status_update(client):
    """Test updating appointment status to Completed."""
    # Book appointment
    client.post("/appointments/new", data={
        "patient_id": "PAT-1001",
        "doctor_id": "DOC-1001",
        "appointment_date": "2026-11-21",
        "appointment_time": "11:30",
        "reason": "Followup"
    })

    # Mark as completed
    status_res = client.post("/appointments/APT-1001/status", data={
        "status": "Completed"
    }, follow_redirects=True)

    assert status_res.status_code == 200
    assert b"marked as Completed" in status_res.data

def test_api_appointment_conflict_returns_409(client):
    """Test REST API returns HTTP 409 Conflict upon slot collision."""
    # 1st API booking
    client.post("/api/appointments", json={
        "patient_id": "PAT-1001",
        "doctor_id": "DOC-1001",
        "appointment_date": "2026-12-01",
        "appointment_time": "15:00",
        "reason": "API booking 1"
    })

    # 2nd API booking collision
    collision_res = client.post("/api/appointments", json={
        "patient_id": "PAT-1001",
        "doctor_id": "DOC-1001",
        "appointment_date": "2026-12-01",
        "appointment_time": "15:00",
        "reason": "API booking collision"
    })

    assert collision_res.status_code == 409
    assert "Conflict" in collision_res.get_json()["error"]

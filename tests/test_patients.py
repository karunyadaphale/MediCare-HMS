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
    db.counters.delete_many({})
    
    # Initialize counter & user
    db.counters.insert_one({"_id": "patient_id", "seq": 1000})
    db.users.insert_one({
        "username": "admin",
        "password_hash": generate_password_hash("Admin@123"),
        "role": "admin",
        "full_name": "Admin Tester",
        "active": True
    })

    with app.test_client() as client:
        # Pre-authenticate
        client.post("/login", data={"username": "admin", "password": "Admin@123"})
        yield client

def test_patient_registration_and_atomic_id(client):
    """Test patient registration generates human-readable sequential ID."""
    response = client.post("/patients/new", data={
        "name": "Jane Doe",
        "date_of_birth": "1992-08-15",
        "gender": "Female",
        "phone": "+1 555-0199",
        "email": "jane.doe@example.com",
        "address": "456 Oak Avenue",
        "blood_group": "O+"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Jane Doe" in response.data
    assert b"PAT-1001" in response.data

def test_patient_search(client):
    """Test searching patient by query parameter."""
    # Seed a patient
    client.post("/patients/new", data={
        "name": "Bruce Wayne",
        "date_of_birth": "1980-02-19",
        "gender": "Male",
        "phone": "+1 555-9999",
        "blood_group": "AB+"
    })

    search_res = client.get("/patients?q=Wayne")
    assert search_res.status_code == 200
    assert b"Bruce Wayne" in search_res.data

    no_match_res = client.get("/patients?q=NonExistentPersonX")
    assert no_match_res.status_code == 200
    assert b"Bruce Wayne" not in no_match_res.data

def test_patient_update(client):
    """Test editing patient demographics."""
    # Create patient
    client.post("/patients/new", data={
        "name": "Clark Kent",
        "date_of_birth": "1985-06-18",
        "gender": "Male",
        "phone": "+1 555-1111"
    })

    # Update patient
    update_res = client.post("/patients/PAT-1001/edit", data={
        "name": "Clark Kent",
        "date_of_birth": "1985-06-18",
        "gender": "Male",
        "phone": "+1 555-2222",
        "email": "clark@dailyplanet.com",
        "address": "Metropolis",
        "blood_group": "O-"
    }, follow_redirects=True)

    assert update_res.status_code == 200
    assert b"+1 555-2222" in update_res.data
    assert b"O-" in update_res.data

def test_patient_archiving(client):
    """Test archiving soft-deletes patient from active listing."""
    client.post("/patients/new", data={
        "name": "Temporary Patient",
        "date_of_birth": "2000-01-01",
        "gender": "Other",
        "phone": "+1 555-0000"
    })

    # Delete
    del_res = client.post("/patients/PAT-1001/delete", follow_redirects=True)
    assert del_res.status_code == 200
    assert b"PAT-1001 has been archived successfully" in del_res.data

def test_api_patients(client):
    """Test JSON REST API endpoints for patients."""
    api_post = client.post("/api/patients", json={
        "name": "API Patient Test",
        "date_of_birth": "1995-12-05",
        "gender": "Female",
        "phone": "+1 555-7788",
        "blood_group": "B+"
    })
    assert api_post.status_code == 201
    json_data = api_post.get_json()
    assert json_data["patient"]["patient_id"].startswith("PAT-")

    api_get = client.get("/api/patients")
    assert api_get.status_code == 200
    assert api_get.get_json()["count"] >= 1

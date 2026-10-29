import pytest
from app import app
from db import init_db
from werkzeug.security import generate_password_hash

@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    
    # Force in-memory mock database for isolated tests
    db = init_db(force_mock=True)
    
    # Insert test users
    db.users.delete_many({})
    db.users.insert_many([
        {
            "username": "admin",
            "password_hash": generate_password_hash("Admin@123"),
            "role": "admin",
            "full_name": "Test Admin",
            "active": True
        },
        {
            "username": "receptionist",
            "password_hash": generate_password_hash("Recep@123"),
            "role": "receptionist",
            "full_name": "Test Receptionist",
            "active": True
        },
        {
            "username": "dr_smith",
            "password_hash": generate_password_hash("Doctor@123"),
            "role": "doctor",
            "doctor_id": "DOC-1001",
            "full_name": "Dr. Smith",
            "active": True
        }
    ])

    with app.test_client() as client:
        yield client

def test_login_page_renders(client):
    """Verify login page is accessible."""
    response = client.get("/login")
    assert response.status_code == 200
    assert b"MediCare HMS" in response.data

def test_successful_admin_login(client):
    """Test valid credentials authenticate successfully."""
    response = client.post("/login", data={
        "username": "admin",
        "password": "Admin@123"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Hospital Administration Dashboard" in response.data

def test_invalid_login(client):
    """Test invalid credentials are rejected with flash error."""
    response = client.post("/login", data={
        "username": "admin",
        "password": "WrongPassword999"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Invalid username or password" in response.data

def test_unauthenticated_access_redirect(client):
    """Test protected routes redirect anonymous users to login."""
    response = client.get("/dashboard")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

def test_rbac_receptionist_cannot_access_reports(client):
    """Test Receptionist role receives 403 Forbidden on Admin-only reports."""
    # Login as receptionist
    client.post("/login", data={"username": "receptionist", "password": "Recep@123"})
    response = client.get("/reports")
    assert response.status_code == 403

def test_logout(client):
    """Test user session is destroyed on logout."""
    client.post("/login", data={"username": "admin", "password": "Admin@123"})
    response = client.get("/logout", follow_redirects=True)
    assert response.status_code == 200
    assert b"You have been signed out successfully" in response.data

def test_api_system_info(client):
    """Test distributed system diagnostics API endpoint."""
    response = client.get("/api/system-info")
    assert response.status_code == 200
    json_data = response.get_json()
    assert "distributed_architecture" in json_data
    assert json_data["system"].startswith("MediCare HMS")

def test_404_page_renders_cleanly(client):
    """Verify friendly 404 page renders without Jinja template errors."""
    client.post("/login", data={"username": "admin", "password": "Admin@123"})
    response = client.get("/non-existent-page-url-xyz")
    assert response.status_code == 404
    assert b"Record or Resource Not Found" in response.data

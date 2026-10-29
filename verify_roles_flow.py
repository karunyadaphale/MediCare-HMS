import requests
import re

def verify_all_role_flows():
    base_url = "http://127.0.0.1:5000"
    print("==================================================")
    print("  VERIFYING ROLE SWITCHING AND ROLE-SPECIFIC SCREENS")
    print("==================================================")

    s = requests.Session()

    # 1. Test Login Page loads cleanly
    r_login = s.get(f"{base_url}/login")
    assert r_login.status_code == 200, f"Login page failed with status {r_login.status_code}"
    assert "Sign In to Hospital Portal" in r_login.text, "Missing sign in button on login page"
    assert "name=\"username\"" in r_login.text, "Missing username field on login page"
    assert "name=\"password\"" in r_login.text, "Missing password field on login page"
    assert "role-launch-grid" not in r_login.text, "role-launch-grid should not be present on login page"
    print("[PASS] Login Page: Clean authentication form verified (autofill removed)")

    # 2. Test 1-click switch to Doctor (Dr. Smith)
    r_doc_switch = s.get(f"{base_url}/switch-role/doctor", allow_redirects=True)
    assert r_doc_switch.status_code == 200
    assert "Doctor OPD Clinical Consultation Station" in r_doc_switch.text
    assert "ATTENDING PHYSICIAN CLINICAL OPD STATION" in r_doc_switch.text
    assert "My Patient Queue" in r_doc_switch.text
    assert "₹" in r_doc_switch.text
    print("[PASS] Doctor Screen: OPD Clinical Station, Queue & Banner verified")

    # Check Doctor's appointments view
    r_doc_apts = s.get(f"{base_url}/appointments")
    assert r_doc_apts.status_code == 200
    assert "My OPD Clinical Consultations Queue" in r_doc_apts.text
    print("[PASS] Doctor Screen: Tailored Appointments Queue verified")

    # Check Doctor's doctors list view
    r_doc_list = s.get(f"{base_url}/doctors")
    assert r_doc_list.status_code == 200
    assert "Medical Staff & My Clinical Profile" in r_doc_list.text
    assert "Your Profile" in r_doc_list.text
    print("[PASS] Doctor Screen: Tailored Doctors List with Profile Highlight verified")

    # 3. Test 1-click switch to Receptionist
    r_rec_switch = s.get(f"{base_url}/switch-role/receptionist", allow_redirects=True)
    assert r_rec_switch.status_code == 200
    assert "Front Desk & Patient Admission Portal" in r_rec_switch.text
    assert "FRONT DESK PATIENT ADMISSION & TRIAGE DESK" in r_rec_switch.text
    assert "Register Walk-In" in r_rec_switch.text
    assert "Queue & Token Booking" in r_rec_switch.text
    print("[PASS] Receptionist Screen: Front Desk Portal, Admissions & Tokens verified")

    # Check Receptionist's appointments view
    r_rec_apts = s.get(f"{base_url}/appointments")
    assert r_rec_apts.status_code == 200
    assert "Front Desk Patient Queue & Token Desk" in r_rec_apts.text
    print("[PASS] Receptionist Screen: Tailored Token Desk Schedule verified")

    # 4. Test 1-click switch to Administrator
    r_adm_switch = s.get(f"{base_url}/switch-role/admin", allow_redirects=True)
    assert r_adm_switch.status_code == 200
    assert "Administrator Command Center" in r_adm_switch.text
    assert "EXECUTIVE HOSPITAL COMMAND & CONTROL CENTER" in r_adm_switch.text
    assert "Revenue & Analytics (₹)" in r_adm_switch.text
    print("[PASS] Admin Screen: Executive Command Center, Financials & Oversight verified")

    # Check Admin's reports view
    r_adm_rep = s.get(f"{base_url}/reports")
    assert r_adm_rep.status_code == 200
    assert "Reports & Analytics" in r_adm_rep.text or "Financial" in r_adm_rep.text
    print("[PASS] Admin Screen: Analytics & Reports Access verified")

    print("\n==================================================")
    print("  ALL 3 ROLE SCREENS FULLY VERIFIED AND PASSING!")
    print("==================================================")

if __name__ == "__main__":
    verify_all_role_flows()

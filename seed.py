"""
MediCare HMS - Database Seeding Script
Populates MongoDB with initial role-based users and realistic synthetic hospital data.
Safe to run multiple times (idempotent).
"""

import sys
from datetime import datetime, date, timedelta, timezone
from werkzeug.security import generate_password_hash
from config import Config
from db import init_db, get_db

def seed_database():
    print("=" * 60)
    print(" MediCare HMS - Initializing Database & Demo Data")
    print("=" * 60)

    db = init_db()
    if db is None:
        print("[ERROR] Could not connect to database. Please check your .env configuration.")
        sys.exit(1)

    now = datetime.now(timezone.utc)
    today_str = date.today().strftime("%Y-%m-%d")
    tomorrow_str = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    yesterday_str = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

    # -------------------------------------------------------------
    # 1. SEED USERS (Role-Based Access Control)
    # -------------------------------------------------------------
    print("\n[1/5] Seeding User Accounts (RBAC)...")
    users_to_seed = [
        {
            "username": Config.ADMIN_USERNAME.lower(),
            "password_hash": generate_password_hash(Config.ADMIN_PASSWORD),
            "full_name": Config.ADMIN_NAME,
            "email": Config.ADMIN_EMAIL,
            "role": "admin",
            "active": True,
            "created_at": now
        },
        {
            "username": "receptionist",
            "password_hash": generate_password_hash("Recep@123"),
            "full_name": "Sarah Miller (Reception)",
            "email": "reception@medicare.local",
            "role": "receptionist",
            "active": True,
            "created_at": now
        },
        {
            "username": "dr_sharma",
            "password_hash": generate_password_hash("Doctor@123"),
            "full_name": "Dr. Sneha Sharma, MD",
            "email": "dr.sharma@medicare.local",
            "role": "doctor",
            "doctor_id": "DOC-1001",
            "active": True,
            "created_at": now
        },
        {
            "username": "dr_smith",
            "password_hash": generate_password_hash("Doctor@123"),
            "full_name": "Dr. Sneha Sharma, MD",
            "email": "dr.sharma@medicare.local",
            "role": "doctor",
            "doctor_id": "DOC-1001",
            "active": True,
            "created_at": now
        },
        {
            "username": "dr_patel",
            "password_hash": generate_password_hash("Doctor@123"),
            "full_name": "Dr. Rajesh Patel, MBBS, MS",
            "email": "dr.patel@medicare.local",
            "role": "doctor",
            "doctor_id": "DOC-1002",
            "active": True,
            "created_at": now
        }
    ]

    for user_data in users_to_seed:
        existing = db.users.find_one({"username": user_data["username"]})
        if not existing:
            db.users.insert_one(user_data)
            print(f"  [+] Created user: {user_data['username']} ({user_data['role']})")
        else:
            db.users.update_one({"username": user_data["username"]}, {"$set": user_data})
            print(f"  [+] Updated user: {user_data['username']} ({user_data['role']})")

    # -------------------------------------------------------------
    # 2. SEED DOCTORS
    # -------------------------------------------------------------
    print("\n[2/5] Seeding Doctor Profiles...")
    doctors_to_seed = [
        {
            "doctor_id": "DOC-1001",
            "name": "Dr. Sneha Sharma",
            "specialization": "Cardiology",
            "department": "Cardiology & Vascular",
            "phone": "+91 98201 23456",
            "email": "dr.sharma@medicare.local",
            "availability": "Mon - Fri, 09:00 - 15:00",
            "consultation_fee": 750,
            "active": True,
            "created_at": now
        },
        {
            "doctor_id": "DOC-1002",
            "name": "Dr. Rajesh Patel",
            "specialization": "General Medicine",
            "department": "Internal Medicine",
            "phone": "+91 98202 34567",
            "email": "dr.patel@medicare.local",
            "availability": "Mon - Sat, 10:00 - 18:00",
            "consultation_fee": 500,
            "active": True,
            "created_at": now
        },
        {
            "doctor_id": "DOC-1003",
            "name": "Dr. Ananya Iyer",
            "specialization": "Neurology",
            "department": "Neurosciences",
            "phone": "+91 98203 45678",
            "email": "dr.iyer@medicare.local",
            "availability": "Tue - Sat, 08:30 - 14:30",
            "consultation_fee": 900,
            "active": True,
            "created_at": now
        },
        {
            "doctor_id": "DOC-1004",
            "name": "Dr. Vikram Malhotra",
            "specialization": "Orthopedics",
            "department": "Surgery & Ortho",
            "phone": "+91 98204 56789",
            "email": "dr.malhotra@medicare.local",
            "availability": "Mon - Thu, 11:00 - 17:00",
            "consultation_fee": 800,
            "active": True,
            "created_at": now
        },
        {
            "doctor_id": "DOC-1005",
            "name": "Dr. Pooja Verma",
            "specialization": "Pediatrics",
            "department": "Child & Adolescent Health",
            "phone": "+91 98205 67890",
            "email": "dr.verma@medicare.local",
            "availability": "Mon - Fri, 09:00 - 16:00",
            "consultation_fee": 600,
            "active": True,
            "created_at": now
        }
    ]

    for doc in doctors_to_seed:
        existing = db.doctors.find_one({"doctor_id": doc["doctor_id"]})
        if not existing:
            db.doctors.insert_one(doc)
            print(f"  [+] Created doctor: {doc['doctor_id']} - {doc['name']} ({doc['specialization']})")
        else:
            db.doctors.update_one({"doctor_id": doc["doctor_id"]}, {"$set": doc})
            print(f"  [+] Updated doctor: {doc['doctor_id']} - {doc['name']} ({doc['specialization']})")

    # -------------------------------------------------------------
    # 3. SEED PATIENTS
    # -------------------------------------------------------------
    print("\n[3/5] Seeding Patient Records...")
    patients_to_seed = [
        {
            "patient_id": "PAT-1001",
            "name": "Alexander Hayes",
            "date_of_birth": "1988-04-14",
            "age": 37,
            "gender": "Male",
            "phone": "+1 (555) 890-1122",
            "email": "alex.hayes@example.com",
            "address": "742 Evergreen Terrace, Springfield",
            "blood_group": "O+",
            "active": True,
            "created_at": now - timedelta(days=20)
        },
        {
            "patient_id": "PAT-1002",
            "name": "Beatriz Morales",
            "date_of_birth": "1994-09-22",
            "age": 31,
            "gender": "Female",
            "phone": "+1 (555) 789-2233",
            "email": "beatriz.m@example.com",
            "address": "1204 Pine Street, Apt 3B, Metropolis",
            "blood_group": "A+",
            "active": True,
            "created_at": now - timedelta(days=15)
        },
        {
            "patient_id": "PAT-1003",
            "name": "Charles Lindqvist",
            "date_of_birth": "1972-11-05",
            "age": 53,
            "gender": "Male",
            "phone": "+1 (555) 678-3344",
            "email": "c.lindqvist@example.com",
            "address": "88 Ocean Drive, Star City",
            "blood_group": "B+",
            "active": True,
            "created_at": now - timedelta(days=10)
        },
        {
            "patient_id": "PAT-1004",
            "name": "Divya Sharma",
            "date_of_birth": "2001-02-18",
            "age": 24,
            "gender": "Female",
            "phone": "+1 (555) 567-4455",
            "email": "divya.sharma@example.com",
            "address": "402 Grand Avenue, Central City",
            "blood_group": "AB+",
            "active": True,
            "created_at": now - timedelta(days=5)
        },
        {
            "patient_id": "PAT-1005",
            "name": "Ethan Wright",
            "date_of_birth": "2015-06-30",
            "age": 10,
            "gender": "Male",
            "phone": "+1 (555) 456-5566",
            "email": "wright.family@example.com",
            "address": "15 Maple Lane, Riverdale",
            "blood_group": "O-",
            "active": True,
            "created_at": now - timedelta(days=2)
        }
    ]

    for pat in patients_to_seed:
        existing = db.patients.find_one({"patient_id": pat["patient_id"]})
        if not existing:
            db.patients.insert_one(pat)
            print(f"  [+] Created patient: {pat['patient_id']} - {pat['name']}")
        else:
            print(f"  [i] Patient exists: {pat['patient_id']} (skipped)")

    # -------------------------------------------------------------
    # 4. SEED APPOINTMENTS
    # -------------------------------------------------------------
    print("\n[4/5] Seeding Appointments...")
    appointments_to_seed = [
        {
            "appointment_id": "APT-1001",
            "patient_id": "PAT-1001",
            "patient_name": "Alexander Hayes",
            "doctor_id": "DOC-1001",
            "doctor_name": "Dr. Sneha Sharma",
            "consultation_fee": 750.0,
            "appointment_date": today_str,
            "appointment_time": "09:30",
            "appointment_datetime": datetime.strptime(f"{today_str} 09:30", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc),
            "reason": "Routine cardiac checkup and BP review",
            "status": "Scheduled",
            "created_at": now - timedelta(days=2)
        },
        {
            "appointment_id": "APT-1002",
            "patient_id": "PAT-1002",
            "patient_name": "Beatriz Morales",
            "doctor_id": "DOC-1002",
            "doctor_name": "Dr. Rajesh Patel",
            "consultation_fee": 500.0,
            "appointment_date": today_str,
            "appointment_time": "11:00",
            "appointment_datetime": datetime.strptime(f"{today_str} 11:00", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc),
            "reason": "Persistent seasonal fever and fatigue",
            "status": "Scheduled",
            "created_at": now - timedelta(days=1)
        },
        {
            "appointment_id": "APT-1003",
            "patient_id": "PAT-1003",
            "patient_name": "Charles Lindqvist",
            "doctor_id": "DOC-1003",
            "doctor_name": "Dr. Ananya Iyer",
            "consultation_fee": 900.0,
            "appointment_date": tomorrow_str,
            "appointment_time": "10:00",
            "appointment_datetime": datetime.strptime(f"{tomorrow_str} 10:00", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc),
            "reason": "Follow-up consultation for migraine symptoms",
            "status": "Scheduled",
            "created_at": now
        },
        {
            "appointment_id": "APT-1004",
            "patient_id": "PAT-1004",
            "patient_name": "Divya Sharma",
            "doctor_id": "DOC-1004",
            "doctor_name": "Dr. Vikram Malhotra",
            "consultation_fee": 800.0,
            "appointment_date": yesterday_str,
            "appointment_time": "14:00",
            "appointment_datetime": datetime.strptime(f"{yesterday_str} 14:00", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc),
            "reason": "Ankle sprain rehabilitation follow-up",
            "status": "Completed",
            "created_at": now - timedelta(days=3)
        },
        {
            "appointment_id": "APT-1005",
            "patient_id": "PAT-1005",
            "patient_name": "Ethan Wright",
            "doctor_id": "DOC-1005",
            "doctor_name": "Dr. Pooja Verma",
            "consultation_fee": 600.0,
            "appointment_date": yesterday_str,
            "appointment_time": "10:30",
            "appointment_datetime": datetime.strptime(f"{yesterday_str} 10:30", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc),
            "reason": "Annual pediatric physical & vaccine review",
            "status": "Completed",
            "created_at": now - timedelta(days=4)
        }
    ]

    for apt in appointments_to_seed:
        existing = db.appointments.find_one({"appointment_id": apt["appointment_id"]})
        if not existing:
            db.appointments.insert_one(apt)
            print(f"  [+] Created appointment: {apt['appointment_id']} ({apt['patient_name']} with {apt['doctor_name']})")
        else:
            db.appointments.update_one({"appointment_id": apt["appointment_id"]}, {"$set": apt})
            print(f"  [+] Updated appointment: {apt['appointment_id']} ({apt['patient_name']} with {apt['doctor_name']})")

    # -------------------------------------------------------------
    # 5. SYNC ATOMIC COUNTERS
    # -------------------------------------------------------------
    print("\n[5/5] Synchronizing Atomic ID Counters...")
    db.counters.update_one({"_id": "patient_id"}, {"$set": {"seq": 1005}}, upsert=True)
    db.counters.update_one({"_id": "doctor_id"}, {"$set": {"seq": 1005}}, upsert=True)
    db.counters.update_one({"_id": "appointment_id"}, {"$set": {"seq": 1005}}, upsert=True)
    print("  [+] Counters updated to 1005. Next records will start at 1006.")

    print("\n" + "=" * 60)
    print(" MediCare HMS - Database Seeding Complete!")
    print("=" * 60)
    print(" Default Login Credentials:")
    print("   1. Admin:        username: admin        / password: Admin@123")
    print("   2. Receptionist: username: receptionist / password: Recep@123")
    print("   3. Doctor:       username: dr_sharma    / password: Doctor@123  (or dr_smith)")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    seed_database()

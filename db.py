import logging
from datetime import datetime, timezone
import pymongo
from pymongo import ReturnDocument
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from config import Config

logger = logging.getLogger("medicare.db")
logging.basicConfig(level=logging.INFO)

_client = None
_db = None
_db_status = {
    "connected": False,
    "is_mock": False,
    "database": Config.DB_NAME,
    "error": None
}

def init_db(app=None, force_mock=False):
    """
    Initialize database connection to MongoDB Atlas or local/mock fallback.
    Establishes indexes and ensures atomic counter initialization.
    """
    global _client, _db, _db_status
    
    if force_mock:
        import mongomock
        logger.info("Initializing in-memory mongomock database (testing/mock mode)...")
        _client = mongomock.MongoClient()
        _db = _client[Config.DB_NAME]
        _db_status["connected"] = True
        _db_status["is_mock"] = True
        _db_status["error"] = None
        _ensure_indexes(_db)
        return _db

    uri = Config.MONGO_URI

    # Detect default placeholder URI or invalid credentials
    is_placeholder = "<username>" in uri or "<password>" in uri or "demo.mongodb.net" in uri

    if not is_placeholder:
        try:
            logger.info("Attempting connection to MongoDB...")
            # Short timeout so application doesn't hang if offline
            client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=4000)
            client.admin.command("ping")
            logger.info("Successfully connected to MongoDB database!")
            _client = client
            _db = _client[Config.DB_NAME]
            _db_status["connected"] = True
            _db_status["is_mock"] = False
            _db_status["error"] = None
            _ensure_indexes(_db)
            return _db
        except (ConnectionFailure, ServerSelectionTimeoutError, Exception) as e:
            logger.warning(f"Failed to connect to MongoDB: {str(e)}")
            _db_status["error"] = str(e)
    else:
        logger.info("MongoDB URI contains placeholder or demo URL. Checking fallback...")
        _db_status["error"] = "Placeholder MongoDB URI detected in configuration"

    if Config.USE_MOCK_DB_IF_UNAVAILABLE:
        try:
            import mongomock
            logger.info("Using mongomock in-memory database as seamless resilient fallback.")
            _client = mongomock.MongoClient()
            _db = _client[Config.DB_NAME]
            _db_status["connected"] = True
            _db_status["is_mock"] = True
            _ensure_indexes(_db)
            return _db
        except Exception as e:
            logger.error(f"Failed to initialize mock database: {str(e)}")
            _db_status["connected"] = False
            _db_status["error"] = str(e)
            return None
    else:
        _db_status["connected"] = False
        return None

def _ensure_indexes(db):
    """Ensure unique constraints and query indexes exist in MongoDB."""
    try:
        # Users indexes
        db.users.create_index("username", unique=True)
        db.users.create_index("role")

        # Patients indexes
        db.patients.create_index("patient_id", unique=True)
        db.patients.create_index("name")
        db.patients.create_index("phone")

        # Doctors indexes
        db.doctors.create_index("doctor_id", unique=True)
        db.doctors.create_index("specialization")
        db.doctors.create_index("active")

        # Appointments indexes
        db.appointments.create_index("appointment_id", unique=True)
        db.appointments.create_index([("doctor_id", pymongo.ASCENDING), ("appointment_date", pymongo.ASCENDING)])
        db.appointments.create_index([("patient_id", pymongo.ASCENDING)])
        db.appointments.create_index([("status", pymongo.ASCENDING)])

        # Audit logs index
        db.audit_logs.create_index([("timestamp", pymongo.DESCENDING)])

        # Ensure counters initial state (starting at 1000 so first is 1001)
        counters = db.counters
        for prefix_key in ["patient_id", "doctor_id", "appointment_id"]:
            if not counters.find_one({"_id": prefix_key}):
                counters.insert_one({"_id": prefix_key, "seq": 1000})

    except Exception as e:
        logger.warning(f"Index creation note (may be non-critical for mock): {str(e)}")

def get_db():
    """Retrieve the active database instance, initializing if necessary."""
    global _db
    if _db is None:
        init_db()
    return _db

def check_db_health():
    """Return current connection diagnostics."""
    global _db_status, _client
    status = dict(_db_status)
    if _client and not status["is_mock"]:
        try:
            _client.admin.command("ping")
            status["connected"] = True
        except Exception as e:
            status["connected"] = False
            status["error"] = str(e)
    return status

def get_next_sequence(sequence_name, prefix="PAT", start=1001):
    """
    Safely and atomically increments the sequence counter for unique human-readable IDs.
    Guarantees conflict-free concurrent ID generation across multiple distributed clients.
    """
    db = get_db()
    if db is None:
        raise RuntimeError("Database connection not established")

    counter = db.counters.find_one_and_update(
        {"_id": sequence_name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    seq_num = counter.get("seq", start)
    return f"{prefix}-{seq_num}"

def log_audit(action, user="system", role="system", details=None, client_ip="127.0.0.1"):
    """
    Records an immutable audit trail entry in the centralized database.
    Demonstrates distributed systems security and audit tracking.
    """
    db = get_db()
    if db is None:
        return
    try:
        db.audit_logs.insert_one({
            "timestamp": datetime.now(timezone.utc),
            "action": action,
            "user": user,
            "role": role,
            "details": details or {},
            "client_ip": client_ip
        })
    except Exception as e:
        logger.error(f"Failed to record audit log: {e}")

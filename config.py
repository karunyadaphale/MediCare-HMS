import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Base application configuration."""
    SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret-key-for-dev-only-39281")
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    DB_NAME = os.getenv("DB_NAME", "medicare_hms")
    
    # Initial Admin Seed Credentials
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin@123")
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@medicare.local")
    ADMIN_NAME = os.getenv("ADMIN_NAME", "System Administrator")

    # Host & Port Settings
    FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "t")

    # Fallback toggle if remote Atlas is unreachable during offline demo/testing
    USE_MOCK_DB_IF_UNAVAILABLE = os.getenv("USE_MOCK_DB_IF_UNAVAILABLE", "True").lower() in ("true", "1", "t")

    # Session & Cookie Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max request payload

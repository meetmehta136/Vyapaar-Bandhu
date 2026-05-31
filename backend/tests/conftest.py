import os
import sys

# Ensure backend/ is on sys.path so 'from app...' imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["TESTING"] = "true"
os.environ["LOG_LEVEL"] = "INFO"
os.environ["TWILIO_AUTH_TOKEN"] = "test_token_for_ci"
os.environ["TWILIO_FROM"] = "whatsapp:+14155551234"
os.environ["DATABASE_URL"] = "sqlite:///test.db"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://vyapaar_bandhu_db_user:bgcHI8sWwK301ov5V9vD277zcPpwaJKs@dpg-d6mq127tskes73e2m230-a/vyapaar_bandhu_db"
)

# Render PostgreSQL requires this
engine = create_engine(DATABASE_URL, connect_args={"sslmode": "require"})
SessionLocal = sessionmaker(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
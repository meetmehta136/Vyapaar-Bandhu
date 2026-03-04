from fastapi import FastAPI
from app.models.base import Base
from app.core.database import engine

app = FastAPI(
    title="VyapaarBandhu",
    description="AI GST Compliance Assistant for Indian Small Businesses",
    version="0.1.0"
)

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    print("✅ All 8 tables created")

@app.get("/health")
def health_check():
    return {
        "status": "alive",
        "product": "VyapaarBandhu",
        "version": "0.1.0"
    }
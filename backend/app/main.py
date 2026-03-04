from fastapi import FastAPI

app = FastAPI(
    title="VyapaarBandhu",
    description="AI GST Compliance Assistant for Indian Small Businesses",
    version="0.1.0"
)

@app.get("/health")
def health_check():
    return {
        "status": "alive",
        "product": "VyapaarBandhu",
        "version": "0.1.0"
    }
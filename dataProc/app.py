from fastapi import FastAPI
from routes.clean import router as clean_router
from routes.duration import router as duration_router
from routes.sequence import router as sequence_router

app = FastAPI(title="Data Processor", version="1.0.0")


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


# Mount versioned routers
app.include_router(clean_router)
app.include_router(duration_router)
app.include_router(sequence_router)

from fastapi import FastAPI
from routes.clean import router as clean_router

app = FastAPI(title="Data Processor", version="1.0.0")


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


# Mount versioned routers
app.include_router(clean_router)

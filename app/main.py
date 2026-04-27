from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(title="Local Agent Platform")

app.include_router(router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}

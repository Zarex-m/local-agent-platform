from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.conversation_routes import router as conversation_router
from app.api.file_routes import router as file_router
from app.api.routes import router
from app.api.tool_routes import router as tool_router
from app.storage.database import init_db

init_db()

app = FastAPI(title="Local Agent Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(conversation_router)
app.include_router(tool_router)
app.include_router(file_router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}

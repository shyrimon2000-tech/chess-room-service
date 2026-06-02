from fastapi import FastAPI

from app.routers import rooms


app = FastAPI(
    title="Chess Room Service",
    description="Room management microservice for the chess application",
    version="0.1.0",
)

@app.get("/")
def root():
    return {
        "service": "chess-room-service",
        "status": "running"
    }

@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(rooms.router)
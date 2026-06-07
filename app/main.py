from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.events.subscriber import start_subscriber
from app.routers import rooms


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_subscriber()
    yield


app = FastAPI(
    title="Chess Room Service",
    description="Room management microservice for the chess application",
    version="0.1.0",
    lifespan=lifespan,
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
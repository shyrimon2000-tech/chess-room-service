import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import wait_for_db
from app.events.publisher import wait_for_redis
from app.events.subscriber import start_subscriber
from app.routers import rooms

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
    force=True,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    wait_for_db()
    wait_for_redis()
    start_subscriber()
    logger.info("chess-room-service started")
    yield


app = FastAPI(
    title="Chess Room Service",
    description="Room management microservice for the chess application",
    version="1.0.0",
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
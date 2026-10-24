import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from lib.db import client, ensure_indexes  # noqa: E402
from lib.demo import ensure_demo  # noqa: E402
from routers import auth, clinic, contacts, indicators, services  # noqa: E402

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def _startup() -> None:
    await ensure_indexes()
    try:
        await ensure_demo()
    except Exception as exc:  # never block boot on demo seeding
        logger.error("ensure_demo failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.startup_task = asyncio.create_task(_startup())
    yield
    client.close()


app = FastAPI(lifespan=lifespan, title="Vatrexz OS API")

api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {"message": "Vatrexz OS API", "phase": 1}


api_router.include_router(auth.router)
api_router.include_router(clinic.router)
api_router.include_router(services.router)
api_router.include_router(contacts.router)
api_router.include_router(indicators.router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

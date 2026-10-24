"""Shared Mongo handle — import `client`/`db` from here (server.py, routers, seed.py)."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING, IndexModel

load_dotenv(Path(__file__).parent.parent / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url, tz_aware=True)
db = client[os.environ["DB_NAME"]]

logger = logging.getLogger(__name__)

# One entry per collection: every field a route filters, sorts, or dedupes on. Applied by ensure_indexes() at startup.
INDEXES: dict[str, list[IndexModel]] = {
    "clinics": [IndexModel([("id", ASCENDING)], name="id", unique=True),
                IndexModel([("slug", ASCENDING)], name="slug", unique=True, sparse=True)],
    "users": [IndexModel([("id", ASCENDING)], name="id", unique=True),
              IndexModel([("email", ASCENDING)], name="email", unique=True),
              IndexModel([("clinic_id", ASCENDING), ("name", ASCENDING)], name="clinic_name")],
    "sessions": [IndexModel([("id", ASCENDING)], name="id", unique=True),
                 IndexModel([("expires_at", ASCENDING)], name="ttl", expireAfterSeconds=0)],
    "contacts": [IndexModel([("id", ASCENDING)], name="id", unique=True),
                 IndexModel([("clinic_id", ASCENDING), ("stage", ASCENDING), ("last_interaction_at", DESCENDING)], name="clinic_stage_last"),
                 IndexModel([("clinic_id", ASCENDING), ("entered_at", DESCENDING)], name="clinic_entered")],
    "contact_events": [IndexModel([("id", ASCENDING)], name="id", unique=True),
                       IndexModel([("clinic_id", ASCENDING), ("contact_id", ASCENDING), ("at", DESCENDING)], name="clinic_contact_at")],
    "services": [IndexModel([("id", ASCENDING)], name="id", unique=True),
                 IndexModel([("clinic_id", ASCENDING), ("name", ASCENDING)], name="clinic_name")],
    "audit_logs": [IndexModel([("clinic_id", ASCENDING), ("at", DESCENDING)], name="clinic_at")],
}


async def ensure_indexes() -> None:
    for collection, models in INDEXES.items():
        for model in models:  # one at a time so a bad spec skips only itself
            try:
                await db[collection].create_indexes([model])
            except Exception as exc:  # never block boot on an index; the log line names what to fix
                logger.error("ensure_indexes(%s.%s): %s", collection, model.document["name"], exc)

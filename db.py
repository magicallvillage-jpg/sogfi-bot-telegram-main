import os
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

import certifi
import motor.motor_asyncio
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MONGO_URL = os.getenv("MONGO_URL")
if not MONGO_URL:
    raise RuntimeError(
        "MONGO_URL is not set. Add it to a .env file next to app.py."
    )

client = motor.motor_asyncio.AsyncIOMotorClient(
    MONGO_URL,
    tlsCAFile=certifi.where(),
)

# ---------------------------------------------------------------------------
# Databases
# ---------------------------------------------------------------------------
db = client["Neww"]                 # misc bot settings / stats collections
characters_db = client["Cluster0"]  # shared character catalog (also written by the uploader bot)

# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------
collection = characters_db["Takecharacters4"]      # shared character catalog (read here, written by uploader bot)
uploader_collection = db["uploaders"]
group_settings = db["group_collections"]
group_collection = db["lmao000o"]
user_collection = db["userrs"]
daily_limit_collection = db["dailly"]
banned_users_collection = db["ban"]
special_group_settings = db["special_group_settings"]
user_message_counts = db["user_message_counts"]
elixir_counts_collection = db["elixir_counts_collection"]
p2p_collection = db["p2p"]


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
async def ensure_indexes() -> None:
    """Create/verify indexes. Call once during application startup."""
    await collection.create_index([("character_id", 1)], unique=True, sparse=True)
    await collection.create_index(
        [("name", "text"), ("anime", "text"), ("event", "text")],
        name="search_index",
    )
    await collection.create_index([("rarity", 1)])
    await collection.create_index([("uploader_id", 1)])
    await user_collection.create_index([("user_id", 1)], unique=True, sparse=True)
    await group_settings.create_index([("group_id", 1)], unique=True, sparse=True)
    logger.info("Indexes created/verified")


# ---------------------------------------------------------------------------
# Uploader check
# ---------------------------------------------------------------------------
async def is_uploader(user_id: int) -> bool:
    uploader = await uploader_collection.find_one({"user_id": user_id})
    return uploader is not None


# ---------------------------------------------------------------------------
# Character lookups (read-only from this bot's perspective)
# ---------------------------------------------------------------------------
async def get_character_by_id(character_id: int) -> Optional[Dict]:
    try:
        return await collection.find_one({"character_id": character_id})
    except Exception as e:
        logger.error(f"Error fetching character {character_id}: {e}")
        return None


async def get_characters_by_ids(character_ids: List[int]) -> List[Dict]:
    try:
        cursor = collection.find({"character_id": {"$in": character_ids}})
        return await cursor.to_list(length=None)
    except Exception as e:
        logger.error(f"Error fetching characters {character_ids}: {e}")
        return []


async def get_random_character(rarity: Optional[str] = None) -> Optional[Dict]:
    """Get a random character, optionally filtered by rarity."""
    try:
        match = {"rarity": rarity} if rarity else {}
        pipeline = [{"$match": match}, {"$sample": {"size": 1}}]
        result = await collection.aggregate(pipeline).to_list(length=1)
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Error getting random character: {e}")
        return None


# ---------------------------------------------------------------------------
# Daily limits (generic helper; take.py currently tracks its own daily limit
# inline on the user document, this is kept for any other feature that wants
# a separate per-action daily counter)
# ---------------------------------------------------------------------------
async def check_daily_limit(user_id: int, limit_type: str, max_limit: int) -> bool:
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        doc = await daily_limit_collection.find_one(
            {"user_id": user_id, "date": today, "type": limit_type}
        )
        return doc["count"] >= max_limit if doc else False
    except Exception as e:
        logger.error(f"Error checking daily limit: {e}")
        return False


async def increment_daily_limit(user_id: int, limit_type: str) -> bool:
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        result = await daily_limit_collection.update_one(
            {"user_id": user_id, "date": today, "type": limit_type},
            {"$inc": {"count": 1}},
            upsert=True,
        )
        return result.acknowledged
    except Exception as e:
        logger.error(f"Error incrementing daily limit: {e}")
        return False

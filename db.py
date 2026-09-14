import motor.motor_asyncio
import logging
import random
from typing import List, Dict, Optional
from bson import ObjectId
from config import MONGO_URL, MONGO_URL2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
client2 = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL2)
db = client["Neww"]
db2 = client["Cluster0"]

db1 = client2["Neww"]
db3 = client["Cluster0"]


# Collections
collection = db2["Takecharacters4"]  # Main characters collection
uploader_collection = db["uploaders"]
counter_collection = db["counters"]
group_settings = db["group_collections"]
group_collection = db["lmao000o"]
user_collection = db["userrs"]
user_collection1 = db1["userrs"]
daily_limit_collection = db["dailly"]
banned_users_collection = db["ban"]
special_group_settings = db["special_group_settings"]
user_message_counts = db["user_message_counts"]
elixir_counts_collection = db["elixir_counts_collection"]
p2p_collection = db["p2p"]

async def ensure_indexes():
    """Create necessary indexes for optimal performance"""
    await collection.create_index([("character_id", 1)], unique=True)
    await collection.create_index([("name", "text"), ("anime", "text"), ("event", "text")], name="search_index")
    await collection.create_index([("rarity", 1)])
    await collection.create_index([("uploader_id", 1)])
    logger.info("Indexes created/verified")

async def get_next_character_id():
    """Get the next available character ID"""
    last_character = await collection.find_one(sort=[("character_id", -1)])
    return last_character["character_id"] + 1 if last_character else 1

async def is_uploader(user_id: int):
    """Check if user is an uploader"""
    uploader = await uploader_collection.find_one({"user_id": user_id})
    return uploader is not None

# Character CRUD Operations
async def add_character(character_data: Dict) -> bool:
    """Add a new character to the database"""
    try:
        character_data["character_id"] = await get_next_character_id()
        result = await collection.insert_one(character_data)
        return result.acknowledged
    except Exception as e:
        logger.error(f"Error adding character: {e}")
        return False

async def update_character(character_id: int, update_data: Dict) -> bool:
    """Update an existing character"""
    try:
        result = await collection.update_one(
            {"character_id": character_id},
            {"$set": update_data}
        )
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"Error updating character: {e}")
        return False

async def delete_character(character_id: int) -> bool:
    """Delete a character from the database"""
    try:
        result = await collection.delete_one({"character_id": character_id})
        return result.deleted_count > 0
    except Exception as e:
        logger.error(f"Error deleting character: {e}")
        return False

# Search and Fetch Operations
async def search_characters(query: str, limit: int = 20) -> List[Dict]:
    """Search characters using MongoDB text search"""
    try:
        if not query or len(query.strip()) < 2:
            return []
            
        cursor = collection.find(
            {"$text": {"$search": query}},
            {"score": {"$meta": "textScore"}}
        ).sort([("score", {"$meta": "textScore"})]).limit(limit)
        
        return await cursor.to_list(length=limit)
    except Exception as e:
        logger.error(f"Search error: {e}")
        return []

async def get_character_by_id(character_id: int) -> Optional[Dict]:
    """Get a single character by ID"""
    try:
        return await collection.find_one({"character_id": character_id})
    except Exception as e:
        logger.error(f"Error fetching character: {e}")
        return None

async def get_characters_by_ids(character_ids: List[int]) -> List[Dict]:
    """Get multiple characters by their IDs"""
    try:
        cursor = collection.find({"character_id": {"$in": character_ids}})
        return await cursor.to_list(length=None)
    except Exception as e:
        logger.error(f"Error fetching characters: {e}")
        return []

async def get_random_character(rarity: Optional[str] = None) -> Optional[Dict]:
    """Get a random character, optionally filtered by rarity"""
    try:
        match = {"rarity": rarity} if rarity else {}
        pipeline = [
            {"$match": match},
            {"$sample": {"size": 1}}
        ]
        cursor = collection.aggregate(pipeline)
        result = await cursor.to_list(length=1)
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Error getting random character: {e}")
        return None

async def get_characters_by_rarity(rarity: str, limit: int = 50) -> List[Dict]:
    """Get characters filtered by rarity"""
    try:
        cursor = collection.find({"rarity": rarity}).limit(limit)
        return await cursor.to_list(length=limit)
    except Exception as e:
        logger.error(f"Error fetching by rarity: {e}")
        return []

async def get_characters_by_uploader(uploader_id: int, limit: int = 50) -> List[Dict]:
    """Get characters uploaded by a specific user"""
    try:
        cursor = collection.find({"uploader_id": uploader_id}).limit(limit)
        return await cursor.to_list(length=limit)
    except Exception as e:
        logger.error(f"Error fetching by uploader: {e}")
        return []

# User Collection Management
async def add_character_to_user(user_id: int, character_id: int) -> bool:
    """Add a character to a user's collection"""
    try:
        result = await user_collection.update_one(
            {"user_id": user_id},
            {"$addToSet": {"character_ids": character_id}},
            upsert=True
        )
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"Error adding character to user: {e}")
        return False

async def get_user_characters(user_id: int) -> List[Dict]:
    """Get all characters owned by a user"""
    try:
        user = await user_collection.find_one({"user_id": user_id})
        if not user or "character_ids" not in user:
            return []
            
        return await get_characters_by_ids(user["character_ids"])
    except Exception as e:
        logger.error(f"Error getting user characters: {e}")
        return []

# Daily Limits
async def check_daily_limit(user_id: int, limit_type: str, max_limit: int) -> bool:
    """Check if user has reached daily limit for an action"""
    try:
        today = datetime.utcnow().date()
        doc = await daily_limit_collection.find_one(
            {"user_id": user_id, "date": today, "type": limit_type}
        )
        return doc["count"] >= max_limit if doc else False
    except Exception as e:
        logger.error(f"Error checking daily limit: {e}")
        return False

async def increment_daily_limit(user_id: int, limit_type: str) -> bool:
    """Increment user's daily limit counter"""
    try:
        today = datetime.utcnow().date()
        result = await daily_limit_collection.update_one(
            {"user_id": user_id, "date": today, "type": limit_type},
            {"$inc": {"count": 1}},
            upsert=True
        )
        return result.acknowledged
    except Exception as e:
        logger.error(f"Error incrementing daily limit: {e}")
        return False

from db import user_collection, collection as character_collection
import logging
from typing import Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def calculate_anime_count(user_id: int, anime_name: str) -> Tuple[int, int]:
    """
    Calculate anime-specific character counts for a user and globally.
    
    Args:
        user_id: Telegram user ID
        anime_name: Anime name to filter characters
    
    Returns:
        Tuple of (user's count, total count)
    """
    try:
        # 1. Get all character IDs for this anime from character_collection
        anime_chars = await character_collection.find(
            {"anime": anime_name},
            {"character_id": 1}  # Get only character_id field
        ).to_list(length=None)
        
        # Extract just the character IDs as integers
        anime_char_ids = [char["character_id"] for char in anime_chars]
        total_count = len(anime_char_ids)
        
        if not anime_char_ids:
            return 0, 0

        # 2. Get the user's character collection
        user_data = await user_collection.find_one(
            {"user_id": user_id},
            {"characters": 1}  # Only get characters field
        )
        
        if not user_data:
            return 0, total_count

        # 3. Count how many matching characters the user has
        user_characters = user_data.get("characters", {})
        user_count = 0
        
        # Convert keys to integers for comparison
        for char_id in anime_char_ids:
            if str(char_id) in user_characters and user_characters[str(char_id)] > 0:
                user_count += 1

        return user_count, total_count

    except Exception as e:
        logger.error(f"Error in calculate_anime_count: {e}", exc_info=True)
        return 0, 0
